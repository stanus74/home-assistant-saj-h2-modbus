from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional, Any, Dict, List, Callable
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import mqtt
from pymodbus.client import ModbusTcpClient

# Try to import paho-mqtt
try:
    import paho.mqtt.client as mqtt_client
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

from .modbus_utils import (
    connect_if_needed,
    set_modbus_config,
    ReconnectionNeededError,
    ConnectionCache
)

_LOGGER = logging.getLogger(__name__)

# Define constants locally to avoid ImportError with existing const.py
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_PUBLISH_ALL = "mqtt_publish_all"

class ModbusConnectionManager:
    """
    Manages the Modbus TCP connection, locking, and reconnection logic.
    
    PERFORMANCE OPTIMIZATION: Uses connection caching to reduce redundant
    connection checks and lock acquisitions.
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int):
        self.hass = hass
        self._host = host
        self._port = port
        self._client: Optional[ModbusTcpClient] = None
        self._connection_lock = asyncio.Lock()
        self._reconnecting = False
        
        # PERFORMANCE OPTIMIZATION: Connection cache to reduce overhead
        # Cache client for 60 seconds to avoid repeated connection checks
        self._connection_cache = ConnectionCache(cache_ttl=60.0)
        
        # Initial setup of global config for utils
        set_modbus_config(host, port, hass)

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.connected

    async def get_client(self) -> ModbusTcpClient:
        """
        Returns a connected client, establishing connection if needed.
        
        PERFORMANCE OPTIMIZATION: Uses connection cache to reduce redundant
        connection checks. Only acquires lock when cache is invalid.
        """
        # PERFORMANCE OPTIMIZATION: Try to get cached client without lock first
        cached_client = self._connection_cache.get_cached_client()
        if cached_client is not None:
            return cached_client
        
        # Cache miss - need to establish connection
        async with self._connection_lock:
            # Double-check after acquiring lock (another task might have connected)
            cached_client = self._connection_cache.get_cached_client()
            if cached_client is not None:
                return cached_client
            
            # Establish new connection
            self._client = await connect_if_needed(self._client, self._host, self._port)
            
            # PERFORMANCE OPTIMIZATION: Cache the connected client
            self._connection_cache.set_cached_client(self._client)
            
            return self._client

    async def reconnect(self) -> bool:
        """
        Forces a reconnection.
        
        PERFORMANCE OPTIMIZATION: Invalidates cache on reconnect to ensure
        fresh connection is used.
        """
        if self._reconnecting:
            return False

        async with self._connection_lock:
            if self._reconnecting:
                return False
            
            self._reconnecting = True
            try:
                # PERFORMANCE OPTIMIZATION: Invalidate cache before reconnect
                self._connection_cache.invalidate()
                
                await self.close()
                self._client = await connect_if_needed(None, self._host, self._port)
                
                # PERFORMANCE OPTIMIZATION: Cache the new connection
                self._connection_cache.set_cached_client(self._client)
                
                return True
            except Exception as e:
                _LOGGER.error("Reconnection failed: %s", e)
                return False
            finally:
                self._reconnecting = False

    async def close(self) -> None:
        """
        Safely closes the connection in an executor.
        
        PERFORMANCE OPTIMIZATION: Invalidates cache when closing connection.
        """
        if self._client:
            try:
                # PERFORMANCE OPTIMIZATION: Invalidate cache on close
                self._connection_cache.invalidate()
                
                client_to_close = self._client
                self._client = None
                await self.hass.async_add_executor_job(client_to_close.close)
                _LOGGER.debug("Modbus client closed")
            except Exception as e:
                _LOGGER.warning("Error closing Modbus client: %s", e)

    def update_config(self, host: str, port: int):
        """
        Updates connection parameters.
        
        PERFORMANCE OPTIMIZATION: Invalidates cache when config changes to
        ensure new connection settings are used.
        """
        if host != self._host or port != self._port:
            _LOGGER.info("Updating Modbus config: %s:%s -> %s:%s", self._host, self._port, host, port)
            self._host = host
            self._port = port
            set_modbus_config(host, port, self.hass)
            
            # PERFORMANCE OPTIMIZATION: Invalidate cache on config change
            self._connection_cache.invalidate()
            
            # Close active client so the next call re-connects with new settings
            if self._client:
                self.hass.async_create_task(self.close())


class MqttCircuitBreaker:
    """Circuit breaker pattern for MQTT publishing."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        now = time.monotonic()

        if self.state == "OPEN":
            if now - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                _LOGGER.info("MQTT Circuit Breaker transitioning to HALF_OPEN")
            else:
                raise ConnectionError("MQTT Circuit Breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                _LOGGER.info("MQTT Circuit Breaker transitioning to CLOSED")
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = now
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                _LOGGER.warning(f"MQTT Circuit Breaker OPEN after {self.failure_count} failures")
            raise e


class MqttPublisher:
    """Manages MQTT publishing via HA or internal Paho client."""

    STRATEGY_HA = "HA"
    STRATEGY_PAHO = "PAHO"
    STRATEGY_NONE = "NONE"

    def __init__(self, hass: HomeAssistant, host: str, port: int, user: str, password: str, topic_prefix: str, publish_all: bool, ultra_fast_enabled: bool, use_ha_mqtt: bool = False):
        self.hass = hass
        self._circuit_breaker = MqttCircuitBreaker(
            failure_threshold=3 if ultra_fast_enabled else 5,
            timeout=30 if ultra_fast_enabled else 60,
        )
        
        # Config
        self.host = host
        try:
            self.port = int(port)
        except (ValueError, TypeError):
            self.port = 1883
            
        self.user = user
        self.password = password
        self.publish_all = publish_all
        self.topic_prefix = (topic_prefix or "saj").strip().rstrip("/")
        self.use_ha_mqtt = use_ha_mqtt
        
        self.strategy = self.STRATEGY_NONE

        # Internal Client
        self._paho_client = None
        self._paho_started = False
        self._last_strategy_log = 0.0
        
        # Log throttling
        self._last_no_connection_log = 0.0
        
        # Determine strategy immediately
        self._determine_strategy()
        
        # Init Paho if selected
        if self.strategy == self.STRATEGY_PAHO:
            self._init_paho_client()

    def _determine_strategy(self):
        """Decide once which MQTT strategy to use with minimal logging."""
        # Clean up host input
        clean_host = (self.host or "").strip().lower()

        # Forced HA MQTT path overrides host setting
        if self.use_ha_mqtt:
            if "mqtt" in self.hass.config.components:
                self.host = ""
                new_strategy = self.STRATEGY_HA
                self._log_strategy(new_strategy, "MQTT Strategy Selected: Forced Home Assistant MQTT (use_ha_mqtt enabled)", "MQTT Strategy remains HA (use_ha_mqtt enabled)")
                self.strategy = new_strategy
                return
            _LOGGER.warning("MQTT Strategy fallback: use_ha_mqtt aktiviert, aber HA MQTT Integration nicht geladen")
            # Host leeren, damit wir nicht zurück auf Paho fallen
            self.host = ""
            clean_host = ""

        # 1. Check for manual disable or empty
        if not clean_host or clean_host in ["disable", "disabled", "off", "none", "false"]:
            # If manually disabled, fall through to HA check or None
            self.host = ""  # Ensure it's treated as empty
            clean_host = ""
        
        # 2. Priority: Manual Configuration (Paho) - Only if we have a valid-looking host
        if self.host:
            if not PAHO_AVAILABLE:
                _LOGGER.warning(
                    "MQTT Strategy fallback: Host configured (%s) but paho-mqtt ist nicht installiert. "
                    "Falle zurück auf HA-MQTT (falls vorhanden) oder deaktiviert.",
                    self.host,
                )
            else:
                new_strategy = self.STRATEGY_PAHO
                self._log_strategy(new_strategy, f"MQTT Strategy Selected: Internal Paho Client (Custom Host configured: {self.host}:{self.port})", f"MQTT Strategy remains Paho (Host: {self.host}:{self.port})")
                self.strategy = new_strategy
                return

        # 3. Priority: Home Assistant Integration
        if "mqtt" in self.hass.config.components:
            new_strategy = self.STRATEGY_HA
            self._log_strategy(new_strategy, "MQTT Strategy Selected: Home Assistant Native Integration", "MQTT Strategy remains HA (auto-detected)")
            self.strategy = new_strategy
            # Warn if user provided credentials in SAJ config, as they are ignored in HA strategy
            if self.user or self.password:
                _LOGGER.warning(
                    "CONFIG WARNING: MQTT User/Pass are set in SAJ config, but ignored because HOST IP is missing/disabled. "
                    "Using HA Integration instead. If you want direct connection, enter the IP. If not, ignore this."
                )
            return

        # 4. No MQTT
        new_strategy = self.STRATEGY_NONE
        self._log_strategy(new_strategy, "MQTT Strategy Selected: Disabled (No config, no HA MQTT found)", "MQTT Strategy remains disabled")
        self.strategy = new_strategy

    def _log_strategy(self, new_strategy: str, info_msg: str, debug_msg: str):
        now = time.monotonic()
        if new_strategy != self.strategy:
            # Only escalate to INFO if last strategy log is older than 2s; otherwise DEBUG to avoid bursts
            if now - self._last_strategy_log > 2:
                _LOGGER.info(info_msg)
            else:
                _LOGGER.debug(info_msg)
            self._last_strategy_log = now
        else:
            _LOGGER.debug(debug_msg)

    def _init_paho_client(self):
        """Initialize Paho client if configured."""
        if PAHO_AVAILABLE and self.host:
            try:
                # Basic init
                self._paho_client = mqtt_client.Client()
                
                # Setup Callbacks for Debugging
                self._paho_client.on_connect = self._on_paho_connect
                self._paho_client.on_disconnect = self._on_paho_disconnect
                
                # Auth
                auth_status = "without Auth"
                if self.user:
                    self._paho_client.username_pw_set(self.user, self.password)
                    auth_status = f"with Auth (User: {self.user})"
                
                _LOGGER.debug("Internal MQTT client initialized %s (waiting for connect)", auth_status)
            except Exception as e:
                _LOGGER.error("Failed to init internal MQTT: %s", e)

    def _on_paho_connect(self, client, userdata, flags, rc, *args):
        """Callback for Paho connection result."""
        # RC codes: 0=Success, 1=Protocol wrong, 2=ID rejected, 3=Server unavailable, 4=Bad user/pass, 5=Not authorized
        if rc == 0:
            _LOGGER.info("Paho MQTT: Connected successfully to %s:%s", self.host, self.port)
        elif rc == 4 or rc == 5:
            _LOGGER.error("Paho MQTT: Auth failed (rc=%s). Check Username/Password in SAJ Config!", rc)
        else:
            _LOGGER.error("Paho MQTT: Connection failed with return code %s", rc)

    def _on_paho_disconnect(self, client, userdata, rc, *args):
        """Callback for Paho disconnect."""
        if rc != 0:
            _LOGGER.warning("Paho MQTT: Disconnected unexpectedly (rc=%s)", rc)

    def update_config(self, host, port, user, password, topic_prefix, publish_all, ultra_fast_enabled, use_ha_mqtt=False):
        """Updates MQTT configuration and re-inits client if needed (logs only on change)."""
        try:
            new_port = int(port)
        except (ValueError, TypeError):
            new_port = 1883

        # If HA MQTT is forced, ignore provided host to prevent Paho fallback
        incoming_host = "" if use_ha_mqtt else host

        # Check if critical connection params changed
        connection_changed = (
            incoming_host != self.host
            or new_port != self.port
            or user != self.user
            or password != self.password
            or topic_prefix != self.topic_prefix
            or publish_all != self.publish_all
            or use_ha_mqtt != self.use_ha_mqtt
        )
        
        self.host = incoming_host
        self.port = new_port
        self.user = user
        self.password = password
        self.topic_prefix = (topic_prefix or "saj").strip().rstrip("/")
        self.publish_all = publish_all
        self.use_ha_mqtt = use_ha_mqtt

        if connection_changed:
            _LOGGER.debug("MQTT Config updated. Prefix: '%s'", self.topic_prefix)
        
        # Update CB
        self._circuit_breaker.failure_threshold = 3 if ultra_fast_enabled else 5
        self._circuit_breaker.timeout = 30 if ultra_fast_enabled else 60

        # Re-evaluate strategy
        prev_strategy = self.strategy
        self._determine_strategy()
        strategy_changed = self.strategy != prev_strategy

        # Handle Strategy Switch or Config Change
        if self.strategy == self.STRATEGY_PAHO:
            if connection_changed or strategy_changed or not self._paho_client:
                self.stop()
                self._init_paho_client()
        else:
            # If we switched away from Paho, stop it
            if prev_strategy == self.STRATEGY_PAHO:
                self.stop()

    async def publish_data(self, data: Dict[str, Any], force: bool = False) -> None:
        """Publishes dictionary data to MQTT based on selected strategy."""
        if not data or self.strategy == self.STRATEGY_NONE:
            return
        
        messages = []
        for key, value in data.items():
            safe_key = key.split("/")[-1] if "/" in key else key
            messages.append((safe_key, str(value)))

        if not messages:
            return

        # STRATEGY 1: HA MQTT
        if self.strategy == self.STRATEGY_HA:
            try:
                is_connected = False
                try:
                    is_connected = mqtt.is_connected(self.hass)
                except (KeyError, Exception):
                    is_connected = False

                if is_connected:
                    for key, payload in messages:
                        topic = f"{self.topic_prefix}/{key}"
                        await self._circuit_breaker.call(
                            mqtt.async_publish, self.hass, topic, payload
                        )
                else:
                    # Log throttling
                    now = time.monotonic()
                    if now - self._last_no_connection_log > 60:
                        msg = (
                            "MQTT ERROR: Strategy is 'Home Assistant', but HA MQTT is NOT CONNECTED.\n"
                            "Action required:\n"
                            "1. Go to Settings -> Devices -> MQTT in Home Assistant and fix the connection there."
                        )
                        # Specific hint if user credentials exist in SAJ config
                        if self.user or self.password:
                            msg += (
                                "\n2. OR: You entered User/Password in SAJ Config but disabled the Host IP.\n"
                                "   -> If you wanted to use the Internal Client, put the Broker IP back into the 'MQTT Host' field."
                            )
                        
                        _LOGGER.error(msg)
                        self._last_no_connection_log = now
            except Exception as e:
                _LOGGER.debug("HA MQTT publish failed: %s", e)
            return

        # STRATEGY 2: PAHO (Internal)
        if self.strategy == self.STRATEGY_PAHO and self._paho_client:
            try:
                if not self._paho_started:
                    _LOGGER.info("Paho MQTT: Starting connection loop to %s:%s", self.host, self.port)
                    self._paho_client.connect_async(self.host, self.port)
                    self._paho_client.loop_start()
                    self._paho_started = True
                
                # Check connection status
                if not self._paho_client.is_connected():
                    return 

                for key, payload in messages:
                    self._paho_client.publish(f"{self.topic_prefix}/{key}", payload)
            except Exception as e:
                _LOGGER.warning("Internal MQTT publish failed: %s", e)

    def stop(self):
        """Stops the internal Paho client."""
        if self._paho_client and self._paho_started:
            _LOGGER.info("Paho MQTT: Stopping client")
            self._paho_client.loop_stop()
            self._paho_client.disconnect()
            self._paho_started = False