import asyncio
import logging
import time
from typing import Optional, Any, Dict, List
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient
from homeassistant.config_entries import ConfigEntry

from . import modbus_readers
from .modbus_utils import (
    try_read_registers,
    try_write_registers,
    ReconnectionNeededError,
    set_modbus_config,
    ensure_client_connected,
    connect_if_needed,
)

# Import of the Pending-Setter Factory and Fields
from .charge_control import ChargeSettingHandler, PENDING_FIELDS, make_pending_setter

_LOGGER = logging.getLogger(__name__)

# Globaler Schalter: Fast-Coordinator (10s) standardmäßig aktiv?
FAST_POLL_DEFAULT = True # True or False


class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int, fast_enabled: Optional[bool] = None) -> None:
        # Optional: UI-Optimismus während eines Intervalls, bevor echte Reads zurückkommen
        self._optimistic_push_enabled: bool = True
        self._optimistic_overlay: dict[str, Any] | None = None
        super().__init__(
            # Coordinator-Basis
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )
        self._host = host
        self._port = port
        set_modbus_config(self._host, self._port)
        self._read_lock = asyncio.Lock()
        self.inverter_data: Dict[str, Any] = {}
        self._client: Optional[AsyncModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        # Fast-Poll-Schalter (None => nutze FAST_POLL_DEFAULT)
        self.fast_enabled: bool = FAST_POLL_DEFAULT if fast_enabled is None else fast_enabled

        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30

        # Einmal-Warnschalter gegen Log-Spam bei fehlenden States/AppMode
        self._warned_missing_states: bool = False
        # Pending settings
        self._pending_charge_start: Optional[str] = None
        self._pending_charge_end: Optional[str] = None
        self._pending_charge_day_mask: Optional[int] = None
        self._pending_charge_power_percent: Optional[int] = None
       
        
        # Pending settings for additional discharge times
        self._pending_discharges: List[Dict[str, Optional[Any]]] = []
        for _ in range(7): # Initialize 7 discharge setting slots
            self._pending_discharges.append({
                "start": None,
                "end": None,
                "day_mask": None,
                "power_percent": None,
            })
        
        self._pending_export_limit: Optional[int] = None
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None
        self._pending_app_mode: Optional[int] = None
        self._pending_discharge_time_enable: Optional[int] = None
        self._pending_battery_on_grid_discharge_depth: Optional[int] = None
        self._pending_battery_off_grid_discharge_depth: Optional[int] = None
        self._pending_battery_capacity_charge_upper_limit: Optional[int] = None
        self._pending_battery_charge_power_limit: Optional[int] = None
        self._pending_battery_discharge_power_limit: Optional[int] = None
        self._pending_grid_max_charge_power: Optional[int] = None
        self._pending_grid_max_discharge_power: Optional[int] = None
        self._pending_settings: Dict[str, Any] = {}

        self._setting_handler = ChargeSettingHandler(self)

        # Dynamically generate all setter methods from the PENDING_FIELDS list
        for name, attr_path in PENDING_FIELDS:
            setter = make_pending_setter(attr_path)
            setattr(self, f"set_{name}", setter.__get__(self, self.__class__))


             # Verify that all expected setter methods were created
        for name, _ in PENDING_FIELDS:
            if not hasattr(self, f"set_{name}"):
                _LOGGER.warning("Missing dynamically generated setter for %s", name)
        # Zweiter Coordinator (10s) wird bei Bedarf initialisiert
        self._fast_coordinator: Optional[DataUpdateCoordinator[Dict[str, Any]]] = None
        # Hinweis: kein eigener Task-Satz mehr nötig
   
    async def start_fast_updates(self) -> None:
        """Erzeuge und starte den 10s-DataUpdateCoordinator für part_2."""
        # Wenn global deaktiviert, nicht starten
        if not self.fast_enabled:
            _LOGGER.info("Fast coordinator disabled via hub setting; skipping start.")
            return
        if self._fast_coordinator is not None:
            return

        async def _async_update_fast() -> Dict[str, Any]:
            # Sicherstellen, dass der Client verbunden ist
            self._client = await connect_if_needed(self._client, self._host, self._port)
            try:
                result = await modbus_readers.read_additional_modbus_data_1_part_2(self._client, self._read_lock)
                # Cache aktualisieren (nicht mit Rohdaten überschreiben)
                self.inverter_data.update(result)
                _LOGGER.debug("Finished fetching %s data in fast cycle (success: True)", self.name)
                return result
            except ReconnectionNeededError as e:
                _LOGGER.warning("Fast coordinator requires reconnection: %s", e)
                # Einmaliger Reconnect-Versuch
                await self.reconnect_client()
                # kein automatisches Retry hier; nächster Tick greift erneut
                return {}

        self._fast_coordinator = DataUpdateCoordinator[Dict[str, Any]](
            self.hass,
            _LOGGER,
            name=f"{self.name} (fast/10s)",
            update_interval=timedelta(seconds=10),
            update_method=_async_update_fast,
        )
        # Ersten Refresh durchführen, damit Entities sofort Daten sehen
        await self._fast_coordinator.async_config_entry_first_refresh()

    def _create_client(self) -> AsyncModbusTcpClient:
        _LOGGER.debug(f"Creating new Modbus client: AsyncModbusTcpClient {self._host}:{self._port}")
        return AsyncModbusTcpClient(host=self._host, port=self._port, timeout=10)

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Update connection settings from config entry options."""
        async with self._connection_lock:
            self.updating_settings = True
            try:
                connection_changed = (host != self._host) or (port != self._port)
                self._host = host
                self._port = port
                set_modbus_config(self._host, self._port)
                self.update_interval = timedelta(seconds=scan_interval)

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    # Close the old client if it exists
                    if self._client:
                        try:
                            self._client.close()
                        except Exception as e:
                            _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                    self._client = self._create_client()
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")

                # Log the updated configuration
                _LOGGER.debug(
                    "Updated configuration - Host: %s, Port: %d, Scan Interval: %d",
                    self._host,
                    self._port,
                    scan_interval
                )
            except Exception as e:
                _LOGGER.error("Failed to update connection settings: %s", e)
                raise
            finally:
                self.updating_settings = False

    async def reconnect_client(self) -> bool:
        async with self._connection_lock:
            _LOGGER.info("Reconnecting Modbus client...")
            if self._reconnecting:
                _LOGGER.debug("Reconnection already in progress, waiting...")
                return False
            try:
                self._reconnecting = True
                if self._client:
                    try:
                        self._client.close()
                    except Exception as e:
                        _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                self._client = self._create_client() # Recreate client to ensure a fresh connection attempt
                await ensure_client_connected(self._client, self._host, self._port, _LOGGER)
                _LOGGER.info("Reconnection successful.")
                return True
            except Exception as e:
                _LOGGER.error("Reconnection failed: %s", e)
                return False
            finally:
                self._reconnecting = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Regelmäßiger Poll-Zyklus:
        1) Verbindung herstellen,
        2) Pending zuerst abarbeiten (Modbus-Writes),
        3) dann frische Werte lesen,
        4) konsolidierten Cache zurückgeben.
        Dadurch verkürzt sich die Sichtbarkeit von Pending→Final auf EIN Intervall."""
        start = time.monotonic()
        try:
            # --- Sicherstellen, dass Modbus-Client verbunden ist ---
            self._client = await connect_if_needed(self._client, self._host, self._port)
            
            # --- Pending zuerst schreiben (inkl. AppMode-OR-Logik) ---
            # Optional: Erwarteten Zielzustand im Cache markieren (ohne Modbus, nur kosmetisch)
            if self._optimistic_push_enabled and self._has_pending():
                self._apply_optimistic_overlay()
                # Optional: Sofortige UI-Aktualisierung mit erwarteten Werten
                if self._optimistic_overlay:
                    self.async_set_updated_data(self._optimistic_overlay)

            await self._process_pending_settings()  # führt die Modbus-Writes aus (Charging/Discharging + AppMode)

            # --- Danach: Frische Reads holen, damit direkt finaler Zustand im selben Intervall sichtbar ist ---
            cache = await self._run_reader_methods()
            # Optimismus-Overlay verwerfen, echte Werte übernehmen
            self._optimistic_overlay = None
            self.inverter_data = cache
            return self.inverter_data
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            raise
        finally:
            elapsed = round(time.monotonic() - start, 3)
            _LOGGER.debug("Update cycle took %ss", elapsed)

    async def _process_pending_settings(self) -> None:
        """Abarbeitung ausstehender Writes; jetzt VOR den Reads aufgerufen."""
        # Es gibt in ChargeSettingHandler KEIN has_pending/handle_all_pending.
        # Wir prüfen die Hub-Pending-Felder und rufen die passenden Handler direkt auf.
        try:
            pending_handlers = [
                (self._pending_charging_state is not None, self._setting_handler.handle_pending_charging_state),
                (self._pending_discharging_state is not None, self._setting_handler.handle_pending_discharging_state),
                (
                    any(getattr(self, f"_pending_charge_{attr}") is not None for attr in ["start", "end", "day_mask", "power_percent"]),
                    self._setting_handler.handle_charge_settings,
                ),
                (self._pending_export_limit is not None, self._setting_handler.handle_export_limit),
                (self._pending_app_mode is not None, self._setting_handler.handle_app_mode),
                (self._pending_discharge_time_enable is not None, self._setting_handler.handle_discharge_time_enable),
                (self._pending_battery_on_grid_discharge_depth is not None, self._setting_handler.handle_battery_on_grid_discharge_depth),
                (self._pending_battery_off_grid_discharge_depth is not None, self._setting_handler.handle_battery_off_grid_discharge_depth),
                (self._pending_battery_capacity_charge_upper_limit is not None, self._setting_handler.handle_battery_capacity_charge_upper_limit),
                (self._pending_battery_charge_power_limit is not None, self._setting_handler.handle_battery_charge_power_limit),
                (self._pending_battery_discharge_power_limit is not None, self._setting_handler.handle_battery_discharge_power_limit),
                (self._pending_grid_max_charge_power is not None, self._setting_handler.handle_grid_max_charge_power),
                (self._pending_grid_max_discharge_power is not None, self._setting_handler.handle_grid_max_discharge_power),
            ]
            # Generische Discharge-Handler dynamisch hinzufügen (Slots 1..7)
            for i in range(1, 8):
                if any(self._pending_discharges[i-1][attr] is not None for attr in ["start", "end", "day_mask", "power_percent"]):
                    pending_handlers.append((True, lambda i=i: self._setting_handler.handle_discharge_settings_by_index(i)))
            for condition, handler in pending_handlers:
                if condition:
                    await handler()
        except Exception as e:
            _LOGGER.warning("Pending processing failed, continuing to read phase: %s", e)

    async def _run_reader_methods(self) -> Dict[str, Any]:
        """Sequentielles Ausführen der Reader; baut den Cache."""
        new_cache: Dict[str, Any] = {}
        self._client = await connect_if_needed(self._client, self._host, self._port)
        
        reader_methods = [
            modbus_readers.read_modbus_inverter_data,
            modbus_readers.read_modbus_realtime_data,
            modbus_readers.read_additional_modbus_data_1_part_1,
            modbus_readers.read_additional_modbus_data_1_part_2,
            modbus_readers.read_additional_modbus_data_2_part_1,
            modbus_readers.read_additional_modbus_data_2_part_2,
            modbus_readers.read_additional_modbus_data_3,
            modbus_readers.read_additional_modbus_data_3_2,
            modbus_readers.read_additional_modbus_data_4,
            modbus_readers.read_battery_data,
            modbus_readers.read_inverter_phase_data,
            modbus_readers.read_offgrid_output_data,
            modbus_readers.read_side_net_data,
            modbus_readers.read_passive_battery_data,
            modbus_readers.read_charge_data,
            modbus_readers.read_discharge_data,
            modbus_readers.read_anti_reflux_data,
            modbus_readers.read_meter_a_data,
        ]

        for method in reader_methods:
            try:
                part = await method(self._client, self._read_lock)
                if part:
                    new_cache.update(part)
            except ReconnectionNeededError as e:
                _LOGGER.warning(f"{method.__name__} required reconnection: {e}")
                # Einmaliger Reconnect-Versuch
                await self.reconnect_client()
                # Versuche es erneut
                try:
                    part = await method(self._client, self._read_lock)
                    if part:
                        new_cache.update(part)
                except Exception as e:
                    _LOGGER.warning(f"Retry failed for {method.__name__}: {e}")
            except Exception as e:
                _LOGGER.warning("Reader failed: %s", e)
        
        # Falls während dieses Intervalls ein Optimismus-Overlay aktiv war,
        # haben wir jetzt echte Werte — Overlay wird ignoriert/gelöscht.
        return new_cache

    async def _get_power_state(self, state_key: str, state_type: str) -> Optional[bool]:
        """Liest Roh-Status + AppMode aus dem Cache und liefert ein bool,
        oder None, wenn Daten (noch) fehlen."""
        try:
            state_value = self.inverter_data.get(state_key)
            app_mode_value = self.inverter_data.get("AppMode")  # Key-Bezeichnung wie in deinen Logs

            if state_value is None or app_mode_value is None:
                if not self._warned_missing_states:
                    _LOGGER.warning(f"{state_type} state or AppMode not available in cached data")
                    self._warned_missing_states = True
                else:
                    _LOGGER.debug("%s state still not available; skip derived handling", state_type)
                return None

            # Sobald Werte vorhanden sind, Warnschalter zurücksetzen
            if self._warned_missing_states:
                self._warned_missing_states = False

            # Rohwert > 0 und AppMode aktiv (== 1)
            return bool(state_value > 0 and app_mode_value == 1)
        except Exception as e:
            _LOGGER.error(f"Error checking {state_type} state: {e}")
            return None

    async def get_charging_state(self) -> Optional[bool]:
        return await self._get_power_state("charging_enabled", "Charging")

    async def get_discharging_state(self) -> Optional[bool]:
        # Wichtig: Roh-Key abfragen, nicht das abgeleitete Flag
        return await self._get_power_state("discharging_enabled", "Discharging")

    async def _read_registers(self, address: int, count: int = 1) -> List[int]:
        return await try_read_registers(
            self._client,
            self._read_lock,
            1,
            address,
            count,
        )

    async def _write_register(self, address: int, value: int) -> bool:
        return await try_write_registers(
            self._client,
            self._read_lock,
            1,
            address,
            value,
        )
    async def async_unload_entry(self) -> bool:
        """Handle removal of the Modbus hub."""
        # Fast-Coordinator stoppen (keine weitere 10s-Polling)
        if self._fast_coordinator is not None:
            try:
                await self._fast_coordinator.async_set_update_interval(None)
            except Exception as e:
                _LOGGER.debug("Ignoring error stopping fast coordinator: %s", e)
            self._fast_coordinator = None

        # Close the Modbus client
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                _LOGGER.warning(f"Error while closing Modbus client: {e}")

        # Clear pending settings
        self._pending_settings.clear()
        return True

    # --- Hilfsfunktionen ---
    def _has_pending(self) -> bool:
        """Prüft, ob ausstehende Änderungen im Hub vorhanden sind (ohne Handler-API)."""
        if self._pending_charging_state is not None:
            return True
        if self._pending_discharging_state is not None:
            return True
        if any(getattr(self, f"_pending_charge_{attr}") is not None for attr in ["start", "end", "day_mask", "power_percent"]):
            return True
        if self._pending_export_limit is not None:
            return True
        if self._pending_app_mode is not None:
            return True
        if self._pending_discharge_time_enable is not None:
            return True
        if any([
            self._pending_battery_on_grid_discharge_depth is not None,
            self._pending_battery_off_grid_discharge_depth is not None,
            self._pending_battery_capacity_charge_upper_limit is not None,
            self._pending_battery_charge_power_limit is not None,
            self._pending_battery_discharge_power_limit is not None,
            self._pending_grid_max_charge_power is not None,
            self._pending_grid_max_discharge_power is not None,
        ]):
            return True
        # Discharge-Slots prüfen
        for i in range(7):
            slot = self._pending_discharges[i]
            if any(slot[attr] is not None for attr in ["start", "end", "day_mask", "power_percent"]):
                return True
        return False

    def _apply_optimistic_overlay(self) -> None:
        """Markiert im lokalen Cache den erwarteten Zielzustand,
        bis die echten Read-Werte direkt im Anschluss kommen.
        Keine Modbus-Zugriffe, nur kosmetisches UI-Snappiness."""
        try:
            # Ausgangslage aus aktuellem Cache
            base = dict(self.inverter_data or {})
            # Pending-Ziele direkt aus Hub-Pending-Feldern ableiten (ohne Handler-API)
            # Wir nutzen die *Roh*-Enable-Keys und setzen nur, wenn Pending-Werte vorhanden sind.
            chg = base.get("charging_enabled")
            dchg = base.get("discharging_enabled")
            if self._pending_charging_state is not None:
                chg = 1 if self._pending_charging_state else 0
            if self._pending_discharging_state is not None:
                dchg = 1 if self._pending_discharging_state else 0
            # AppMode-OR: 1 sobald mindestens einer aktiv, sonst 0
            app_mode = 1 if bool(chg) or bool(dchg) else 0

            overlay = base
            if chg is not None:
                overlay["charging_enabled"] = 1 if chg else 0
            if dchg is not None:
                overlay["discharging_enabled"] = 1 if dchg else 0
            overlay["AppMode"] = app_mode

            self._optimistic_overlay = overlay
            # UI kann (wenn gewünscht) sofort „näherungsweise“ rendert, ohne Modbus:
            # Hinweis: Wir rufen HIER NICHT request_refresh() und keine Modbus-Funktionen.
            # Wenn du die Entities sofort updaten willst (ohne Modbus), könntest du:
            # self.async_set_updated_data(overlay)
            # Da du „keinen Coordinator-Aufruf beim Klick“ wünschst, lassen wir das standardmäßig aus.
        except Exception as e:
            _LOGGER.debug("Optimistic overlay skipped: %s", e)
