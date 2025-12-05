from __future__ import annotations
"""SAJ Modbus Hub with optimized processing and fixed interval system."""
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
from datetime import timedelta
from homeassistant.core import HomeAssistant, callback, CoreState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.components import mqtt
from .const import DOMAIN, CONF_FAST_ENABLED
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from pymodbus.client import ModbusTcpClient
from homeassistant.config_entries import ConfigEntry

# Try to import paho-mqtt for direct connection fallback
try:
    import paho.mqtt.client as mqtt_client
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

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

# Enable defaults for debugging
FAST_POLL_DEFAULT = False
# ULTRA_FAST_POLL removed, now dynamic via config
ADVANCED_LOGGING = False
CONF_ULTRA_FAST_ENABLED = "ultra_fast_enabled"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_PUBLISH_ALL = "mqtt_publish_all"

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
 
        # Prioritize options, fallback to data
        host = config_entry.options.get(CONF_HOST, config_entry.data.get(CONF_HOST))
        port = config_entry.options.get(CONF_PORT, config_entry.data.get(CONF_PORT, 502))
        scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, config_entry.data.get(CONF_SCAN_INTERVAL, 60))
 
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
 
        # MQTT Configuration
        # Removed http:// prefix - MQTT requires plain IP or hostname
        self.mqtt_host = config_entry.options.get("mqtt_host", "")
        self.mqtt_port = config_entry.options.get("mqtt_port", 1883)
        self.mqtt_user = config_entry.options.get("mqtt_user", "")
        self.mqtt_password = config_entry.options.get("mqtt_password", "")
        raw_prefix = (
            config_entry.options.get(CONF_MQTT_TOPIC_PREFIX)
            or config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "")
        )
        normalized_prefix = (raw_prefix or "").strip()
        self.mqtt_topic_prefix = normalized_prefix.rstrip("/") if normalized_prefix else "saj"
        self.mqtt_publish_all = config_entry.options.get(
            CONF_MQTT_PUBLISH_ALL,
            config_entry.data.get(CONF_MQTT_PUBLISH_ALL, False),
        )
        self._ha_mqtt_available = None
        self._ha_mqtt_last_check = 0.0
        self._ha_mqtt_check_interval = 30.0

        # Initialize internal MQTT client as fallback
        self._paho_client = None
        self._paho_started = False
        
        if ADVANCED_LOGGING:
            _LOGGER.info("MQTT Paho Client Available: %s", PAHO_AVAILABLE)

        if PAHO_AVAILABLE and self.mqtt_host:
            try:
                # Use basic init to be compatible with v1 and v2
                self._paho_client = mqtt_client.Client()
                if self.mqtt_user:
                    self._paho_client.username_pw_set(self.mqtt_user, self.mqtt_password)
            except Exception as e:
                _LOGGER.error("Failed to initialize internal MQTT client: %s", e)

        set_modbus_config(self._host, self._port, hass)
        self._read_lock = asyncio.Lock()
        self.inverter_data: Dict[str, Any] = {}
        self._client: Optional[ModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        self.fast_enabled = config_entry.options.get(CONF_FAST_ENABLED, FAST_POLL_DEFAULT)
        self.ultra_fast_enabled = config_entry.options.get(CONF_ULTRA_FAST_ENABLED, False)
        
        # Force fast_enabled if ultra_fast is enabled to ensure loop starts
        if self.ultra_fast_enabled:
            self.fast_enabled = True

        self._fast_coordinator = None
        self._fast_unsub = None
        self._cancel_fast_update = None
        self._pending_fast_start_cancel: Optional[Callable] = None
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
            _LOGGER.warning("Fast updates disabled via hub setting (fast_enabled=False); skipping start.")
            return
        if self._cancel_fast_update is not None:
            _LOGGER.debug("Fast updates already running")
            return
        if self._pending_fast_start_cancel is not None:
            _LOGGER.debug("Fast update start already scheduled; skipping duplicate schedule")
            return

        interval = 1 if self.ultra_fast_enabled else 10
        
        # Check if MQTT integration is configured in Home Assistant
        mqtt_in_config = "mqtt" in self.hass.config.components
        
        # Determine startup delay:
        # - If HA is NOT running yet (starting up): Wait 30s to let MQTT load
        # - If HA IS running (config change): Start almost immediately (1s)
        
        is_running = False
        # Handle CoreState enum changes (RUNNING vs running) to be compatible with different HA versions
        if hasattr(CoreState, "running") and self.hass.state == CoreState.running:
            is_running = True
        elif hasattr(CoreState, "RUNNING") and self.hass.state == CoreState.RUNNING:
            is_running = True
            
        if is_running:
            startup_delay = 1
        else:
            startup_delay = 30 if mqtt_in_config else 1
        
        _LOGGER.info(
            "Scheduling fast updates start (interval=%ss, Ultra Fast=%s). MQTT in HA config: %s. Delay: %ss", 
            interval, self.ultra_fast_enabled, mqtt_in_config, startup_delay
        )
        
        @callback
        def _start_loop(_):
            # clear pending marker
            self._pending_fast_start_cancel = None
            if self._cancel_fast_update is not None:
                return  # Already started

            _LOGGER.info("Starting fast update loop now")
            self._cancel_fast_update = async_track_time_interval(
                self.hass,
                self._async_update_fast,
                timedelta(seconds=interval)
            )
            
        self._pending_fast_start_cancel = async_call_later(self.hass, startup_delay, _start_loop)

    async def _async_update_fast(self, now=None) -> None:
        """Fast update function called by async_track_time_interval."""
        if not self.fast_enabled:
            return
            
        # Debug log to confirm loop is running
        if ADVANCED_LOGGING:
            _LOGGER.debug("Fast update loop triggered")

        if self._client is None or not self._client.connected:
            try:
                await self._ensure_connected_client()
            except Exception as e:
                _LOGGER.warning("Fast update: Failed to ensure connection: %s", e)
                return
        
        try:
            # Execute reader for fast poll sensors
            # All requested power sensors are in additional_data_1_part_2
            result = await modbus_readers.read_additional_modbus_data_1_part_2(self._client, self._read_lock)
            
            if result:
                # Filter result to only include fast poll sensors
                fast_data = {k: v for k, v in result.items() if k in FAST_POLL_SENSORS}
                
                if fast_data:
                    # Update internal cache with all data (even non-fast ones from the block)
                    self.inverter_data.update(result)
                    
                    # Publish to MQTT
                    self._publish_fast_data_to_mqtt(fast_data)
                    
                    # Only notify fast listeners about fast sensor changes if NOT in ultra fast mode
                    # In ultra fast mode (1s), we only push to MQTT to avoid overloading HA state machine
                    # NOTE: The regular coordinator update (every 60s) will still update these sensors in HA.
                    if not self.ultra_fast_enabled:
                        for listener in self._fast_listeners:
                            listener()
                    elif ADVANCED_LOGGING:
                        _LOGGER.debug("Skipping HA entity updates in Ultra Fast mode to save DB")
                    
                    if ADVANCED_LOGGING:
                        _LOGGER.debug(
                            f"Fast update completed: {len(fast_data)} sensors updated "
                            f"(filtered to fast sensors only)"
                        )
                else:
                    _LOGGER.debug("Fast update: No fast-poll sensors in result")
            else:
                if ADVANCED_LOGGING:
                    _LOGGER.debug("Fast update: Reader returned no data")

        except ReconnectionNeededError as e:
            _LOGGER.warning("Fast update requires reconnection: %s", e)
            await self.reconnect_client()
        except Exception as e:
            _LOGGER.warning("Fast update failed: %s", e)

    def _is_ha_mqtt_available(self) -> bool:
        now = time.monotonic()
        if (
            self._ha_mqtt_available is not None
            and (now - self._ha_mqtt_last_check) < self._ha_mqtt_check_interval
        ):
            return self._ha_mqtt_available
        available = False
        if "mqtt" in self.hass.config.components:
            try:
                available = bool(mqtt.is_connected(self.hass))
            except (AttributeError, ImportError, KeyError):
                available = False
        if not available and self.hass.services.has_service("mqtt", "publish"):
            available = True
        self._ha_mqtt_available = available
        self._ha_mqtt_last_check = now
        return available

    def _publish_fast_data_to_mqtt(self, data: Dict[str, Any]) -> None:
        """Publish fast poll data to MQTT."""
        if not data:
            return

        def normalize_sensor_key(raw_key: str) -> str:
            parts = [segment for segment in raw_key.split("/") if segment]
            for segment in reversed(parts):
                if segment.lower() not in {"saj", "mqtt"}:
                    return segment
            return parts[-1] if parts else raw_key

        base_topic = self._get_base_topic()
        messages: List[tuple[str, str]] = []
        for key, value in data.items():
            sensor_key = normalize_sensor_key(key) or key.replace("/", "_")
            messages.append((sensor_key, str(value)))

        if not messages:
            return

        if self._is_ha_mqtt_available():
            try:
                if self._paho_client and self._paho_started:
                    self._paho_client.loop_stop()
                    self._paho_client.disconnect()
                    self._paho_started = False
                for sensor_key, payload in messages:
                    topic = f"{base_topic}/{sensor_key}"
                    self.hass.async_create_task(
                        mqtt.async_publish(self.hass, topic, payload)
                    )
                return
            except Exception as err:
                _LOGGER.debug("HA MQTT publish failed, falling back: %s", err)
                self._ha_mqtt_available = False
                self._ha_mqtt_last_check = 0.0

        if PAHO_AVAILABLE and (self._paho_client or self.mqtt_host):
            if self._paho_client is None and self.mqtt_host:
                try:
                    self._paho_client = mqtt_client.Client()
                    if self.mqtt_user:
                        self._paho_client.username_pw_set(self.mqtt_user, self.mqtt_password)
                except Exception as err:
                    _LOGGER.error("Failed to initialize internal MQTT client: %s", err)
                    return
            if self._paho_client:
                try:
                    if not self._paho_started:
                        self._paho_client.connect_async(self.mqtt_host, self.mqtt_port)
                        self._paho_client.loop_start()
                        self._paho_started = True
                    for sensor_key, payload in messages:
                        self._paho_client.publish(f"{base_topic}/{sensor_key}", payload)
                    return
                except Exception as err:
                    _LOGGER.error("Internal MQTT publish failed: %s", err)
                    return

        if not PAHO_AVAILABLE:
            _LOGGER.warning(
                "MQTT service unavailable and paho-mqtt not installed; cannot publish MQTT data."
            )
        else:
            _LOGGER.warning(
                "MQTT service unavailable and no internal client configured. Check MQTT settings."
            )

    @callback
    def async_add_fast_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for fast-update notifications."""
        self._fast_listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            if update_callback in self._fast_listeners:
                self._fast_listeners.remove(update_callback)

        return remove_listener

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
                
                # Update fast_enabled and ultra_fast_enabled
                self.ultra_fast_enabled = ultra_fast_enabled
                # Force fast_enabled if ultra_fast is enabled
                self.fast_enabled = fast_enabled or ultra_fast_enabled

                # Update MQTT settings
                mqtt_changed = (
                    mqtt_host != self.mqtt_host or 
                    mqtt_port != self.mqtt_port or 
                    mqtt_user != self.mqtt_user or 
                    mqtt_password != self.mqtt_password
                )
                self.mqtt_host = mqtt_host
                self.mqtt_port = mqtt_port
                self.mqtt_user = mqtt_user
                self.mqtt_password = mqtt_password

                last_prefix = (self.mqtt_topic_prefix or "").strip()
                if not last_prefix:
                    entry_prefix = (
                        (self._config_entry.options.get(CONF_MQTT_TOPIC_PREFIX, "") or "")
                        or (self._config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "") or "")
                    )
                    last_prefix = entry_prefix.strip() or "saj"
                incoming_prefix = mqtt_topic_prefix if mqtt_topic_prefix is not None else last_prefix
                if not isinstance(incoming_prefix, str):
                    incoming_prefix = str(incoming_prefix)
                incoming_prefix = incoming_prefix.strip()
                if not incoming_prefix:
                    incoming_prefix = last_prefix
                new_prefix = incoming_prefix.rstrip("/")
                prefix_changed = new_prefix != self.mqtt_topic_prefix
                self.mqtt_topic_prefix = new_prefix
                if prefix_changed:
                    _LOGGER.info("MQTT topic prefix updated to %s", self.mqtt_topic_prefix)
                publish_all_changed = mqtt_publish_all != self.mqtt_publish_all
                self.mqtt_publish_all = mqtt_publish_all
                if publish_all_changed:
                    _LOGGER.info("MQTT full publish toggled to %s", self.mqtt_publish_all)
                if mqtt_changed or prefix_changed:
                    self._ha_mqtt_available = None
                    self._ha_mqtt_last_check = 0.0

                if mqtt_changed:
                    _LOGGER.info("MQTT settings changed, re-initializing client...")
                    
                    # Stop existing client if running
                    if self._paho_client:
                        if self._paho_started:
                            self._paho_client.loop_stop()
                            self._paho_client.disconnect()
                            self._paho_started = False
                        self._paho_client = None

                    # Re-init client with new credentials if needed
                    if PAHO_AVAILABLE and self.mqtt_host:
                        try:
                            self._paho_client = mqtt_client.Client()
                            if self.mqtt_user:
                                self._paho_client.username_pw_set(self.mqtt_user, self.mqtt_password)
                            _LOGGER.info("Internal MQTT client re-initialized")
                        except Exception as e:
                            _LOGGER.error("Failed to re-initialize internal MQTT client: %s", e)

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    if self._client:
                        try:
                            # Use standard synchronous close
                            self._client.close()
                        except Exception as e:
                            _LOGGER.warning(f"Error while closing old Modbus client: {e}")
                    # Reset client to None so it gets recreated by connect_if_needed with new settings
                    self._client = None
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")

                if ADVANCED_LOGGING:
                    _LOGGER.debug(
                        "Updated configuration - Host: %s, Port: %d, Scan Interval: %d, Fast Enabled: %s, Ultra Fast: %s",
                        self._host,
                        self._port,
                        scan_interval,
                        fast_enabled,
                        self.ultra_fast_enabled
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
        # Cancel any pending start
        if self._pending_fast_start_cancel is not None:
            self._pending_fast_start_cancel()
            self._pending_fast_start_cancel = None
            _LOGGER.debug("Cancelled pending fast start")
        # Stop existing fast updates
        if self._cancel_fast_update is not None:
            self._cancel_fast_update()
            self._cancel_fast_update = None
            _LOGGER.debug("Stopped old fast updates")
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
                        # Use standard synchronous close
                        self._client.close()
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
            
            # This reads ALL data, including the fast sensors (Group 2)
            # This ensures that even if Ultra Fast mode skips HA updates in the fast loop,
            # the sensors are still updated in HA every 60s (or configured scan_interval).
            cache = await self._run_reader_methods()
            self._optimistic_overlay = None
            self.inverter_data = cache

            if self.mqtt_publish_all and self.inverter_data:
                self._publish_fast_data_to_mqtt(self.inverter_data)
            
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
                        "Static inverter data loaded successfully",
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
                
                if isinstance(result, (ReconnectionNeededError, ConnectionError)):
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
        
        # Stop internal MQTT client if running
        if self._paho_client and self._paho_started:
            self._paho_client.loop_stop()
            self._paho_client.disconnect()
            self._paho_started = False
        
        # Clear fast listeners
        self._fast_listeners.clear()

        # Sicherstellen, dass der Client immer geschlossen wird
        client_to_close = self._client
        if client_to_close:
            self._client = None  # Verweis sofort entfernen
            try:
                # Use standard synchronous close
                client_to_close.close()
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

    def _get_base_topic(self) -> str:
        base = (self.mqtt_topic_prefix or "").rstrip("/")
        return base or "saj"