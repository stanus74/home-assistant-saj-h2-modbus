from __future__ import annotations
"""SAJ Modbus Hub with optimized processing and fixed interval system."""
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
from datetime import timedelta

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
        self._optimistic_push_enabled: bool = True
        self._optimistic_overlay: dict[str, Any] | None = None
        self._config_entry = config_entry

        # Config extraction - Connection
        host = config_entry.options.get(CONF_HOST, config_entry.data.get(CONF_HOST))
        port = config_entry.options.get(CONF_PORT, config_entry.data.get(CONF_PORT, 502))
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, config_entry.data.get(CONF_SCAN_INTERVAL, 60))

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.title,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )

        self.fast_enabled = config_entry.options.get(CONF_FAST_ENABLED, FAST_POLL_DEFAULT)
        self.ultra_fast_enabled = config_entry.options.get(CONF_ULTRA_FAST_ENABLED, False)
        if self.ultra_fast_enabled:
            self.fast_enabled = True

        # Config extraction - MQTT (Fallback logic options -> data -> default)
        mqtt_host = config_entry.options.get("mqtt_host", config_entry.data.get("mqtt_host", ""))
        mqtt_port = config_entry.options.get("mqtt_port", config_entry.data.get("mqtt_port", 1883))
        mqtt_user = config_entry.options.get("mqtt_user", config_entry.data.get("mqtt_user", ""))
        mqtt_password = config_entry.options.get("mqtt_password", config_entry.data.get("mqtt_password", ""))
        mqtt_topic_prefix = config_entry.options.get(CONF_MQTT_TOPIC_PREFIX, config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "saj"))
        mqtt_publish_all = config_entry.options.get(CONF_MQTT_PUBLISH_ALL, config_entry.data.get(CONF_MQTT_PUBLISH_ALL, False))

        _LOGGER.info(
            "SAJ Hub Initialized. Host: %s, Fast: %s, MQTT Prefix: '%s', MQTT Host: '%s'", 
            host, self.fast_enabled, mqtt_topic_prefix, mqtt_host
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
            self.ultra_fast_enabled
        )
        
        # Log which strategy was picked
        _LOGGER.info("SAJ MQTT Strategy initialized: %s", self.mqtt.strategy)

        # State & Locks
        self._read_lock = asyncio.Lock() # Lock for read operations specifically
        self.inverter_data: Dict[str, Any] = {}
        self.updating_settings = False
        
        # Fast Poll State
        self._fast_unsub = None
        self._cancel_fast_update = None
        self._pending_fast_start_cancel: Optional[Callable] = None
        self._fast_listeners: List[Callable] = []
        self._fast_debug_log_next = 0.0

        self._inverter_static_data: Optional[Dict[str, Any]] = None
        self._warned_missing_states: bool = False

        # Charge Control
        self._pending_charging_state = None
        self._pending_discharging_state = None
        self._pending_passive_mode_state = None
        self._setting_handler = ChargeSettingHandler(self)
        
        self._init_setters()

    def _init_setters(self):
        """Initializes dynamic setters."""
        for name, attr_path in PENDING_FIELDS:
            def make_setter(path):
                async def setter(value):
                    self._setting_handler.set_pending(path, value)
                return setter
            setattr(self, f"set_{name}", make_setter(attr_path))

        # Explicit setters for power states
        self.set_charging = self._set_charging_state
        self.set_discharging = self._set_discharging_state
        self.set_passive_mode = self._set_passive_mode

    async def _set_charging_state(self, value: bool) -> None:
        self._pending_charging_state = value
        self.async_set_updated_data(self.inverter_data)
        self._setting_handler.set_charging_state(value)
        self.hass.async_create_task(self.process_pending_now())

    async def _set_discharging_state(self, value: bool) -> None:
        self._pending_discharging_state = value
        self.async_set_updated_data(self.inverter_data)
        self._setting_handler.set_discharging_state(value)
        self.hass.async_create_task(self.process_pending_now())

    async def _set_passive_mode(self, value: Optional[int]) -> None:
        self._pending_passive_mode_state = value
        self.async_set_updated_data(self.inverter_data)
        self._setting_handler.set_passive_mode(value)
        self.hass.async_create_task(self.process_pending_now())

    async def process_pending_now(self) -> None:
        """Immediately process pending settings."""
        try:
            await self.connection.get_client()
            await self._setting_handler.process_pending()
        except Exception as e:
            _LOGGER.error("Immediate pending processing failed: %s", e)

    # --- COORDINATOR METHODS ---

    async def start_main_coordinator(self) -> None:
        """Legacy compatibility."""
        _LOGGER.debug("start_main_coordinator called")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Regular poll cycle (slow)."""
        try:
            client = await self.connection.get_client() # Ensure connected

            if self._optimistic_push_enabled and self._setting_handler.has_pending():
                self._apply_optimistic_overlay()
                if self._optimistic_overlay:
                    self.async_set_updated_data(self._optimistic_overlay)

            await self._setting_handler.process_pending()

            cache = await self._run_reader_methods(client)
            self._optimistic_overlay = None
            self.inverter_data = cache

            if self.mqtt.publish_all and self.inverter_data:
                await self.mqtt.publish_data(self.inverter_data)
            
            return self.inverter_data
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            self._optimistic_overlay = None
            raise

    async def _run_reader_methods(self, client) -> Dict[str, Any]:
        """Executes all readers using the provided client."""
        new_cache: Dict[str, Any] = {}
        
        # Load Static Data once
        if self._inverter_static_data is None:
            try:
                self._inverter_static_data = await modbus_readers.read_modbus_inverter_data(
                    client, self._read_lock
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
                # Sequential
                for method in group:
                    try:
                        res = await method(client, self._read_lock)
                        if isinstance(res, dict): new_cache.update(res)
                    except Exception as e:
                         _LOGGER.warning("Reader error: %s", e)
            else:
                # Parallel
                tasks = [method(client, self._read_lock) for method in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict): new_cache.update(res)
                    elif isinstance(res, ReconnectionNeededError):
                         await self.connection.reconnect()
                    elif isinstance(res, Exception):
                         _LOGGER.warning("Reader error: %s", res)

        return new_cache

    # --- FAST POLLING ---

    async def start_fast_updates(self) -> None:
        if not self.fast_enabled or self._cancel_fast_update:
            return

        interval = 1 if self.ultra_fast_enabled else 10
        mqtt_in_config = "mqtt" in self.hass.config.components
        
        # Smart Delay Logic
        is_running = self.hass.state == CoreState.running if hasattr(CoreState, "running") else False
        startup_delay = 1 if is_running else (30 if mqtt_in_config else 1)

        @callback
        def _start_loop(_):
            self._pending_fast_start_cancel = None
            if self._cancel_fast_update: return
            
            _LOGGER.info(f"Starting fast update loop ({interval}s)")
            self._cancel_fast_update = async_track_time_interval(
                self.hass, self._async_update_fast, timedelta(seconds=interval)
            )

        self._pending_fast_start_cancel = async_call_later(self.hass, startup_delay, _start_loop)

    async def _async_update_fast(self, now=None) -> None:
        if not self.fast_enabled: return
        
        try:
            client = await self.connection.get_client()
            result = await modbus_readers.read_additional_modbus_data_1_part_2(client, self._read_lock)
            
            if result:
                fast_data = {k: v for k, v in result.items() if k in FAST_POLL_SENSORS}
                if fast_data:
                    self.inverter_data.update(result)
                    await self.mqtt.publish_data(fast_data)

                    # Update HA only in normal fast mode, skip in Ultra Fast to save DB
                    if not self.ultra_fast_enabled:
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
    ) -> None:
        """Update connection settings. Full signature restored to support positional arguments."""
        if self.updating_settings: return
        self.updating_settings = True
        try:
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
                ultra_fast_enabled
            )
            
            _LOGGER.info("SAJ MQTT Strategy updated to: %s", self.mqtt.strategy)
            
            # Update Hub State
            self.update_interval = timedelta(seconds=scan_interval)
            self.fast_enabled = fast_enabled or ultra_fast_enabled
            self.ultra_fast_enabled = ultra_fast_enabled

            # Restart Fast Loop
            if self._cancel_fast_update:
                self._cancel_fast_update()
                self._cancel_fast_update = None
            if self._pending_fast_start_cancel:
                self._pending_fast_start_cancel()
                self._pending_fast_start_cancel = None
            
            if self.fast_enabled:
                await self.start_fast_updates()

        finally:
            self.updating_settings = False

    async def async_unload_entry(self) -> None:
        if self._cancel_fast_update: self._cancel_fast_update()
        if self._pending_fast_start_cancel: self._pending_fast_start_cancel()
        
        self.mqtt.stop()
        await self.connection.close()
        self._fast_listeners.clear()

    # --- HELPERS ---
    
    def _apply_optimistic_overlay(self) -> None:
        try:
            overlay = self._setting_handler.get_optimistic_overlay(self.inverter_data)
            if overlay: self._optimistic_overlay = overlay
        except Exception: pass

    async def _write_register(self, address: int, value: int) -> bool:
        """Helper for charge_control.py to write via connection service."""
        client = await self.connection.get_client()
        return await try_write_registers(
            client, self._read_lock, 1, address, value
        )

    @property
    def _client(self):
        return self.connection._client