import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
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

from .charge_control import (
    ChargeSettingHandler,
    PENDING_FIELDS,
    make_pending_setter,
    SIMPLE_REGISTER_MAP
)

_LOGGER = logging.getLogger(__name__)

FAST_POLL_DEFAULT = False
ADVANCED_LOGGING = False
CHARGE_PENDING_SUFFIXES = ("start", "end", "day_mask", "power_percent")


class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int, fast_enabled: Optional[bool] = None) -> None:
        self._optimistic_push_enabled: bool = True
        self._optimistic_overlay: dict[str, Any] | None = None
        
        if ADVANCED_LOGGING:
            _LOGGER.info(f"[ADVANCED] SAJModbusHub initialization started - Name: {name}, Host: {host}, Port: {port}, Scan Interval: {scan_interval}s")
        
        _LOGGER.info(f"Initializing SAJModbusHub with scan_interval: {scan_interval} seconds")
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )
        _LOGGER.info(f"SAJModbusHub initialized with update_interval: {self.update_interval}")
        self._host = host
        self._port = port
        set_modbus_config(self._host, self._port)
        self._read_lock = asyncio.Lock()
        self.inverter_data: Dict[str, Any] = {}
        self._client: Optional[AsyncModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        self.fast_enabled: bool = FAST_POLL_DEFAULT if fast_enabled is None else fast_enabled

        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30

        self._warned_missing_states: bool = False
        
        self._pending_cache: Optional[bool] = None
        self._pending_cache_valid: bool = False
        
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

        # Initialize simple pending attributes
        for attr_name in SIMPLE_REGISTER_MAP:
            setattr(self, f"_pending_{attr_name}", None)
        
        # Power state pending attributes
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None
        
        # Initialize handler and verify registered handlers
        self._setting_handler = ChargeSettingHandler(self)
        self._verify_and_log_handlers()

        # Dynamically generate all setter methods from PENDING_FIELDS
        for name, attr_path in PENDING_FIELDS:
            setter = make_pending_setter(attr_path)
            setattr(self, f"set_{name}", setter.__get__(self, self.__class__))

        # Verify setter methods
        for name, _ in PENDING_FIELDS:
            if not hasattr(self, f"set_{name}"):
                _LOGGER.warning("Missing dynamically generated setter for %s", name)
        
        self._fast_coordinator: Optional[DataUpdateCoordinator[Dict[str, Any]]] = None
        self._fast_unsub = None

    def _verify_and_log_handlers(self) -> None:
        """Verify all handlers are registered and log them."""
        handlers = self._setting_handler.get_handlers()
        
        if ADVANCED_LOGGING:
            _LOGGER.info(f"[ADVANCED] Found {len(handlers)} registered handlers:")
            for attr_name, handler_func in handlers.items():
                handler_name = getattr(handler_func, '__name__', 'unknown')
                _LOGGER.debug(f"[ADVANCED]   - {attr_name} → {handler_name}")
        
        # Build set of expected pending attributes
        expected_attrs = set()
        
        # Simple register attributes
        for attr_name in SIMPLE_REGISTER_MAP:
            expected_attrs.add(f"_pending_{attr_name}")
        
        # Power state attributes (both needed for AppMode management)
        expected_attrs.add("_pending_charging_state")
        expected_attrs.add("_pending_discharging_state")
        
        # Charge group (special handler)
        expected_attrs.add("_charge_group")
        
        # Check for missing handlers
        registered_attrs = set(handlers.keys())
        missing_attrs = expected_attrs - registered_attrs
        
        if missing_attrs:
            _LOGGER.error(
                "The following pending attributes have NO registered handler: %s. "
                "This WILL cause RuntimeError during processing. "
                "Please ensure all handlers are registered in ChargeSettingHandler._register_handlers().",
                missing_attrs
            )
            raise RuntimeError(f"Missing handlers for: {missing_attrs}")
        
        # Log extra handlers (shouldn't happen, but useful for debugging)
        extra_attrs = registered_attrs - expected_attrs
        if extra_attrs and ADVANCED_LOGGING:
            _LOGGER.debug(f"[ADVANCED] Extra handlers registered (may be intentional): {extra_attrs}")
        
        _LOGGER.info(f"Handler verification complete: {len(handlers)} handlers ready")

    async def start_main_coordinator(self) -> None:
        """Ensure the main coordinator is running and scheduled."""
        _LOGGER.info("Starting main coordinator scheduling...")
        try:
            await self.async_request_refresh()
            _LOGGER.info("Main coordinator refresh requested")
        except Exception as e:
            _LOGGER.error(f"Failed to request main coordinator refresh: {e}")

    async def process_pending_now(self) -> None:
        """Immediately process pending settings without waiting for next update cycle."""
        _LOGGER.debug("Immediately processing pending settings...")
        try:
            await self._ensure_connected_client()
            await self._process_pending_settings()
            _LOGGER.debug("Immediate pending processing completed")
        except Exception as e:
            _LOGGER.error(f"Immediate pending processing failed: {e}")

    async def _ensure_connected_client(self) -> AsyncModbusTcpClient:
        """Ensure the client is connected under connection lock."""
        if ADVANCED_LOGGING:
            _LOGGER.debug(f"[ADVANCED] _ensure_connected_client called - Current client state: {self._client}")
        
        async with self._connection_lock:
            if ADVANCED_LOGGING:
                _LOGGER.debug("Connection lock acquired for %s:%s", self._host, self._port)
            
            self._client = await connect_if_needed(self._client, self._host, self._port)
            
            if ADVANCED_LOGGING:
                _LOGGER.debug(f"[ADVANCED] connect_if_needed returned client: {self._client}, connected: {self._client.connected if self._client else 'N/A'}")
            
            return self._client
   
    async def start_fast_updates(self) -> None:
        """Create and start the 10s-DataUpdateCoordinator."""
        if not self.fast_enabled:
            _LOGGER.info("Fast coordinator disabled via hub setting; skipping start.")
            return
        if self._fast_coordinator is not None:
            return

        async def _async_update_fast() -> Dict[str, Any]:
            if self._client is None or not self._client.connected:
                await self._ensure_connected_client()
            try:
                result = await modbus_readers.read_additional_modbus_data_1_part_2(self._client, self._read_lock)
                self.inverter_data.update(result)
                _LOGGER.debug("Finished fetching %s data in fast cycle (success: True)", self.name)
                return result
            except ReconnectionNeededError as e:
                _LOGGER.warning("Fast coordinator requires reconnection: %s", e)
                await self.reconnect_client()
                return {}

        self._fast_coordinator = DataUpdateCoordinator[Dict[str, Any]](
            self.hass,
            _LOGGER,
            name=f"{self.name} (fast/10s)",
            update_interval=timedelta(seconds=10),
            update_method=_async_update_fast,
        )
        
        def _fast_coordinator_callback(data=None):
            if data:
                self.inverter_data.update(data)
                _LOGGER.debug("Fast coordinator updated inverter_data cache")
        
        self._fast_unsub = self._fast_coordinator.async_add_listener(_fast_coordinator_callback)
        
        try:
            await self._fast_coordinator.async_refresh()
            _LOGGER.debug("Fast coordinator created and initial refresh completed")
        except Exception as e:
            _LOGGER.warning("Initial refresh of fast coordinator failed: %s", e)

    def _create_client(self) -> AsyncModbusTcpClient:
        _LOGGER.debug("Creating new AsyncModbusTcpClient instance for %s:%s", self._host, self._port)
        return AsyncModbusTcpClient(host=self._host, port=self._port, timeout=10)

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Update connection settings from config entry options."""
        if self.updating_settings:
            if ADVANCED_LOGGING:
                _LOGGER.debug("[ADVANCED] Settings update already in progress, skipping duplicate call")
            return
            
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
                    if self._client:
                        try:
                            await self._client.close()
                        except Exception as e:
                            _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                    self._client = self._create_client()
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")

                restart_fast = self.fast_enabled

                if ADVANCED_LOGGING:
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
        
        if restart_fast:
            await self.restart_fast_updates()

    async def restart_fast_updates(self) -> None:
        """Restart the fast update coordinator with current config."""
        if not self.fast_enabled:
            return
        if self._fast_coordinator is not None:
            try:
                if self._fast_unsub is not None:
                    self._fast_unsub()
                    self._fast_unsub = None
                self._fast_coordinator = None
                _LOGGER.debug("Old fast coordinator removed")
            except Exception as e:
                _LOGGER.warning("Failed to remove old fast coordinator: %s", e)
        await self.start_fast_updates()

    async def reconnect_client(self) -> bool:
        if ADVANCED_LOGGING:
            _LOGGER.info(f"[ADVANCED] reconnect_client called - Current reconnecting state: {self._reconnecting}")
        
        if self._reconnecting:
            _LOGGER.debug("Reconnection already in progress, waiting...")
            return False
            
        async with self._connection_lock:
            if self._reconnecting:
                _LOGGER.debug("Reconnection already in progress (double-check), waiting...")
                return False
                
            if ADVANCED_LOGGING:
                _LOGGER.info("[ADVANCED] Reconnecting Modbus client...")
            
            try:
                self._reconnecting = True
                if self._client:
                    try:
                        await self._client.close()
                    except Exception as e:
                        _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                self._client = self._create_client()
                await ensure_client_connected(self._client, self._host, self._port, _LOGGER)
                
                if ADVANCED_LOGGING:
                    _LOGGER.info("[ADVANCED] Reconnection successful.")
                
                return True
            except Exception as e:
                _LOGGER.error("Reconnection failed: %s", e)
                return False
            finally:
                self._reconnecting = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Regular poll cycle: process pending first, then read fresh values."""
        start = time.monotonic()
        
        if ADVANCED_LOGGING:
            _LOGGER.info(f"[ADVANCED] Main coordinator update cycle started - Fast enabled: {self.fast_enabled}")
        
        _LOGGER.info("Starting main coordinator update cycle")
        try:
            await self._ensure_connected_client()
            
            if self._optimistic_push_enabled and self._has_pending():
                _LOGGER.debug("Found pending settings, applying optimistic overlay")
                self._apply_optimistic_overlay()
                if self._optimistic_overlay:
                    self.async_set_updated_data(self._optimistic_overlay)

            if ADVANCED_LOGGING:
                _LOGGER.info("[ADVANCED] Processing pending settings...")
            
            await self._process_pending_settings()

            if ADVANCED_LOGGING:
                _LOGGER.info("[ADVANCED] Running reader methods...")
            
            cache = await self._run_reader_methods()
            self._optimistic_overlay = None
            self.inverter_data = cache
            
            if ADVANCED_LOGGING:
                _LOGGER.info(f"[ADVANCED] Update cycle completed - Cache size: {len(cache)} items")
            
            return self.inverter_data
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            self._optimistic_overlay = None
            raise
        finally:
            elapsed = round(time.monotonic() - start, 3)
            if ADVANCED_LOGGING:
                _LOGGER.info(f"[ADVANCED] Total update cycle time: {elapsed}s")

    def _get_pending_handlers(self) -> Dict[str, Callable]:
        """Sammelt alle Pending-Handler mit Werten ein."""
        handlers = self._setting_handler.get_handlers()
        pending = {}
        
        for attr_name in handlers.keys():
            if attr_name == "_charge_group":
                if any(getattr(self, f"_pending_charge_{suffix}") is not None
                       for suffix in CHARGE_PENDING_SUFFIXES):
                    pending[attr_name] = handlers[attr_name]
            elif attr_name.startswith("_pending_"):
                if getattr(self, attr_name, None) is not None:
                    pending[attr_name] = handlers[attr_name]
        
        return pending

    async def _process_pending_settings(self) -> None:
        """Verarbeite alle ausstehenden Settings mit Parallelisierung.
        
        Ablauf:
        1. Sammle alle Pending-Handler
        2. Sortiere in parallele (Simple) und sequenzielle (Charge) Handler
        3. Führe Simple-Handler parallel aus (asyncio.gather)
        4. Führe Charge/Discharge-Handler sequenziell aus
        5. Invalidiere Cache
        """
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] _process_pending_settings started")
        
        _LOGGER.debug("Processing pending settings...")
        
        try:
            # 1. Sammle alle Pending-Attribute mit ihren Handlern
            pending = self._get_pending_handlers()
            
            # 1b. Check for discharge pending settings (separate from handlers)
            discharge_pending = [
                idx for idx, slot in enumerate(self._pending_discharges, start=1)
                if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES)
            ]
            
            if not pending and not discharge_pending:
                _LOGGER.debug("No pending settings found to process")
                return
            
            if ADVANCED_LOGGING:
                _LOGGER.info(f"[ADVANCED] Found {len(pending)} pending handler(s): {list(pending.keys())}")
            
            # 2. Sortiere in parallele und sequenzielle Handler
            # Simple Handler: unabhängig, können parallel laufen
            simple_pending = {
                k: v for k, v in pending.items()
                if not (k == "_charge_group" or k.startswith("_pending_charge_"))
            }
            
            # Charge Handler: haben Abhängigkeiten, müssen sequenziell laufen
            charge_pending = {
                k: v for k, v in pending.items()
                if k == "_charge_group" or k.startswith("_pending_charge_")
            }
            
            # Discharge Handler: Already collected above, just log
            if discharge_pending:
                _LOGGER.info(f"[PENDING DEBUG] Found discharge pending for indices: {discharge_pending}")
                for idx in discharge_pending:
                    slot = self._pending_discharges[idx - 1]
                    _LOGGER.info(
                        f"[PENDING DEBUG] Discharge{idx} pending values: "
                        f"start={slot.get('start')}, end={slot.get('end')}, "
                        f"day_mask={slot.get('day_mask')}, power_percent={slot.get('power_percent')}"
                    )
            
            results = []
            
            # 3a. Parallele Ausführung von einfachen Handlern
            if simple_pending:
                if ADVANCED_LOGGING:
                    _LOGGER.info(f"[ADVANCED] Executing {len(simple_pending)} simple handler(s) in parallel")
                
                tasks = [handler() for handler in simple_pending.values()]
                simple_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for attr_name, result in zip(simple_pending.keys(), simple_results):
                    if isinstance(result, Exception):
                        _LOGGER.error(
                            "Error executing handler for '%s': %s",
                            attr_name, result, exc_info=result
                        )
                    else:
                        results.append((attr_name, result))
                        if ADVANCED_LOGGING and result:
                            _LOGGER.debug(f"[ADVANCED] Handler '{attr_name}' succeeded")
            
            # 3b. Sequenzielle Ausführung von Charge-Handlern
            if charge_pending:
                if ADVANCED_LOGGING:
                    _LOGGER.info(f"[ADVANCED] Executing {len(charge_pending)} charge handler(s) sequentially")
                
                for attr_name, handler in charge_pending.items():
                    try:
                        result = await handler()
                        results.append((attr_name, result))
                        if ADVANCED_LOGGING:
                            _LOGGER.debug(f"[ADVANCED] Charge handler '{attr_name}' completed")
                    except Exception as e:
                        _LOGGER.error(
                            "Error executing charge handler '%s': %s",
                            attr_name, e, exc_info=e
                        )
            
            # 3c. Discharge-Handler (sequenziell pro Index)
            for discharge_idx in discharge_pending:
                try:
                    if ADVANCED_LOGGING:
                        _LOGGER.debug(f"[ADVANCED] Processing discharge settings for index {discharge_idx}")
                    
                    await self._setting_handler.handle_discharge_settings_by_index(discharge_idx)
                    results.append((f"discharge{discharge_idx}", True))
                except Exception as e:
                    _LOGGER.error(
                        "Error processing discharge settings for index %s: %s",
                        discharge_idx, e, exc_info=e
                    )
            
            # 4. Summary
            successful = sum(1 for _, r in results if r is True)
            if ADVANCED_LOGGING and results:
                _LOGGER.info(
                    f"[ADVANCED] Pending processing complete: "
                    f"{successful}/{len(pending) + len(discharge_pending)} successful"
                )
        
        except Exception as e:
            _LOGGER.warning(
                "Pending processing failed, continuing to read phase: %s",
                e, exc_info=True
            )
        
        finally:
            self._invalidate_pending_cache()

    async def _run_reader_methods(self) -> Dict[str, Any]:
        """Sequential execution of readers; builds the cache."""
        if ADVANCED_LOGGING:
            _LOGGER.info(f"[ADVANCED] _run_reader_methods started - Client connected: {self._client.connected if self._client else 'No client'}")
        
        new_cache: Dict[str, Any] = {}
        await self._ensure_connected_client()
        
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
                await self.reconnect_client()
                try:
                    part = await method(self._client, self._read_lock)
                    if part:
                        new_cache.update(part)
                except Exception as e:
                    _LOGGER.warning(f"Retry failed for {method.__name__}: {e}")
            except Exception as e:
                _LOGGER.warning("Reader failed: %s", e)
        
        return new_cache

    async def _get_power_state(self, state_key: str, state_type: str) -> Optional[bool]:
        """Reads raw status + AppMode from cache and returns a bool."""
        try:
            state_value = self.inverter_data.get(state_key)
            app_mode_value = self.inverter_data.get("AppMode")

            if state_value is None or app_mode_value is None:
                if not self._warned_missing_states:
                    _LOGGER.warning(f"{state_type} state or AppMode not available in cached data")
                    self._warned_missing_states = True
                else:
                    _LOGGER.debug("%s state still not available; skip derived handling", state_type)
                return None

            if self._warned_missing_states:
                self._warned_missing_states = False

            return bool(state_value > 0 and app_mode_value == 1)
        except Exception as e:
            _LOGGER.error(f"Error checking {state_type} state: {e}")
            return None

    async def get_charging_state(self) -> Optional[bool]:
        return await self._get_power_state("charging_enabled", "Charging")

    async def get_discharging_state(self) -> Optional[bool]:
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
                if self._fast_unsub is not None:
                    self._fast_unsub()
                    self._fast_unsub = None
                self._fast_coordinator = None
                _LOGGER.debug("Fast coordinator listener removed")
            except Exception as e:
                _LOGGER.warning("Failed to remove fast coordinator listener: %s", e)

        if self._client:
            try:
                await self._client.close()
                _LOGGER.debug("Modbus client connection closed")
            except Exception as e:
                _LOGGER.warning("Error closing Modbus client: %s", e)
            finally:
                self._client = None
                _LOGGER.debug("Modbus client cleaned up")

    # --- Helper functions ---
    def _has_pending(self) -> bool:
        """Checks if there are pending changes (with caching)."""
        if self._pending_cache_valid:
            return self._pending_cache
        
        # Check simple pending attributes
        for attr_name in SIMPLE_REGISTER_MAP:
            if getattr(self, f"_pending_{attr_name}") is not None:
                self._pending_cache = True
                self._pending_cache_valid = True
                return True
        
        # Check power state
        if self._pending_charging_state is not None or self._pending_discharging_state is not None:
            self._pending_cache = True
            self._pending_cache_valid = True
            return True
        
        # Check charge settings
        if any(
            getattr(self, f"_pending_charge_{suffix}") is not None
            for suffix in CHARGE_PENDING_SUFFIXES
        ):
            self._pending_cache = True
            self._pending_cache_valid = True
            return True
        
        # Check discharge settings
        for slot in self._pending_discharges:
            if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES):
                self._pending_cache = True
                self._pending_cache_valid = True
                return True
        
        self._pending_cache = False
        self._pending_cache_valid = True
        return False
    
    def _invalidate_pending_cache(self) -> None:
        """Invalidate the pending cache when pending values change."""
        self._pending_cache_valid = False

    def _apply_optimistic_overlay(self) -> None:
        """Marks the expected target state in the local cache."""
        try:
            base = dict(self.inverter_data or {})
            chg = base.get("charging_enabled")
            dchg = base.get("discharging_enabled")
            
            if self._pending_charging_state is not None:
                chg = 1 if self._pending_charging_state else 0
            if self._pending_discharging_state is not None:
                dchg = 1 if self._pending_discharging_state else 0
            
            app_mode = 1 if bool(chg) or bool(dchg) else 0

            overlay = base
            if chg is not None:
                overlay["charging_enabled"] = 1 if chg else 0
            if dchg is not None:
                overlay["discharging_enabled"] = 1 if dchg else 0
            overlay["AppMode"] = app_mode

            self._optimistic_overlay = overlay
        except Exception as e:
            _LOGGER.debug("Optimistic overlay skipped: %s", e)