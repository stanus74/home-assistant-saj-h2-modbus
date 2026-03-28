from __future__ import annotations
import asyncio
import logging
import time
from typing import Any
import importlib
from homeassistant.core import HomeAssistant
from homeassistant.components import mqtt
from pymodbus.client import ModbusTcpClient

from .modbus_utils import (
    _connect_client_inplace,
    set_modbus_config,
    ConnectionCache,
    CircuitBreaker,
    ModbusCircuitBreaker,
)
from .utils import create_logged_task

# paho-mqtt is imported lazily in an executor to avoid blocking the event loop
PAHO_AVAILABLE = None  # None=unknown, True/False once attempted

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
        self._connection_lock = asyncio.Lock()
        self._reconnecting = False

        # ONE client object, created once and reused for the entire lifetime.
        # Reconnect = close() + connect() on this same object – never replaced.
        # This guarantees that all polling loops always reference the same socket.
        self._client: ModbusTcpClient = ModbusTcpClient(host=host, port=port, timeout=5)

        # Connection cache to avoid repeated connection-state checks
        self._connection_cache = ConnectionCache(cache_ttl=30.0)

        # Per-instance circuit breaker – isolates this inverter's failure state
        # from any other configured inverter (multi-inverter setups).
        self._circuit_breaker = ModbusCircuitBreaker()

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
        return self._client.connected

    @property
    def circuit_breaker(self) -> ModbusCircuitBreaker:
        """Per-instance circuit breaker for this inverter connection."""
        return self._circuit_breaker

    async def get_client(self) -> ModbusTcpClient:
        """
        Returns the single connected client, connecting it if needed.

        Always returns the same ModbusTcpClient instance. Never creates a second one.
        """
        async with self._connection_lock:
            cached_client = await self._connection_cache.get_cached_client()
            if cached_client is not None and cached_client.connected:
                return cached_client

            async def _connect_and_cache() -> ModbusTcpClient:
                await _connect_client_inplace(self._client, self._host, self._port)
                await self._connection_cache.set_cached_client(self._client)
                return self._client

            return await self._circuit_breaker.call(
                _connect_and_cache,
                should_trip=lambda e: isinstance(e, (ConnectionError, OSError)),
            )

    async def reconnect(self) -> bool:
        """
        Forces a reconnection by closing and re-opening the single client socket.
        Never creates a new ModbusTcpClient – always reuses the same object.
        """
        if self._reconnecting:
            return False

        async with self._connection_lock:
            if self._reconnecting:
                return False

            self._reconnecting = True
            try:
                await self._connection_cache.invalidate()
                await self._close_socket()
                await _connect_client_inplace(self._client, self._host, self._port)
                await self._connection_cache.set_cached_client(self._client)
                return True
            except Exception as e:
                _LOGGER.error("Reconnection failed: %s", e)
                return False
            finally:
                self._reconnecting = False

    async def _close_socket(self) -> None:
        """Close the socket on the single client without destroying the client object."""
        try:
            await self.hass.async_add_executor_job(self._client.close)
            _LOGGER.debug("Modbus socket closed")
        except Exception as e:
            _LOGGER.warning("Error closing Modbus socket: %s", e)

    async def close(self) -> None:
        """Close the socket. The client object itself is kept alive for reuse."""
        await self._connection_cache.invalidate()
        await self._close_socket()

    async def notify_error(self) -> None:
        """Mark connection cache as immediately expired after a read/write error.

        Call this as soon as a ReconnectionNeededError is caught so that no
        concurrent task receives the now-stale cached client before reconnect()
        has finished.
        """
        await self._connection_cache.notify_error()

    async def cleanup_cache(self) -> None:
        """Clean up stale cache entries and close socket if disconnected."""
        async with self._connection_lock:
            invalidated = await self._connection_cache.cleanup_stale()
            if invalidated and not self._client.connected:
                await self._close_socket()
                _LOGGER.debug("Modbus socket closed after cache cleanup")

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

            # Close active client so the next call re-connects with new settings.
            create_logged_task(self.hass, self.close(), logger=_LOGGER)


class MqttCircuitBreaker(CircuitBreaker):
    """Circuit breaker pattern for MQTT publishing."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60) -> None:
        super().__init__(failure_threshold, timeout, "MQTT")


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
        self._strategy_cache_key = None

        # Internal Client
        self._paho_client = None
        self._paho_started = False
        self._paho_module = None
        self._paho_available: bool | None = None
        self._last_strategy_log = 0.0
        
        # Log throttling
        self._last_no_connection_log = 0.0
        
        # Determine strategy immediately
        self._determine_strategy(force=True)
        
        # Init Paho if selected
        if self.strategy == self.STRATEGY_PAHO:
            create_logged_task(self.hass, self._async_init_paho_client(), logger=_LOGGER)

    def _strategy_key(self) -> tuple:
        """Compute strategy cache key based on relevant inputs."""
        clean_host = (self.host or "").strip().lower()
        ha_mqtt_loaded = "mqtt" in self.hass.config.components
        return (
            clean_host,
            bool(self.use_ha_mqtt),
            bool(ha_mqtt_loaded),
            bool(self._paho_available is not False),
        )

    def _is_ha_mqtt_available(self) -> bool:
        """Return True if the HA MQTT integration is loaded and available."""
        return "mqtt" in self.hass.config.components

    def _select_strategy(self, clean_host: str) -> str:
        """Derive the correct MQTT strategy from the current configuration.

        Priority order:
        1. Forced HA MQTT (use_ha_mqtt flag)
        2. Paho (explicit host, paho installed)
        3. HA MQTT (auto-detected)
        4. None (disabled)
        """
        # Priority 1: forced HA MQTT
        if self.use_ha_mqtt:
            if self._is_ha_mqtt_available():
                return self.STRATEGY_HA
            _LOGGER.warning(
                "MQTT strategy fallback: use_ha_mqtt is enabled, but HA MQTT integration is not loaded"
            )
            return self.STRATEGY_NONE

        # Priority 2: Paho with explicit host
        if clean_host:
            if self._paho_available is False:
                _LOGGER.warning(
                    "MQTT strategy fallback: host configured (%s) but paho-mqtt is not installed. "
                    "Falling back to HA MQTT (if available) or disabling MQTT.",
                    self.host,
                )
            else:
                return self.STRATEGY_PAHO

        # Priority 3: HA MQTT auto-detected
        if self._is_ha_mqtt_available():
            return self.STRATEGY_HA

        # Priority 4: disabled
        return self.STRATEGY_NONE

    def _determine_strategy(self, force: bool = False):
        """Decide once which MQTT strategy to use with minimal logging."""
        cache_key = self._strategy_key()
        if not force and cache_key == self._strategy_cache_key:
            return
        self._strategy_cache_key = cache_key

        # Normalise and sanitise host input
        clean_host = (self.host or "").strip().lower()
        if clean_host in {"disable", "disabled", "off", "none", "false"}:
            clean_host = ""
        if not clean_host:
            self.host = ""

        # When use_ha_mqtt is active, never fall back to Paho
        if self.use_ha_mqtt:
            self.host = ""
            clean_host = ""

        new_strategy = self._select_strategy(clean_host)

        if new_strategy == self.STRATEGY_PAHO:
            self._log_strategy(
                new_strategy,
                f"MQTT Strategy Selected: Internal Paho Client (Custom Host configured: {self.host}:{self.port})",
                f"MQTT Strategy remains Paho (Host: {self.host}:{self.port})",
            )
        elif new_strategy == self.STRATEGY_HA:
            self._log_strategy(
                new_strategy,
                "MQTT Strategy Selected: Home Assistant Native Integration"
                if not self.use_ha_mqtt
                else "MQTT Strategy Selected: Forced Home Assistant MQTT (use_ha_mqtt enabled)",
                "MQTT Strategy remains HA"
                if not self.use_ha_mqtt
                else "MQTT Strategy remains HA (use_ha_mqtt enabled)",
            )
            if new_strategy == self.STRATEGY_HA and not self.use_ha_mqtt and (self.user or self.password):
                _LOGGER.warning(
                    "CONFIG WARNING: MQTT User/Pass are set in SAJ config, but ignored because HOST IP is missing/disabled. "
                    "Using HA Integration instead. If you want direct connection, enter the IP. If not, ignore this."
                )
        else:
            self._log_strategy(
                new_strategy,
                "MQTT Strategy Selected: Disabled (No config, no HA MQTT found)",
                "MQTT Strategy remains disabled",
            )

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

    async def _async_load_paho_module(self) -> bool:
        """Load paho.mqtt.client in executor to avoid blocking the event loop."""
        if self._paho_available is not None:
            return bool(self._paho_available)

        def _import_paho():
            return importlib.import_module("paho.mqtt.client")

        try:
            self._paho_module = await self.hass.async_add_executor_job(_import_paho)
            self._paho_available = True
            return True
        except ImportError:
            self._paho_available = False
            return False

    async def _async_init_paho_client(self) -> None:
        """Initialize Paho client if configured."""
        if not self.host:
            return

        if not await self._async_load_paho_module():
            _LOGGER.warning(
                "MQTT strategy fallback: host configured (%s) but paho-mqtt is not installed. "
                "Falling back to HA MQTT (if available) or disabling MQTT.",
                self.host,
            )
            prev_strategy = self.strategy
            self._determine_strategy(force=True)
            if self.strategy != prev_strategy:
                self.stop()
            return

        try:
            # Basic init
            self._paho_client = self._paho_module.Client()

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

    async def _publish_paho(self, topic: str, payload: str) -> None:
        """Publish via Paho client in executor."""
        if not self._paho_client:
            return
        await self.hass.async_add_executor_job(self._paho_client.publish, topic, payload)

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

        # Re-evaluate strategy only when strategy inputs change
        prev_strategy = self.strategy
        self._determine_strategy(force=False)
        strategy_changed = self.strategy != prev_strategy

        # Handle Strategy Switch or Config Change
        if self.strategy == self.STRATEGY_PAHO:
            if connection_changed or strategy_changed or not self._paho_client:
                self.stop()
                create_logged_task(self.hass, self._async_init_paho_client(), logger=_LOGGER)
        else:
            # If we switched away from Paho, stop it
            if prev_strategy == self.STRATEGY_PAHO:
                self.stop()

    async def publish_data(self, data: dict[str, Any], force: bool = False) -> None:
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
                    await self._circuit_breaker.call(
                        self._publish_paho,
                        f"{self.topic_prefix}/{key}",
                        payload,
                    )
            except Exception as e:
                _LOGGER.warning("Internal MQTT publish failed: %s", e)

    def stop(self):
        """Stops the internal Paho client."""
        if self._paho_client and self._paho_started:
            _LOGGER.info("Paho MQTT: Stopping client")
            self._paho_client.loop_stop()
            self._paho_client.disconnect()
            self._paho_started = False
