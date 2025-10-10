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

# Global switch: Fast-Coordinator (10s) active by default?
FAST_POLL_DEFAULT = False # True or False

CHARGE_PENDING_SUFFIXES = ("start", "end", "day_mask", "power_percent")

SIMPLE_PENDING_ATTRS = (
    "_pending_charging_state",
    "_pending_discharging_state",
    "_pending_export_limit",
    "_pending_app_mode",
    "_pending_discharge_time_enable",
    "_pending_battery_on_grid_discharge_depth",
    "_pending_battery_off_grid_discharge_depth",
    "_pending_battery_capacity_charge_upper_limit",
    "_pending_battery_charge_power_limit",
    "_pending_battery_discharge_power_limit",
    "_pending_grid_max_charge_power",
    "_pending_grid_max_discharge_power",
    "_pending_passive_charge_enable",
    "_pending_passive_grid_charge_power",
    "_pending_passive_grid_discharge_power",
    "_pending_passive_bat_charge_power",
    "_pending_passive_bat_discharge_power",
)

PENDING_HANDLER_MAP = [
    ("_pending_charging_state", "handle_pending_charging_state"),
    ("_pending_discharging_state", "handle_pending_discharging_state"),
    ("_charge_group", "handle_charge_settings"),
    ("_pending_export_limit", "handle_export_limit"),
    ("_pending_app_mode", "handle_app_mode"),
    ("_pending_discharge_time_enable", "handle_discharge_time_enable"),
    ("_pending_battery_on_grid_discharge_depth", "handle_battery_on_grid_discharge_depth"),
    ("_pending_battery_off_grid_discharge_depth", "handle_battery_off_grid_discharge_depth"),
    ("_pending_battery_capacity_charge_upper_limit", "handle_battery_capacity_charge_upper_limit"),
    ("_pending_battery_charge_power_limit", "handle_battery_charge_power_limit"),
    ("_pending_battery_discharge_power_limit", "handle_battery_discharge_power_limit"),
    ("_pending_grid_max_charge_power", "handle_grid_max_charge_power"),
    ("_pending_grid_max_discharge_power", "handle_grid_max_discharge_power"),
    ("_pending_passive_charge_enable", "handle_passive_charge_enable"),
    ("_pending_passive_grid_charge_power", "handle_passive_grid_charge_power"),
    ("_pending_passive_grid_discharge_power", "handle_passive_grid_discharge_power"),
    ("_pending_passive_bat_charge_power", "handle_passive_bat_charge_power"),
    ("_pending_passive_bat_discharge_power", "handle_passive_bat_discharge_power"),
]


class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int, fast_enabled: Optional[bool] = None) -> None:
        # Optional: UI optimism during an interval before real reads return
        self._optimistic_push_enabled: bool = True
        self._optimistic_overlay: dict[str, Any] | None = None
        super().__init__(
            # Coordinator base
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
        # Fast-Poll switch (None => use FAST_POLL_DEFAULT)
        self.fast_enabled: bool = FAST_POLL_DEFAULT if fast_enabled is None else fast_enabled

        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30

        # One-time warning switch against log spam for missing states/AppMode
        self._warned_missing_states: bool = False
        # Pending settings
        self._pending_charge_start: Optional[str] = None
        self._pending_charge_end: Optional[str] = None
        self._pending_charge_day_mask: Optional[int] = None
        self._pending_charge_power_percent: Optional[int] = None
       
        
        # Pending settings for additional discharge times
        self._pending_discharges: List[Dict[str, Optional[Any]]] = [
            {key: None for key in CHARGE_PENDING_SUFFIXES}
            for _ in range(7)
        ]

        for attr in SIMPLE_PENDING_ATTRS:
            setattr(self, attr, None)
        
        self._setting_handler = ChargeSettingHandler(self)

        # Dynamically generate all setter methods from the PENDING_FIELDS list
        for name, attr_path in PENDING_FIELDS:
            setter = make_pending_setter(attr_path)
            setattr(self, f"set_{name}", setter.__get__(self, self.__class__))


        # Verify that all expected setter methods were created
        for name, _ in PENDING_FIELDS:
            if not hasattr(self, f"set_{name}"):
                _LOGGER.warning("Missing dynamically generated setter for %s", name)
        # Second coordinator (10s) is initialized when needed
        self._fast_coordinator: Optional[DataUpdateCoordinator[Dict[str, Any]]] = None
        # Note: no own task set needed anymore
   
    async def start_fast_updates(self) -> None:
        """Create and start the 10s-DataUpdateCoordinator for part_2."""
        # If globally disabled, don't start
        if not self.fast_enabled:
            _LOGGER.info("Fast coordinator disabled via hub setting; skipping start.")
            return
        if self._fast_coordinator is not None:
            return

        async def _async_update_fast() -> Dict[str, Any]:
            # Ensure the client is connected
            self._client = await connect_if_needed(self._client, self._host, self._port)
            try:
                result = await modbus_readers.read_additional_modbus_data_1_part_2(self._client, self._read_lock)
                # Update cache (don't overwrite with raw data)
                self.inverter_data.update(result)
                _LOGGER.debug("Finished fetching %s data in fast cycle (success: True)", self.name)
                return result
            except ReconnectionNeededError as e:
                _LOGGER.warning("Fast coordinator requires reconnection: %s", e)
                # Single reconnection attempt
                await self.reconnect_client()
                # no automatic retry here; next tick will try again
                return {}

        self._fast_coordinator = DataUpdateCoordinator[Dict[str, Any]](
            self.hass,
            _LOGGER,
            name=f"{self.name} (fast/10s)",
            update_interval=timedelta(seconds=10),
            update_method=_async_update_fast,
        )
        # Perform first refresh so entities can see data immediately
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
        """Regular poll cycle:
        1) Establish connection,
        2) Process pending first (Modbus-Writes),
        3) then read fresh values,
        4) return consolidated cache.
        This shortens the visibility of Pending→Final to ONE interval."""
        start = time.monotonic()
        try:
            # --- Ensure Modbus client is connected ---
            self._client = await connect_if_needed(self._client, self._host, self._port)
            
            # --- Write pending first (including AppMode-OR logic) ---
            # Optional: Mark expected target state in cache (without Modbus, only cosmetic)
            if self._optimistic_push_enabled and self._has_pending():
                self._apply_optimistic_overlay()
                # Optional: Immediate UI update with expected values
                if self._optimistic_overlay:
                    self.async_set_updated_data(self._optimistic_overlay)

            await self._process_pending_settings()  # Executes the Modbus writes (Charging/Discharging + AppMode)

            # --- Then: Get fresh reads so final state is visible in the same interval ---
            cache = await self._run_reader_methods()
            # Discard optimistic overlay, take real values
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
        """Processing pending writes; now called BEFORE the reads."""
        try:
            for attr_name, handler_name in PENDING_HANDLER_MAP:
                if attr_name == "_charge_group":
                    if any(
                        getattr(self, f"_pending_charge_{suffix}") is not None
                        for suffix in CHARGE_PENDING_SUFFIXES
                    ):
                        await getattr(self._setting_handler, handler_name)()
                    continue

                if getattr(self, attr_name) is not None:
                    await getattr(self._setting_handler, handler_name)()

            for index, slot in enumerate(self._pending_discharges, start=1):
                if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES):
                    await self._setting_handler.handle_discharge_settings_by_index(index)
        except Exception as e:
            _LOGGER.warning("Pending processing failed, continuing to read phase: %s", e)

    async def _run_reader_methods(self) -> Dict[str, Any]:
        """Sequential execution of readers; builds the cache."""
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
        
        # If an optimistic overlay was active during this interval,
        # we now have real values — overlay is ignored/deleted.
        return new_cache

    async def _get_power_state(self, state_key: str, state_type: str) -> Optional[bool]:
        """Reads raw status + AppMode from cache and returns a bool,
        or None if data is (still) missing."""
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

            # Once values are present, reset warning switch
            if self._warned_missing_states:
                self._warned_missing_states = False

            # Raw value > 0 and AppMode active (== 1)
            return bool(state_value > 0 and app_mode_value == 1)
        except Exception as e:
            _LOGGER.error(f"Error checking {state_type} state: {e}")
            return None

    async def get_charging_state(self) -> Optional[bool]:
        return await self._get_power_state("charging_enabled", "Charging")

    async def get_discharging_state(self) -> Optional[bool]:
        # Important: Query raw key, not the derived flag
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
    async def async_unload_entry(self) -> None:
       """Cleanup tasks when the config entry is removed."""
       if self._fast_coordinator:
           try:
               # Remove listener and set to None instead of calling async_stop()
               self._fast_coordinator.async_remove_listener(self.async_set_updated_data)
               self._fast_coordinator = None
               _LOGGER.debug("Fast coordinator listener removed")
           except Exception as e:
               _LOGGER.warning("Failed to remove fast coordinator listener: %s", e)

       if self._client and self._client.connected:
           await self._client.close()
           _LOGGER.debug("Modbus client connection closed")

    # --- Helper functions ---
    def _has_pending(self) -> bool:
        """Checks if there are pending changes in the hub (without Handler-API)."""
        if any(getattr(self, attr) is not None for attr in SIMPLE_PENDING_ATTRS):
            return True
        if any(
            getattr(self, f"_pending_charge_{suffix}") is not None
            for suffix in CHARGE_PENDING_SUFFIXES
        ):
            return True
        for slot in self._pending_discharges:
            if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES):
                return True
        return False

    def _apply_optimistic_overlay(self) -> None:
        """Marks the expected target state in the local cache,
        until the real read values come directly afterwards.
        No Modbus accesses, only cosmetic UI snappiness."""
        try:
            # Starting point from current cache
            base = dict(self.inverter_data or {})
            # Derive pending targets directly from hub-pending fields (without Handler-API)
            # We use the *raw* enable keys and only set when pending values are present.
            chg = base.get("charging_enabled")
            dchg = base.get("discharging_enabled")
            if self._pending_charging_state is not None:
                chg = 1 if self._pending_charging_state else 0
            if self._pending_discharging_state is not None:
                dchg = 1 if self._pending_discharging_state else 0
            # AppMode-OR: 1 as soon as at least one is active, otherwise 0
            app_mode = 1 if bool(chg) or bool(dchg) else 0

            overlay = base
            if chg is not None:
                overlay["charging_enabled"] = 1 if chg else 0
            if dchg is not None:
                overlay["discharging_enabled"] = 1 if dchg else 0
            overlay["AppMode"] = app_mode

            self._optimistic_overlay = overlay
            # UI can (if desired) render "approximately" immediately, without Modbus:
            # Note: We do NOT call request_refresh() and no Modbus functions HERE.
            # If you want to update the entities immediately (without Modbus), you could:
            # self.async_set_updated_data(overlay)
            # Since you wish for "no coordinator call on click", we leave that out by default.
        except Exception as e:
            _LOGGER.debug("Optimistic overlay skipped: %s", e)
