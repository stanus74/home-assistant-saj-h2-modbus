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
from pymodbus.client import ModbusTcpClient
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
)

_LOGGER = logging.getLogger(__name__)

FAST_POLL_DEFAULT = False
ADVANCED_LOGGING = False

# Define which sensor keys should be updated in fast polling (10s interval)
FAST_POLL_SENSORS = {
    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower", "directionPV", "directionBattery",
    "directionGrid", "directionOutput", "CT_GridPowerWatt",
    "CT_GridPowerVA", "CT_PVPowerWatt", "CT_PVPowerVA", "totalgridPowerVA",
    "TotalInvPowerVA", "BackupTotalLoadPowerWatt", "BackupTotalLoadPowerVA",
}


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
 
        set_modbus_config(self._host, self._port, hass)
        self._read_lock = asyncio.Lock()
        self.inverter_data: Dict[str, Any] = {}
        self._client: Optional[ModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        self.fast_enabled = FAST_POLL_DEFAULT  # Initialize fast_enabled attribute
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

        self._setting_handler = ChargeSettingHandler(self)
        
        # Generate setters that delegate to the handler
        for name, attr_path in PENDING_FIELDS:
            # Create a closure to capture attr_path
            def make_setter(path):
                # Must be async because entities await this method
                async def setter(value):
                    self._setting_handler.set_pending(path, value)
                return setter
            
            setattr(self, f"set_{name}", make_setter(attr_path))

        # Define explicit setters for power states
        async def _set_charging_state(value: bool) -> None:
            self._setting_handler.set_charging_state(value)
            _LOGGER.info("Set pending charging state to: %s", value)
            self.hass.async_create_task(self.process_pending_now())

        async def _set_discharging_state(value: bool) -> None:
            self._setting_handler.set_discharging_state(value)
            _LOGGER.info("Set pending discharging state to: %s", value)
            self.hass.async_create_task(self.process_pending_now())

        self.set_charging = _set_charging_state
        self.set_discharging = _set_discharging_state

    async def start_main_coordinator(self) -> None:
        """Start the main coordinator scheduling."""
        _LOGGER.info("Starting main coordinator scheduling...")
        # The DataUpdateCoordinator handles the scheduling, so we just log here.
        # This method is kept for compatibility but does nothing.
        pass

    async def process_pending_now(self) -> None:
        """Immediately process pending settings without waiting for next update cycle."""
        _LOGGER.debug("Immediately processing pending settings...")
        try:
            await self._ensure_connected_client()
            # Delegated to handler
            await self._setting_handler.process_pending()
            _LOGGER.debug("Immediate pending processing completed")
        except Exception as e:
            _LOGGER.error("Immediate pending processing failed: %s", e)

    async def _ensure_connected_client(self) -> ModbusTcpClient:
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

    async def update_connection_settings(self, host: str, port: int, scan_interval: int, fast_enabled: bool) -> None:
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
                set_modbus_config(self._host, self._port, self.hass)
                self._scan_interval = scan_interval
                self.update_interval = timedelta(seconds=scan_interval)
                
                # Update fast_enabled
                self.fast_enabled = fast_enabled

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    if self._client:
                        try:
                            # Use the awaitable close wrapper from SAJModbusClient
                            await self._client.close()
                        except Exception as e:
                            _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                    # Reset client to None so it gets recreated by connect_if_needed with new settings
                    self._client = None
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")

                if ADVANCED_LOGGING:
                    _LOGGER.debug(
                        "Updated configuration - Host: %s, Port: %d, Scan Interval: %d, Fast Enabled: %s",
                        self._host,
                        self._port,
                        scan_interval,
                        fast_enabled
                    )
            except Exception as e:
                _LOGGER.error("Failed to update connection settings: %s", e)
                raise
            finally:
                self.updating_settings = False
        
        # Restart fast updates if enabled, or stop if disabled
        if self.fast_enabled:
            await self.restart_fast_updates()
        elif self._cancel_fast_update is not None:
            self._cancel_fast_update()
            self._cancel_fast_update = None
            _LOGGER.info("Fast updates stopped")

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
                
                # Set to None to force recreation in connect_if_needed
                self._client = None
                self._client = await connect_if_needed(self._client, self._host, self._port)

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
            
            # Delegated to handler
            await self._setting_handler.process_pending()

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
                    # Delegated check to handler
                    if self._setting_handler.is_charging_locked(current_time):
                        if "charging_enabled" in result:
                            _LOGGER.info("[CACHE LOCK] Ignoring charging_enabled (locked)")
                            result.pop("charging_enabled")
                    
                    if self._setting_handler.is_discharging_locked(current_time):
                        if "discharging_enabled" in result:
                            _LOGGER.info("[CACHE LOCK] Ignoring discharging_enabled (locked)")
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
        self._setting_handler.cleanup_locks(current_time)
        
        # Preserve locked values if still active - Delegated logic
        if self._setting_handler.is_charging_locked(current_time):
            if "charging_enabled" in self.inverter_data:
                new_cache["charging_enabled"] = self.inverter_data["charging_enabled"]
                _LOGGER.info("[CACHE LOCK] Preserving charging_enabled = %s", new_cache['charging_enabled'])
        
        if self._setting_handler.is_discharging_locked(current_time):
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
        if client_to_close:
            self._client = None  # Verweis sofort entfernen
            try:
                await client_to_close.close()
                _LOGGER.debug("Modbus client connection closed")
            except Exception as e:
                _LOGGER.warning("Error closing Modbus client: %s", e)
        else:
            _LOGGER.debug("Modbus client was already None, no need to close.")
        
        _LOGGER.debug("Modbus client cleaned up")

    # --- Helper functions ---
    def _has_pending(self) -> bool:
        """Delegated to handler."""
        return self._setting_handler.has_pending()
    
    def _invalidate_pending_cache(self) -> None:
        """Delegated to handler."""
        self._setting_handler.invalidate_cache()

    def _apply_optimistic_overlay(self) -> None:
        """Delegated to handler."""
        try:
            overlay = self._setting_handler.get_optimistic_overlay(self.inverter_data)
            if overlay:
                self._optimistic_overlay = overlay
        except Exception as e:
            _LOGGER.debug("Optimistic overlay skipped: %s", e)