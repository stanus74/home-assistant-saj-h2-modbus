from __future__ import annotations
"""SAJ Modbus Hub with optimized processing and fixed interval system."""
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
from datetime import timedelta, datetime

from homeassistant.core import HomeAssistant, callback, CoreState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_FAST_ENABLED
from . import modbus_readers
from .modbus_utils import (
    try_read_registers,
    try_write_registers,
    ReconnectionNeededError,
)
from .charge_control import (
    ChargeSettingHandler,
    PENDING_FIELDS,
)
from .services import ModbusConnectionManager, MqttPublisher

_LOGGER = logging.getLogger(__name__)

# Config Defaults
FAST_POLL_DEFAULT = False
ADVANCED_LOGGING = False
CONF_ULTRA_FAST_ENABLED = "ultra_fast_enabled"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_PUBLISH_ALL = "mqtt_publish_all"
CONF_USE_HA_MQTT = "use_ha_mqtt"

# Constants
DEFAULT_MODBUS_PORT = 502
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC_PREFIX = "saj"
FAST_UPDATE_INTERVAL = 10
ULTRA_FAST_UPDATE_INTERVAL = 1
STARTUP_DELAY_RUNNING = 1
STARTUP_DELAY_MQTT = 30

FAST_POLL_SENSORS = {
    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower", "directionPV", "directionBattery",
    "directionGrid", "directionOutput", "CT_GridPowerWatt",
    "CT_GridPowerVA", "CT_PVPowerWatt", "CT_PVPowerVA", "totalgridPowerVA",
    "TotalInvPowerVA", "BackupTotalLoadPowerWatt", "BackupTotalLoadPowerVA",
}

CRITICAL_READER_GROUPS = {1, 2}


class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

        # Config extraction - Connection
        host = self._get_config_value(config_entry, CONF_HOST)
        port = self._get_config_value(config_entry, CONF_PORT, DEFAULT_MODBUS_PORT)
        scan_interval = self._get_config_value(config_entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.title,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )

        # Robust config loading (options priority, then data)
        self.ultra_fast_enabled = self._get_config_value(config_entry, CONF_ULTRA_FAST_ENABLED, False)
        self.fast_enabled = self._get_config_value(config_entry, CONF_FAST_ENABLED, FAST_POLL_DEFAULT)

        # Config extraction - MQTT (Fallback logic options -> data -> default)
        mqtt_host = self._get_config_value(config_entry, "mqtt_host", "")
        mqtt_port = self._get_config_value(config_entry, "mqtt_port", DEFAULT_MQTT_PORT)
        mqtt_user = self._get_config_value(config_entry, "mqtt_user", "")
        mqtt_password = self._get_config_value(config_entry, "mqtt_password", "")
        mqtt_topic_prefix = self._get_config_value(config_entry, CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
        mqtt_publish_all = self._get_config_value(config_entry, CONF_MQTT_PUBLISH_ALL, False)
        use_ha_mqtt = self._get_config_value(config_entry, CONF_USE_HA_MQTT, False)

        _LOGGER.info(
            "SAJ Hub Initialized. Host: %s, Fast: %s, Ultra: %s, MQTT Prefix: '%s', MQTT Host: '%s'", 
            host, self.fast_enabled, self.ultra_fast_enabled, mqtt_topic_prefix, mqtt_host
        )

        # --- SERVICES ---
        self.connection = ModbusConnectionManager(hass, host, port)
        self.mqtt = MqttPublisher(
            hass, 
            mqtt_host, 
            mqtt_port, 
            mqtt_user, 
            mqtt_password, 
            mqtt_topic_prefix, 
            mqtt_publish_all, 
            self.ultra_fast_enabled,
            use_ha_mqtt,
        )
        
        # Log which strategy was picked
        _LOGGER.info("SAJ MQTT Strategy initialized: %s", self.mqtt.strategy)

        # State & Locks
        # PERFORMANCE OPTIMIZATION: Separate locks for different polling intervals
        # This reduces lock contention between ultra fast (1s), fast (10s), and slow (60s) loops
        self._ultra_fast_lock = asyncio.Lock()  # For 1s ultra fast polling
        self._fast_lock = asyncio.Lock()        # For 10s fast polling
        self._slow_lock = asyncio.Lock()        # For 60s slow polling

        # Merge locks for shared state/mask registers
        self._merge_locks: Dict[int, asyncio.Lock] = {
            0x3604: asyncio.Lock(),  # charging state + charge_time_enable mask
            0x3605: asyncio.Lock(),  # discharging state + discharge_time_enable mask
        }
        
        # DEDICATED WRITE LOCK: Write operations have priority over read operations
        # This prevents write operations from waiting for read operations to complete
        self._write_lock = asyncio.Lock()
        self._write_in_progress = False  # Flag for active write operation
        
        self.inverter_data: Dict[str, Any] = {}
        self.updating_settings = False
        
        # Fast Poll State
        self._fast_unsub = None
        self._cancel_fast_update = None
        self._cancel_ultra_fast_update = None
        self._pending_fast_start_cancel: Optional[Callable] = None
        self._pending_ultra_fast_start_cancel: Optional[Callable] = None
        self._fast_listeners: List[Callable] = []
        self._fast_debug_log_next = 0.0
        self._fast_poll_sensor_keys = FAST_POLL_SENSORS

        self._inverter_static_data: Optional[Dict[str, Any]] = None
        self._warned_missing_states: bool = False

        # Charge Control
        self._pending_charging_state = None
        self._pending_discharging_state = None
        self._pending_passive_mode_state = None
        self._setting_handler = ChargeSettingHandler(self)
        self.use_ha_mqtt = use_ha_mqtt
        
        self._init_setters()

    def _get_config_value(self, config_entry: ConfigEntry, key: str, default: Any = None) -> Any:
        """Get config value with fallback: options -> data -> default."""
        return config_entry.options.get(key, config_entry.data.get(key, default))

    def _init_setters(self) -> None:
        """Initializes dynamic setters."""
        for name, attr_path in PENDING_FIELDS:
            def make_setter(path: str):
                async def setter(value: Any) -> None:
                    self._setting_handler.set_pending(path, value)
                return setter
            setattr(self, f"set_{name}", make_setter(attr_path))

        # Explicit setters for power states
        self.set_charging = self._set_charging_state
        self.set_discharging = self._set_discharging_state
        self.set_passive_mode = self._set_passive_mode

    def _set_power_state(self, value: bool | int | None, state_attr: str, handler_method: str) -> None:
        """Set a power state with pending flag and trigger processing."""
        setattr(self, f"_pending_{state_attr}", value)
        self.async_set_updated_data(self.inverter_data)
        getattr(self._setting_handler, handler_method)(value)
        self.hass.async_create_task(self.process_pending_now())

    async def _set_charging_state(self, value: bool) -> None:
        self._set_power_state(value, "charging_state", "set_charging_state")

    async def _set_discharging_state(self, value: bool) -> None:
        self._set_power_state(value, "discharging_state", "set_discharging_state")

    async def _set_passive_mode(self, value: Optional[int]) -> None:
        self._set_power_state(value, "passive_mode_state", "set_passive_mode")

    async def process_pending_now(self) -> None:
        """Immediately process pending settings."""
        try:
            await self.connection.get_client()
            await self._setting_handler.process_pending()
        except Exception as e:
            _LOGGER.error("Immediate pending processing failed: %s", e)

    # --- COORDINATOR METHODS ---

    async def _async_update_data(self) -> Dict[str, Any]:
        """Regular poll cycle (slow)."""
        try:
            client = await self.connection.get_client() # Ensure connected

            await self._setting_handler.process_pending()

            cache = await self._run_reader_methods(client)
            self.inverter_data = cache

            if self.mqtt.publish_all and self.inverter_data:
                await self.mqtt.publish_data(self.inverter_data)
            
            return self.inverter_data
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            raise

    def _process_reader_result(self, result: Any) -> bool:
        """Process a reader result and update cache if valid. Returns True if reconnection needed."""
        if isinstance(result, dict):
            return False
        elif isinstance(result, ReconnectionNeededError):
            return True
        elif isinstance(result, Exception):
            _LOGGER.warning("Reader error: %s", result)
        return False

    async def _run_reader_methods(self, client: Any) -> Dict[str, Any]:
        """Executes all readers using the provided client."""
        new_cache: Dict[str, Any] = {}
        
        # Load Static Data once
        if self._inverter_static_data is None:
            try:
                self._inverter_static_data = await modbus_readers.read_modbus_inverter_data(
                    client, self._slow_lock  # Use slow lock for static data
                )
            except Exception as e:
                _LOGGER.error("Failed to load static data: %s", e)
                self._inverter_static_data = {}
        
        if self._inverter_static_data:
            new_cache.update(self._inverter_static_data)

        # Reader groups (Same definition as original)
        reader_groups = [
            [modbus_readers.read_modbus_realtime_data],
            [modbus_readers.read_additional_modbus_data_1_part_1, modbus_readers.read_additional_modbus_data_1_part_2],
            [modbus_readers.read_additional_modbus_data_2_part_1, modbus_readers.read_additional_modbus_data_2_part_2],
            [modbus_readers.read_additional_modbus_data_3, modbus_readers.read_additional_modbus_data_3_2, modbus_readers.read_additional_modbus_data_4],
            [modbus_readers.read_battery_data, modbus_readers.read_inverter_phase_data, modbus_readers.read_offgrid_output_data],
            [modbus_readers.read_side_net_data, modbus_readers.read_passive_battery_data, modbus_readers.read_meter_a_data],
            [modbus_readers.read_charge_data, modbus_readers.read_discharge_data],
        ]

        for group_idx, group in enumerate(reader_groups, 1):
            if group_idx in CRITICAL_READER_GROUPS:
                # Sequential - use slow lock for critical groups
                for method in group:
                    try:
                        res = await method(client, self._slow_lock)
                        if isinstance(res, dict): new_cache.update(res)
                    except Exception as e:
                         _LOGGER.warning("Reader error: %s", e)
            else:
                # Parallel - use slow lock for non-critical groups
                tasks = [method(client, self._slow_lock) for method in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict): new_cache.update(res)
                    elif self._process_reader_result(res):
                         await self.connection.reconnect()

        return new_cache

    # --- FAST POLLING ---

    def _get_startup_delay(self) -> int:
        """Get startup delay based on HA state and MQTT availability."""
        mqtt_in_config = "mqtt" in self.hass.config.components
        is_running = self.hass.state == CoreState.running if hasattr(CoreState, "running") else False
        return STARTUP_DELAY_RUNNING if is_running else (STARTUP_DELAY_MQTT if mqtt_in_config else STARTUP_DELAY_RUNNING)

    @callback
    def _start_update_loop(self, interval: int, cancel_attr: str, ultra: bool = False) -> None:
        """Start an update loop with the given interval."""
        if cancel_attr == "_cancel_fast_update":
            self._pending_fast_start_cancel = None
        else:
            self._pending_ultra_fast_start_cancel = None

        if getattr(self, cancel_attr):
            return

        _LOGGER.info("Starting fast update loop (%ds)", interval)
        async def runner(now):
            await self._async_update_fast(now, ultra=ultra)

        setattr(self, cancel_attr, async_track_time_interval(self.hass, runner, timedelta(seconds=interval)))

    @callback
    def _schedule_update_loop(self, interval: int, cancel_attr: str, ultra: bool = False) -> None:
        """Schedule an update loop to start after startup delay."""
        startup_delay = self._get_startup_delay()
        pending_attr = (
            "_pending_ultra_fast_start_cancel"
            if cancel_attr == "_cancel_ultra_fast_update"
            else "_pending_fast_start_cancel"
        )

        # Replace any existing pending handle for the same loop
        pending_handle = getattr(self, pending_attr, None)
        if pending_handle:
            pending_handle()

        setattr(
            self,
            pending_attr,
            async_call_later(
                self.hass,
                startup_delay,
                lambda _: self._start_update_loop(interval, cancel_attr, ultra),
            ),
        )

    async def start_fast_updates(self) -> None:
        """Start fast update loops based on configuration."""
        # Start the 10s Fast Loop if enabled (independent of Ultra)
        if self.fast_enabled:
            if self._cancel_fast_update:
                self._cancel_fast_update()
                self._cancel_fast_update = None
            if self._pending_fast_start_cancel:
                self._pending_fast_start_cancel()
                self._pending_fast_start_cancel = None

            self._schedule_update_loop(FAST_UPDATE_INTERVAL, "_cancel_fast_update", False)

        # Start the 1s Ultra Loop independently if enabled
        if self.ultra_fast_enabled:
            if self._cancel_ultra_fast_update:
                self._cancel_ultra_fast_update()
                self._cancel_ultra_fast_update = None
            if self._pending_ultra_fast_start_cancel:
                self._pending_ultra_fast_start_cancel()
                self._pending_ultra_fast_start_cancel = None

            self._schedule_update_loop(ULTRA_FAST_UPDATE_INTERVAL, "_cancel_ultra_fast_update", True)

    async def _async_update_fast(self, now=None, ultra: bool = False) -> None:
        """
        Perform fast update of sensor data with performance optimizations.
        
        PERFORMANCE OPTIMIZATIONS:
        1. Separate locks for ultra fast vs fast modes - reduces lock contention
        2. Skip ultra-fast update if write operation is in progress
        """
        if not self.fast_enabled and not ultra:
            return
        
        # Skip ultra-fast update if write operation is in progress
        if ultra and self._write_in_progress:
            _LOGGER.debug("Skipping ultra-fast update - write operation in progress")
            return
        
        try:
            client = await self.connection.get_client()
            
            # PERFORMANCE OPTIMIZATION: Use dedicated lock based on polling mode
            # Ultra fast (1s) uses its own lock to avoid contention with fast (10s) and slow (60s)
            lock = self._ultra_fast_lock if ultra else self._fast_lock
            
            # FAIL-FAST RETRY LOGIC FOR ULTRA-FAST POLL
            # If a read fails, immediately retry once. If the retry also fails, skip the update cycle.
            try:
                result = await modbus_readers.read_additional_modbus_data_1_part_2(client, lock)
            except Exception as e:
                _LOGGER.debug("Ultra-fast poll failed, attempting one retry: %s", e)
                try:
                    # Immediate retry once
                    result = await modbus_readers.read_additional_modbus_data_1_part_2(client, lock)
                except Exception as retry_e:
                    # If retry also fails, skip the update cycle
                    _LOGGER.debug("Ultra-fast poll retry failed, skipping update cycle: %s", retry_e)
                    return
            
            if result:
                fast_data = {k: v for k, v in result.items() if k in self._fast_poll_sensor_keys}
                
                if fast_data:
                    # Update inverter data with all fast data
                    self.inverter_data.update(fast_data)
                    
                    await self.mqtt.publish_data(fast_data)

                    # Only the 10s loop should push to HA entities to avoid DB spam
                    if not ultra:
                        for listener in self._fast_listeners:
                            listener()

        except ReconnectionNeededError:
            await self.connection.reconnect()
        except Exception as e:
            _LOGGER.warning("Fast update failed: %s", e)

    @callback
    def async_add_fast_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        self._fast_listeners.append(update_callback)
        @callback
        def remove_listener() -> None:
            if update_callback in self._fast_listeners:
                self._fast_listeners.remove(update_callback)
        return remove_listener

    # --- CONFIG & LIFECYCLE ---

    async def update_connection_settings(
        self,
        host: str,
        port: int,
        scan_interval: int,
        fast_enabled: bool,
        ultra_fast_enabled: bool,
        mqtt_host: str = "",
        mqtt_port: int = 1883,
        mqtt_user: str = "",
        mqtt_password: str = "",
        mqtt_topic_prefix: Optional[str] = None,
        mqtt_publish_all: bool = False,
        use_ha_mqtt: bool = False,
    ) -> None:
        """Update connection settings. Full signature restored to support positional arguments."""
        if self.updating_settings: return
        self.updating_settings = True
        try:
            prev_strategy = self.mqtt.strategy
            # Update Services
            self.connection.update_config(host, port)
            
            # FAILSAFE: If prefix argument is None (because __init__.py didn't pass it),
            # retrieve it from the ConfigEntry options/data directly.
            if mqtt_topic_prefix is None:
                mqtt_topic_prefix = self._config_entry.options.get(CONF_MQTT_TOPIC_PREFIX, self._config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "saj"))
            
            # Update MQTT: pass explicit values from args (or recovered value)
            self.mqtt.update_config(
                mqtt_host, 
                mqtt_port,
                mqtt_user, 
                mqtt_password,
                mqtt_topic_prefix, 
                mqtt_publish_all,
                ultra_fast_enabled,
                use_ha_mqtt,
            )
            
            # Update Hub State
            self.update_interval = timedelta(seconds=scan_interval)
            
            self.fast_enabled = fast_enabled
            self.ultra_fast_enabled = ultra_fast_enabled
            self.use_ha_mqtt = use_ha_mqtt

            # Restart Fast Loop (Stop everything first, then restart based on flags)
            self._cleanup_fast_update_callbacks()

            # Start loops independently based on flags
            if self.fast_enabled or self.ultra_fast_enabled:
                await self.start_fast_updates()

        finally:
            self.updating_settings = False

    def _cleanup_fast_update_callbacks(self) -> None:
        """Clean up all fast update callbacks."""
        if self._cancel_fast_update:
            self._cancel_fast_update()
        if self._cancel_ultra_fast_update:
            self._cancel_ultra_fast_update()
        if self._pending_fast_start_cancel:
            self._pending_fast_start_cancel()
        if self._pending_ultra_fast_start_cancel:
            self._pending_ultra_fast_start_cancel()
        
        # Clear references completely
        self._cancel_fast_update = None
        self._cancel_ultra_fast_update = None
        self._pending_fast_start_cancel = None
        self._pending_ultra_fast_start_cancel = None

    async def async_unload_entry(self) -> None:
        self._cleanup_fast_update_callbacks()
        self.mqtt.stop()
        try:
            await self._setting_handler.shutdown()
        except Exception as e:
            _LOGGER.debug("Error during setting handler shutdown: %s", e)
        await self.connection.close()
        self._fast_listeners.clear()

    # --- HELPERS ---
    
    async def _write_register(self, address: int, value: int) -> bool:
        """
        Helper for charge_control.py to write via connection service.
        
        Uses dedicated write lock with priority over read operations.
        """
        # Do not acquire the lock twice: try_write_registers already uses it.
        self._write_in_progress = True
        try:
            client = await self.connection.get_client()
            return await try_write_registers(
                client, self._write_lock, 1, address, value
            )
        finally:
            self._write_in_progress = False

    async def _read_registers(self, address: int, count: int) -> List[int]:
        """
        Helper for charge_control.py to read via connection service.
        
        Waits for any pending write operation before reading.
        """
        # Wait for any pending write operation
        while self._write_in_progress:
            await asyncio.sleep(0.01)
        
        client = await self.connection.get_client()
        return await try_read_registers(
            client, self._slow_lock, 1, address, count
        )

    async def merge_write_register(
        self,
        address: int,
        modifier: Callable[[int], int],
        label: str = "merge write",
    ) -> tuple[bool, int]:
        """Read-modify-write with per-register lock to preserve shared bits."""
        lock = self._merge_locks.get(address, self._write_lock)
        async with lock:
            current_regs = await self._read_registers(address, 1)
            if not current_regs:
                return False, 0
            current = current_regs[0]
            new_val = modifier(current)
            if new_val == current:
                return True, current
            ok = await self._write_register(address, new_val)
            if ok:
                _LOGGER.debug("%s: wrote merged value %s to 0x%04x", label, new_val, address)
                return True, new_val
            return False, current
