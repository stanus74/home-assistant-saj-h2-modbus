from __future__ import annotations
"""SAJ Modbus Hub with optimized processing and fixed interval system."""
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
from datetime import timedelta
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval
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

# Define which sensor keys should be updated in fast polling (10s interval)
FAST_POLL_SENSORS = {
    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower", "directionPV", "directionBattery",
    "directionGrid", "directionOutput", "CT_GridPowerWatt",
    "CT_GridPowerVA", "CT_PVPowerWatt", "CT_PVPowerVA", "totalgridPowerVA",
    "TotalInvPowerVA", "BackupTotalLoadPowerWatt", "BackupTotalLoadPowerVA",
}

_simple_pending_attrs_list = []
for _, attr_path in PENDING_FIELDS:
    if "[" in attr_path or attr_path.startswith("charge_"):
        continue
    _simple_pending_attrs_list.append(f"_pending_{attr_path}")

SIMPLE_PENDING_ATTRS = tuple(_simple_pending_attrs_list)

_PENDING_HANDLER_MAP_GENERATED = []
for attr in SIMPLE_PENDING_ATTRS:
    if attr == "_pending_charging_state":
        handler_name = "handle_charging_state"
    elif attr == "_pending_discharging_state":
        handler_name = "handle_discharging_state"
    else:
        handler_name = f"handle_{attr[9:]}"
    _PENDING_HANDLER_MAP_GENERATED.append((attr, handler_name))

PENDING_HANDLER_MAP = _PENDING_HANDLER_MAP_GENERATED


class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._optimistic_push_enabled: bool = True
        self._optimistic_overlay: dict[str, Any] | None = None
 
        host = config_entry.data.get("host")
        port = config_entry.data.get("port", 502)
        scan_interval = config_entry.data.get("scan_interval", 60)
 
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] SAJModbusHub initialization started - Host: %s, Port: %s, Scan Interval: %ss", host, port, scan_interval)
        _LOGGER.info("Initializing SAJModbusHub with scan_interval: %s seconds", scan_interval)
 
        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.title,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )
 
        _LOGGER.info(f"SAJModbusHub initialized with update_interval: {self.update_interval}")
        self._host = host
        self._port = port
        self._config_entry = config_entry
 
        set_modbus_config(self._host, self._port)
        self._read_lock = asyncio.Lock()
        self.inverter_data: Dict[str, Any] = {}
        self._client: Optional[AsyncModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        self.fast_enabled = False  # Initialize fast_enabled attribute
        self._fast_coordinator = None
        self._fast_unsub = None
        self._cancel_fast_update = None
        self._fast_listeners: List[Callable] = []
 
        self._scan_interval = scan_interval
        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30
        self._warned_missing_states: bool = False
        self._inverter_static_data: Optional[Dict[str, Any]] = None
        self._pending_cache: Optional[bool] = None
        self._pending_cache_valid: bool = False

        # Pending base values
        self._pending_charge_start = None
        self._pending_charge_end = None
        self._pending_charge_day_mask = None
        self._pending_charge_power_percent = None

        self._pending_charges = [
            {key: None for key in CHARGE_PENDING_SUFFIXES}
            for _ in range(7)
        ]
        self._pending_discharges = [
            {key: None for key in CHARGE_PENDING_SUFFIXES}
            for _ in range(7)
        ]

        for attr_name in SIMPLE_REGISTER_MAP:
            setattr(self, f"_pending_{attr_name}", None)

        self._pending_charge_time_enable: Optional[int] = None
        self._pending_discharge_time_enable: Optional[int] = None
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None
        self._charging_state_lock_until: Optional[float] = None
        self._discharging_state_lock_until: Optional[float] = None

        self._setting_handler = ChargeSettingHandler(self)
        

        for name, attr_path in PENDING_FIELDS:
            setter = make_pending_setter(attr_path)
            setattr(self, f"set_{name}", setter.__get__(self, self.__class__))

        async def _set_charging_state(self, value: bool) -> None:
            self._pending_charging_state = value
            _LOGGER.info("Set pending charging state to: %s", value)
            if hasattr(self, '_invalidate_pending_cache'):
                self._invalidate_pending_cache()
            self.hass.async_create_task(self.process_pending_now())

        async def _set_discharging_state(self, value: bool) -> None:
            self._pending_discharging_state = value
            _LOGGER.info("Set pending discharging state to: %s", value)
            if hasattr(self, '_invalidate_pending_cache'):
                self._invalidate_pending_cache()
            self.hass.async_create_task(self.process_pending_now())

        self.set_charging = _set_charging_state.__get__(self, self.__class__)
        self.set_discharging = _set_discharging_state.__get__(self, self.__class__)

    async def start_main_coordinator(self) -> None:
        """Start the main coordinator scheduling."""
        _LOGGER.info("Starting main coordinator scheduling...")
        # The DataUpdateCoordinator handles the scheduling, so we just log here.
        # This method is kept for compatibility but does nothing.
        pass

    # ------------------------------------------------------------
    # (rest of your file remains unchanged; omitted for brevity)
    # ------------------------------------------------------------


    async def process_pending_now(self) -> None:
        """Immediately process pending settings without waiting for next update cycle."""
        _LOGGER.debug("Immediately processing pending settings...")
        try:
            await self._ensure_connected_client()
            await self._process_pending_settings()
            _LOGGER.debug("Immediate pending processing completed")
        except Exception as e:
            _LOGGER.error("Immediate pending processing failed: %s", e)

    async def _ensure_connected_client(self) -> AsyncModbusTcpClient:
        """Ensure client is connected under connection lock."""
        if ADVANCED_LOGGING:
            _LOGGER.debug("[ADVANCED] _ensure_connected_client called - Current client state: %s", self._client)
        
        async with self._connection_lock:
            if ADVANCED_LOGGING:
                _LOGGER.debug("Connection lock acquired for %s:%s", self._host, self._port)

            self._client = await connect_if_needed(self._client, self._host, self._port)

            if ADVANCED_LOGGING:
                _LOGGER.debug("[ADVANCED] connect_if_needed returned client: %s, connected: %s", self._client, self._client.connected if self._client else 'N/A')

            return self._client

    async def start_fast_updates(self) -> None:
        """Start fast updates using async_track_time_interval."""
        if not self.fast_enabled:
            _LOGGER.info("Fast updates disabled via hub setting; skipping start.")
            return
        if self._cancel_fast_update is not None:
            _LOGGER.debug("Fast updates already running")
            return

        _LOGGER.info("Starting fast updates with 10s interval using async_track_time_interval")
        
        self._cancel_fast_update = async_track_time_interval(
            self.hass,
            self._async_update_fast,
            timedelta(seconds=10)
        )
        
        # Trigger first update immediately
        await self._async_update_fast()

    async def _async_update_fast(self, now=None) -> None:
        """Fast update function called by async_track_time_interval."""
        if not self.fast_enabled:
            return
            
        if self._client is None or not self._client.connected:
            try:
                await self._ensure_connected_client()
            except Exception as e:
                _LOGGER.warning("Fast update: Failed to ensure connection: %s", e)
                return
        
        try:
            result = await modbus_readers.read_additional_modbus_data_1_part_2(self._client, self._read_lock)
            if result:
                # Filter result to only include fast poll sensors
                fast_data = {k: v for k, v in result.items() if k in FAST_POLL_SENSORS}
                
                if fast_data:
                    # Update internal cache with all data
                    self.inverter_data.update(result)
                    
                    # Only notify fast listeners about fast sensor changes
                    for listener in self._fast_listeners:
                        listener()
                    
                    if ADVANCED_LOGGING:
                        _LOGGER.debug(
                            f"Fast update completed: {len(fast_data)}/{len(result)} sensors updated "
                            f"(filtered to fast sensors only)"
                        )
                else:
                    _LOGGER.debug("Fast update: No fast-poll sensors in result")
        except ReconnectionNeededError as e:
            _LOGGER.warning("Fast update requires reconnection: %s", e)
            await self.reconnect_client()
        except Exception as e:
            _LOGGER.warning("Fast update failed: %s", e)

    @callback
    def async_add_fast_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Add a listener specifically for fast updates."""
        self._fast_listeners.append(update_callback)
        
        @callback
        def remove_listener() -> None:
            """Remove listener."""
            if update_callback in self._fast_listeners:
                self._fast_listeners.remove(update_callback)
        
        return remove_listener

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
                self._scan_interval = scan_interval
                self.update_interval = timedelta(seconds=scan_interval)

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    if self._client:
                        try:
                            await self._client.close()
                        except Exception as e:
                            _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                    # Ersetze _create_client() durch die Erstellung eines neuen AsyncModbusTcpClient
                    self._client = AsyncModbusTcpClient(self._host, self._port)
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")

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
        
        # Restart fast updates if enabled
        if self.fast_enabled:
            await self.restart_fast_updates()

    async def restart_fast_updates(self) -> None:
        """Restart the fast update interval with current config."""
        if not self.fast_enabled:
            return
        
        # Stop existing fast updates
        if self._cancel_fast_update is not None:
            self._cancel_fast_update()
            self._cancel_fast_update = None
            _LOGGER.debug("Stopped old fast updates")
        
        # Start new fast updates
        await self.start_fast_updates()

    async def reconnect_client(self) -> bool:
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] reconnect_client called - Current reconnecting state: %s", self._reconnecting)

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
                        _LOGGER.warning("Error while closing old Modbus client: %s", e)
                self._client = AsyncModbusTcpClient(self._host, self._port)
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
        """Regular poll cycle with fixed interval."""
        start = time.monotonic()
        
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] Main coordinator update cycle started - Fixed interval: %ss", self._scan_interval)
        
        _LOGGER.info("Starting main coordinator update cycle")
        try:
            # Ensure client is connected before processing
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
                _LOGGER.info("[ADVANCED] Update cycle completed - Cache size: %d items", len(cache))
            
            return self.inverter_data
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            self._optimistic_overlay = None
            raise
        finally:
            elapsed = round(time.monotonic() - start, 3)
            if ADVANCED_LOGGING:
                _LOGGER.info("[ADVANCED] Total update cycle time: %ss", elapsed)

    def _get_pending_handlers(self) -> Dict[str, Callable]:
        """Collect all pending handlers with values."""
        handlers = self._setting_handler.get_handlers()
        pending = {}
        
        for attr_name in handlers.keys():
            if attr_name.startswith("_pending_"):
                if getattr(self, attr_name, None) is not None:
                    pending[attr_name] = handlers[attr_name]
        
        return pending

    async def _process_pending_settings(self) -> None:
        """Process all pending settings with optimized batch processing and priority system."""
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] _process_pending_settings started")
        
        _LOGGER.debug("Processing pending settings...")
        
        try:
            # Collect all pending attributes with their handlers
            pending = self._get_pending_handlers()
            
            # Check for charge pending settings
            charge_pending = [
                idx for idx, slot in enumerate(self._pending_charges, start=1)
                if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES)
            ]
            
            # Check for discharge pending settings
            discharge_pending = [
                idx for idx, slot in enumerate(self._pending_discharges, start=1)
                if any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES)
            ]
            
            if not pending and not charge_pending and not discharge_pending:
                _LOGGER.debug("No pending settings found to process")
                return
            
            if ADVANCED_LOGGING:
                _LOGGER.info("[ADVANCED] Found %d pending handler(s): %s", len(pending), list(pending.keys()))
            
            # Log pending settings for debugging
            if charge_pending:
                _LOGGER.info("[PENDING DEBUG] Found charge pending for indices: %s", charge_pending)
            
            if discharge_pending:
                _LOGGER.info(f"[PENDING DEBUG] Found discharge pending for indices: {discharge_pending}")
            
            results = []
            
            # 1. Process power state handlers first (highest priority)
            power_state_pending = {
                k: v for k, v in pending.items()
                if k in ("_pending_charging_state", "_pending_discharging_state")
            }
            
            if power_state_pending:
                _LOGGER.info(f"Processing {len(power_state_pending)} power state handlers")
                for attr_name, handler in power_state_pending.items():
                    try:
                        result = await handler()
                        results.append((attr_name, result))
                        if ADVANCED_LOGGING:
                            _LOGGER.debug(f"[ADVANCED] Power state handler '{attr_name}' completed")
                    except Exception as e:
                        _LOGGER.error(
                            "Error executing power state handler '%s': %s",
                            attr_name, e, exc_info=e
                        )
            
            # 2. Process charge and discharge slot handlers in parallel (medium priority)
            slot_tasks = []
            
            for charge_idx in charge_pending:
                slot_tasks.append(self._setting_handler.handle_charge_settings_by_index(charge_idx))
            
            for discharge_idx in discharge_pending:
                slot_tasks.append(self._setting_handler.handle_discharge_settings_by_index(discharge_idx))
            
            if slot_tasks:
                _LOGGER.info(f"Processing {len(slot_tasks)} slot handlers in parallel")
                slot_results = await asyncio.gather(*slot_tasks, return_exceptions=True)
                
                for i, result in enumerate(slot_results):
                    slot_type = "charge" if i < len(charge_pending) else "discharge"
                    idx = charge_pending[i] if i < len(charge_pending) else discharge_pending[i - len(charge_pending)]
                    results.append((f"{slot_type}{idx}", True if not isinstance(result, Exception) else False))
                    
                    if isinstance(result, Exception):
                        _LOGGER.error(
                            "Error processing slot handler '%s%d': %s",
                            slot_type, idx, result, exc_info=result
                        )
            
            # 3. Process simple handlers in parallel (lowest priority)
            simple_pending = {
                k: v for k, v in pending.items()
                if k not in power_state_pending
            }
            
            if simple_pending:
                _LOGGER.info(f"Processing {len(simple_pending)} simple handlers in parallel")
                simple_tasks = [handler() for handler in simple_pending.values()]
                simple_results = await asyncio.gather(*simple_tasks, return_exceptions=True)
                
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
            
            # 4. Summary
            successful = sum(1 for _, r in results if r is True)
            if ADVANCED_LOGGING and results:
                _LOGGER.info(
                    f"[ADVANCED] Pending processing complete: "
                    f"{successful}/{len(charge_pending) + len(discharge_pending) + len(pending)} successful"
                )
    
        except Exception as e:
            _LOGGER.warning("Pending processing failed, continuing to read phase: %s", e, exc_info=True)
        finally:
            self._invalidate_pending_cache()

    async def _run_reader_methods(self) -> Dict[str, Any]:
        """Parallel execution of readers in logical groups; builds cache."""
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] _run_reader_methods started - Client connected: %s", self._client.connected if self._client else 'No client')
        
        new_cache: Dict[str, Any] = {}
      
        
        # Load static inverter data only once (on first call)
        if self._inverter_static_data is None:
            try:
                _LOGGER.info("Loading static inverter data (first time only)...")
                self._inverter_static_data = await modbus_readers.read_modbus_inverter_data(
                    self._client, self._read_lock
                )
                if self._inverter_static_data:
                    _LOGGER.info(
                        "Static inverter data loaded successfully: SN=%s, Type=%s",
                        self._inverter_static_data.get("sn", "Unknown"),
                        self._inverter_static_data.get("devtype", "Unknown")
                    )
                else:
                    _LOGGER.warning("Static inverter data returned empty")
            except Exception as e:
                _LOGGER.error("Failed to load static inverter data: %s", e)
                self._inverter_static_data = {}
        
        # Always include static data in cache
        if self._inverter_static_data:
            new_cache.update(self._inverter_static_data)
        
        # Group readers by logical dependencies - readers in same group run in parallel
        reader_groups = [
            # Group 1: Critical real-time data
            [modbus_readers.read_modbus_realtime_data],
            
            # Group 2: Additional data part 1 (can run in parallel)
            [
                modbus_readers.read_additional_modbus_data_1_part_1,
                modbus_readers.read_additional_modbus_data_1_part_2,
            ],
            
            # Group 3: Additional data part 2 (can run in parallel)
            [
                modbus_readers.read_additional_modbus_data_2_part_1,
                modbus_readers.read_additional_modbus_data_2_part_2,
            ],
            
            # Group 4: Additional data part 3 & 4 (can run in parallel)
            [
                modbus_readers.read_additional_modbus_data_3,
                modbus_readers.read_additional_modbus_data_3_2,
                modbus_readers.read_additional_modbus_data_4,
            ],
            
            # Group 5: Device-specific data (can run in parallel)
            [
                modbus_readers.read_battery_data,
                modbus_readers.read_inverter_phase_data,
                modbus_readers.read_offgrid_output_data,
            ],
            
            # Group 6: Network and passive data (can run in parallel)
            [
                modbus_readers.read_side_net_data,
                modbus_readers.read_passive_battery_data,
                modbus_readers.read_meter_a_data,
            ],
            
            # Group 7: Charge/Discharge settings (can run in parallel)
            [
                modbus_readers.read_charge_data,
                modbus_readers.read_discharge_data,
            ],
        ]

        current_time = time.monotonic()
        total_readers = sum(len(group) for group in reader_groups)
        successful_count = 0
        
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] Executing %d readers in %d groups", total_readers, len(reader_groups))
        
        # Execute each group in sequence, but readers within group run in parallel
        for group_idx, group in enumerate(reader_groups, 1):
            group_start = time.monotonic()
            
            # Create tasks for all readers in this group
            tasks = [method(self._client, self._read_lock) for method in group]
            
            # Execute group in parallel with exception handling
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            group_duration = time.monotonic() - group_start
            
            # Process results from this group
            for method, result in zip(group, results):
                method_name = method.__name__
                
                if isinstance(result, ReconnectionNeededError):
                    _LOGGER.warning("%s required reconnection: %s", method_name, result)
                    try:
                        await self.reconnect_client()
                        # Retry once after reconnection
                        retry_result = await method(self._client, self._read_lock)
                        if retry_result:
                            new_cache.update(retry_result)
                            successful_count += 1
                    except Exception as retry_error:
                        _LOGGER.warning("Retry failed for %s: %s", method_name, retry_error)
                
                elif isinstance(result, Exception):
                    _LOGGER.warning("Reader %s failed: %s", method_name, result)
                
                elif isinstance(result, dict) and result:
                    # Check for locked values that should NOT be overwritten
                    if self._charging_state_lock_until and current_time < self._charging_state_lock_until:
                        if "charging_enabled" in result:
                            _LOGGER.info(
                                "[CACHE LOCK] Ignoring charging_enabled from %s "
                                "(locked until %.1fs)",
                                method_name,
                                self._charging_state_lock_until - current_time
                            )
                            result.pop("charging_enabled")
                    
                    if self._discharging_state_lock_until and current_time < self._discharging_state_lock_until:
                        if "discharging_enabled" in result:
                            _LOGGER.info(
                                "[CACHE LOCK] Ignoring discharging_enabled from %s "
                                "(locked until %.1fs)",
                                method_name,
                                self._discharging_state_lock_until - current_time
                            )
                            result.pop("discharging_enabled")
                    
                    new_cache.update(result)
                    successful_count += 1
            
            if ADVANCED_LOGGING:
                _LOGGER.debug(
                    f"[ADVANCED] Group {group_idx}/{len(reader_groups)} completed in {group_duration:.2f}s "
                    f"({len(group)} readers)"
                )
        
        if ADVANCED_LOGGING:
            _LOGGER.info(
                f"[ADVANCED] All reader groups completed: {successful_count}/{total_readers} successful"
            )
        
        # Clear expired locks
        if self._charging_state_lock_until and current_time >= self._charging_state_lock_until:
            self._charging_state_lock_until = None
        
        if self._discharging_state_lock_until and current_time >= self._discharging_state_lock_until:
            self._discharging_state_lock_until = None
        
        # Preserve locked values if still active
        if self._charging_state_lock_until and current_time < self._charging_state_lock_until:
            if "charging_enabled" in self.inverter_data:
                new_cache["charging_enabled"] = self.inverter_data["charging_enabled"]
                _LOGGER.info("[CACHE LOCK] Preserving charging_enabled = %s", new_cache['charging_enabled'])
        
        if self._discharging_state_lock_until and current_time < self._discharging_state_lock_until:
            if "discharging_enabled" in self.inverter_data:
                new_cache["discharging_enabled"] = self.inverter_data["discharging_enabled"]
                _LOGGER.info("[CACHE LOCK] Preserving discharging_enabled = %s", new_cache['discharging_enabled'])
        
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
        # Cancel fast updates
        if self._cancel_fast_update is not None:
            self._cancel_fast_update()
            self._cancel_fast_update = None
            _LOGGER.debug("Fast update interval cancelled")
        
        # Clear fast listeners
        self._fast_listeners.clear()

        # Sicherstellen, dass der Client immer geschlossen wird
        client_to_close = self._client
        self._client = None  # Verweis sofort entfernen
        if client_to_close:
            try:
                await client_to_close.close()
                _LOGGER.debug("Modbus client connection closed")
            except Exception as e:
                _LOGGER.warning("Error closing Modbus client: %s", e)
        
        _LOGGER.debug("Modbus client cleaned up")

    # --- Helper functions ---
    def _has_pending(self) -> bool:
        """Optimized check for pending changes with early exit strategy."""
        if self._pending_cache_valid:
            return self._pending_cache
        
        # Check simple pending attributes (early exit on first match)
        has_pending = any(
            getattr(self, f"_pending_{attr_name}", None) is not None
            for attr_name in SIMPLE_REGISTER_MAP
        )
        
        # Check time_enable attributes
        if not has_pending:
            has_pending = (
                self._pending_charge_time_enable is not None or
                self._pending_discharge_time_enable is not None
            )
        
        # Check power state
        if not has_pending:
            has_pending = (
                self._pending_charging_state is not None or
                self._pending_discharging_state is not None
            )
        
        # Check charge and discharge settings (combined for efficiency)
        if not has_pending:
            has_pending = any(
                any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES)
                for slot in (self._pending_charges + self._pending_discharges)
            )
        
        # Cache the result
        self._pending_cache = has_pending
        self._pending_cache_valid = True
        return has_pending
    
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

            overlay = dict(base)  # Erstelle eine Kopie der Basisdaten
            if chg is not None:
                overlay["charging_enabled"] = 1 if chg else 0
            if dchg is not None:
                overlay["discharging_enabled"] = 1 if dchg else 0
            overlay["AppMode"] = app_mode

            self._optimistic_overlay = overlay
        except Exception as e:
            _LOGGER.debug("Optimistic overlay skipped: %s", e)