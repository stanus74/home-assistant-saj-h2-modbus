"""SAJ Modbus Hub with optimized processing and fixed interval system."""

from __future__ import annotations
import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
from contextvars import ContextVar
import logging
import time
from typing import Any, Callable
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback, CoreState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_FAST_ENABLED,
    CONF_ULTRA_FAST_ENABLED,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_MQTT_PUBLISH_ALL,
    CONF_USE_HA_MQTT,
    DEFAULT_CONFIG_SCHEMA,
)
from . import modbus_readers
from .modbus_utils import (
    try_read_registers,
    try_write_registers,
    ReconnectionNeededError,
    _CIRCUIT_BREAKER_CTX,
)
from .charge_control import (
    ChargeSettingHandler,
    PENDING_FIELDS,
)
from .services import ModbusConnectionManager, MqttPublisher
from .utils import get_config_values, create_logged_task

_LOGGER = logging.getLogger(__name__)

# Hub-local config defaults
FAST_POLL_DEFAULT = False
ADVANCED_LOGGING = False
FAST_UPDATE_INTERVAL = 10
ULTRA_FAST_UPDATE_INTERVAL = 1
STARTUP_DELAY_RUNNING = 1
STARTUP_DELAY_MQTT = 30

FAST_POLL_SENSORS = {
    "TotalLoadPower",
    "pvPower",
    "batteryPower",
    "totalgridPower",
    "inverterPower",
    "gridPower",
    "directionPV",
    "directionBattery",
    "directionGrid",
    "directionOutput",
    "CT_GridPowerWatt",
    "CT_GridPowerVA",
    "CT_PVPowerWatt",
    "CT_PVPowerVA",
    "totalgridPowerVA",
    "TotalInvPowerVA",
    "BackupTotalLoadPowerWatt",
    "BackupTotalLoadPowerVA",
    # pv1Power/pv2Power come from read_additional_modbus_data_1_part_1.
    # That function is read in the 10 s fast loop (non-ultra) but NOT in the
    # 1 s ultra-fast loop (which only reads part_2). These keys therefore
    # update at 10 s in fast mode and at 60 s in ultra-fast mode.
    "pv1Power",
    "pv2Power",
}

# TTL for static inverter data (serial, firmware, model). Re-read after this many seconds.
_STATIC_DATA_TTL = 3600.0

_LOCK_ORDER = {
    "merge": 0,
    "slow": 1,
    "fast": 1,
    "ultra_fast": 1,
    "write": 2,
}
_LOCK_STACK: ContextVar[tuple[str, ...]] = ContextVar("saj_lock_stack", default=())

# All reader groups executed sequentially in the 60 s slow poll.
# Defined once at module level to avoid re-creating the list on every cycle (F16).
_READER_GROUPS = [
    [modbus_readers.read_modbus_realtime_data],
    [
        modbus_readers.read_additional_modbus_data_1_part_1,
        modbus_readers.read_additional_modbus_data_1_part_2,
    ],
    [
        modbus_readers.read_additional_modbus_data_2_part_1,
        modbus_readers.read_additional_modbus_data_2_part_2,
    ],
    [
        modbus_readers.read_additional_modbus_data_3,
        modbus_readers.read_additional_modbus_data_3_2,
        modbus_readers.read_additional_modbus_data_4,
    ],
    [
        modbus_readers.read_battery_data,
        modbus_readers.read_inverter_phase_data,
        modbus_readers.read_offgrid_output_data,
    ],
    [
        modbus_readers.read_side_net_data,
        modbus_readers.read_passive_battery_data,
        modbus_readers.read_meter_a_data,
    ],
    [modbus_readers.read_charge_data, modbus_readers.read_discharge_data],
]


class SAJModbusHub(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

        config = get_config_values(config_entry, DEFAULT_CONFIG_SCHEMA)

        # Config extraction - Connection
        host = config[CONF_HOST]
        port = config[CONF_PORT]
        scan_interval = config[CONF_SCAN_INTERVAL]

        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.title,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )

        # Robust config loading (options priority, then data)
        self.ultra_fast_enabled = config[CONF_ULTRA_FAST_ENABLED]
        self.fast_enabled = config[CONF_FAST_ENABLED]

        # Config extraction - MQTT (Fallback logic options -> data -> default)
        mqtt_host = config["mqtt_host"]
        mqtt_port = config["mqtt_port"]
        mqtt_user = config["mqtt_user"]
        mqtt_password = config["mqtt_password"]
        mqtt_topic_prefix = config[CONF_MQTT_TOPIC_PREFIX]
        mqtt_publish_all = config[CONF_MQTT_PUBLISH_ALL]
        use_ha_mqtt = config[CONF_USE_HA_MQTT]

        _LOGGER.info(
            "SAJ Hub Initialized. Host: %s, Fast: %s, Ultra: %s, MQTT Prefix: '%s', MQTT Host: '%s'",
            host,
            self.fast_enabled,
            self.ultra_fast_enabled,
            mqtt_topic_prefix,
            mqtt_host,
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

        self._init_locks()
        self._init_fast_poll_state()
        self._init_charge_control(use_ha_mqtt)

    def _init_locks(self) -> None:
        """Initialise all asyncio locks and synchronisation primitives."""
        # PERFORMANCE OPTIMIZATION: Separate locks for different polling intervals
        # to reduce contention between ultra-fast (1s), fast (10s) and slow (60s) loops.
        # Single lock for all reads because reader groups execute sequentially
        self._read_lock = asyncio.Lock()

        # Merge locks for shared state/mask registers
        self._merge_locks: dict[int, asyncio.Lock] = {
            0x3604: asyncio.Lock(),  # charging state + charge_time_enable mask
            0x3605: asyncio.Lock(),  # discharging state + discharge_time_enable mask
        }

        # Read-modify-write locks for non-merge-locked registers.
        # OrderedDict enables LRU eviction: oldest (front) entry is dropped first.
        self._rmw_locks: OrderedDict[int, asyncio.Lock] = OrderedDict()
        self._rmw_locks_last_access: dict[int, float] = {}
        self._rmw_lock_ttl: float = 3600.0  # 1 hour TTL
        self._rmw_dict_lock = asyncio.Lock()

        # DEDICATED WRITE LOCK: Write operations have priority over read operations.
        self._write_lock = asyncio.Lock()
        self._write_done = asyncio.Event()
        self._write_done.set()
        self._ultra_fast_pending = False

        self.inverter_data: dict[str, Any] = {}
        self.updating_settings = False
        self._data_lock = asyncio.Lock()

    def _init_fast_poll_state(self) -> None:
        """Initialise fast/ultra-fast polling callback handles and listener registry."""
        self._fast_unsub = None
        self._cancel_fast_update = None
        self._cancel_ultra_fast_update = None
        self._pending_fast_start_cancel: Callable | None = None
        self._pending_ultra_fast_start_cancel: Callable | None = None
        self._cache_cleanup_unsub = None
        self._fast_listeners: set[Callable[[], None]] = set()
        self._fast_poll_sensor_keys = FAST_POLL_SENSORS

        self._inverter_static_data: dict[str, Any] | None = None
        self._inverter_static_data_loaded_at: float | None = None
        self._warned_missing_states: bool = False

    def _init_charge_control(self, use_ha_mqtt: bool) -> None:
        """Initialise charge/discharge control handler, setters and cache cleanup timer."""
        self._pending_charging_state = None
        self._pending_discharging_state = None
        self._pending_passive_mode_state = None
        self._setting_handler = ChargeSettingHandler(self)
        self.use_ha_mqtt = use_ha_mqtt

        self._init_setters()

        self._cache_cleanup_unsub = async_track_time_interval(
            self.hass,
            self._async_cleanup_cache,
            timedelta(seconds=300),
        )

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

    def _set_power_state(
        self, value: bool | int | None, state_attr: str, handler_method: str
    ) -> None:
        """Set a power state with pending flag and trigger processing."""
        setattr(self, f"_pending_{state_attr}", value)
        self.async_set_updated_data(self.inverter_data)
        getattr(self._setting_handler, handler_method)(value)
        create_logged_task(self.hass, self.process_pending_now(), logger=_LOGGER)

    async def _set_charging_state(self, value: bool) -> None:
        self._set_power_state(value, "charging_state", "set_charging_state")

    async def _set_discharging_state(self, value: bool) -> None:
        self._set_power_state(value, "discharging_state", "set_discharging_state")

    async def _set_passive_mode(self, value: int | None) -> None:
        self._set_power_state(value, "passive_mode_state", "set_passive_mode")

    async def process_pending_now(self) -> None:
        """Immediately process pending settings."""
        try:
            await self._setting_handler.process_pending()
        except Exception as e:
            _LOGGER.error("Immediate pending processing failed: %s", e)

    # --- COORDINATOR METHODS ---

    async def _async_update_data(self) -> dict[str, Any]:
        """Regular poll cycle (slow)."""
        try:
            client = await self.connection.get_client()  # Ensure connected

            await self._setting_handler.process_pending()

            cache = await self._run_reader_methods(client)
            async with self._data_lock:
                self.inverter_data = cache

            if self.mqtt.publish_all and self.inverter_data:
                # Prevent duplicate MQTT publishing by excluding fast-poll sensors
                # from the slow loop if they are already handled by fast/ultra-fast loops.
                if self.fast_enabled or self.ultra_fast_enabled:
                    publish_cache = {
                        k: v for k, v in self.inverter_data.items()
                        if k not in self._fast_poll_sensor_keys
                    }
                else:
                    publish_cache = self.inverter_data
                if publish_cache:
                    await self.mqtt.publish_data(publish_cache)

            return self.inverter_data
        except (ConnectionError, ReconnectionNeededError) as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except Exception as err:
            _LOGGER.error("Update cycle failed: %s", err)
            raise UpdateFailed(f"Update cycle failed: {err}") from err

    async def _run_reader_methods(self, client: Any) -> dict[str, Any]:
        """Executes all readers using the provided client."""
        # Activate the per-instance circuit breaker for the entire read session.
        # All downstream try_read_registers() calls pick this up via the ContextVar.
        cb_token = _CIRCUIT_BREAKER_CTX.set(self.connection.circuit_breaker)
        try:
            new_cache: dict[str, Any] = {}

            # Load Static Data – refresh after TTL expires (default 1 h).
            _static_expired = (
                self._inverter_static_data_loaded_at is None
                or (time.monotonic() - self._inverter_static_data_loaded_at)
                > _STATIC_DATA_TTL
            )
            if _static_expired:
                try:
                    self._inverter_static_data = (
                        await modbus_readers.read_modbus_inverter_data(
                            client, self._read_lock
                        )
                    )
                    self._inverter_static_data_loaded_at = time.monotonic()
                except Exception as e:
                    _LOGGER.error("Failed to load static data: %s", e)
                    self._inverter_static_data = {}
                    self._inverter_static_data_loaded_at = time.monotonic()

            if self._inverter_static_data:
                new_cache.update(self._inverter_static_data)

            for group in _READER_GROUPS:
                for method in group:
                    try:
                        res = await method(client, self._read_lock)
                        if isinstance(res, dict):
                            new_cache.update(res)
                    except ReconnectionNeededError:
                        await self.connection.notify_error()
                        await self.connection.reconnect()
                        raise
                    except Exception as e:
                        _LOGGER.warning("Reader %s error: %s", method.__name__, e)

            return new_cache
        finally:
            _CIRCUIT_BREAKER_CTX.reset(cb_token)

    # --- FAST POLLING ---

    @callback
    def _start_update_loop(
        self, interval: int, cancel_attr: str, ultra: bool = False
    ) -> None:
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

        setattr(
            self,
            cancel_attr,
            async_track_time_interval(self.hass, runner, timedelta(seconds=interval)),
        )

    @callback
    def _schedule_update_loop(
        self, interval: int, cancel_attr: str, ultra: bool = False
    ) -> None:
        """Schedule an update loop robustly based on HA startup state."""
        pending_attr = (
            "_pending_ultra_fast_start_cancel"
            if cancel_attr == "_cancel_ultra_fast_update"
            else "_pending_fast_start_cancel"
        )

        # Replace any existing pending handle for the same loop
        pending_handle = getattr(self, pending_attr, None)
        if pending_handle:
            pending_handle()

        is_running = (
            self.hass.state == CoreState.running
            if hasattr(CoreState, "running")
            else False
        )

        if not is_running:
            _LOGGER.debug("HA not fully started, delaying %s loop", cancel_attr)
            cancel_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                lambda _: self._start_update_loop(interval, cancel_attr, ultra)
            )
            setattr(self, pending_attr, cancel_listener)
        else:
            setattr(
                self,
                pending_attr,
                async_call_later(
                    self.hass,
                    STARTUP_DELAY_RUNNING,
                    lambda _: self._start_update_loop(interval, cancel_attr, ultra),
                ),
            )

    async def start_fast_updates(self) -> None:
        """Start fast update loops based on configuration."""
        # Start the 10s Fast Loop only when Ultra is disabled
        if self.fast_enabled and not self.ultra_fast_enabled:
            if self._cancel_fast_update:
                self._cancel_fast_update()
                self._cancel_fast_update = None
            if self._pending_fast_start_cancel:
                self._pending_fast_start_cancel()
                self._pending_fast_start_cancel = None

            self._schedule_update_loop(
                FAST_UPDATE_INTERVAL, "_cancel_fast_update", False
            )
        else:
            if self._cancel_fast_update:
                self._cancel_fast_update()
                self._cancel_fast_update = None
            if self._pending_fast_start_cancel:
                self._pending_fast_start_cancel()
                self._pending_fast_start_cancel = None

        # Start the 1s Ultra Loop independently if enabled
        if self.ultra_fast_enabled:
            if self._cancel_ultra_fast_update:
                self._cancel_ultra_fast_update()
                self._cancel_ultra_fast_update = None
            if self._pending_ultra_fast_start_cancel:
                self._pending_ultra_fast_start_cancel()
                self._pending_ultra_fast_start_cancel = None

            self._schedule_update_loop(
                ULTRA_FAST_UPDATE_INTERVAL, "_cancel_ultra_fast_update", True
            )

    async def _run_fast_modbus_read(
        self, client: Any, lock: asyncio.Lock, ultra: bool
    ) -> dict[str, Any] | None:
        """Execute Modbus read with one-shot retry for fast poll cycle.

        Returns the raw result dict, an empty dict if the device returned
        nothing, or None if both the initial attempt and the retry failed
        (already logged; caller should skip the update cycle).
        ReconnectionNeededError is always re-raised for hub-level handling.
        """
        for attempt in (1, 2):
            try:
                if ultra:
                    return await modbus_readers.read_additional_modbus_data_1_part_2(
                        client, lock
                    )
                part_1 = await modbus_readers.read_additional_modbus_data_1_part_1(
                    client, lock
                )
                part_2 = await modbus_readers.read_additional_modbus_data_1_part_2(
                    client, lock
                )
                return {**part_1, **part_2}
            except ReconnectionNeededError:
                raise
            except Exception as e:
                if attempt == 1:
                    _LOGGER.debug("Fast poll failed, attempting one retry: %s", e)
                else:
                    _LOGGER.debug(
                        "Ultra-fast poll retry failed, skipping update cycle: %s", e
                    )
                    return None

    async def _publish_fast_mqtt(self, fast_data: dict[str, Any]) -> None:
        """Publish fast-poll sensor values to MQTT."""
        await self.mqtt.publish_data(fast_data)

    def _notify_fast_listeners(self) -> None:
        """Notify HA entity listeners about updated fast-poll sensor data.

        Only called from the 10 s loop – not from ultra-fast (1 s) mode –
        to avoid flooding the HA recorder database.
        """
        for listener in tuple(self._fast_listeners):
            listener()

    async def _async_update_fast(self, now=None, ultra: bool = False) -> None:
        """Perform fast update of sensor data with performance optimizations.

        PERFORMANCE OPTIMIZATIONS:
        1. Separate locks for ultra fast vs fast modes - reduces lock contention
        2. Skip ultra-fast update if write operation is in progress
        """
        if not self.fast_enabled and not ultra:
            return

        # Immediately skip ultra-fast update if a write operation is in progress.
        # No wait: the write may take longer than the 1s poll interval, and
        # blocking here would throw off the entire ultra-fast schedule.
        # The pending flag ensures a catch-up update is triggered after the write.
        if ultra and not self._write_done.is_set():
            _LOGGER.debug("Skipping ultra-fast update - write operation in progress")
            return

        try:
            client = await self.connection.get_client()

            # TOCTOU guard: a write may have started while we awaited get_client().
            # Re-check _write_done before touching the Modbus socket.
            if ultra and not self._write_done.is_set():
                _LOGGER.debug(
                    "Skipping ultra-fast update after get_client – write in progress"
                )
                return

            # PERFORMANCE OPTIMIZATION: Use dedicated single lock for all reads.
            lock = self._read_lock
            lock_name = "fast_read"

            # Activate per-instance circuit breaker for this fast-poll read session.
            cb_token = _CIRCUIT_BREAKER_CTX.set(self.connection.circuit_breaker)
            try:
                async with self._lock_order_guard(lock_name):
                    result = await self._run_fast_modbus_read(client, lock, ultra)
                    if result is None:
                        return  # both attempts failed, already logged

                    if not result:
                        _LOGGER.warning(
                            "Fast poll returned an empty result – skipping update cycle"
                        )
                        return

                    fast_data = {
                        k: v
                        for k, v in result.items()
                        if k in self._fast_poll_sensor_keys
                    }
                    if not fast_data:
                        _LOGGER.warning(
                            "Fast poll: result contained no matching sensor keys "
                            "(got %d raw keys, 0 matched FAST_POLL_SENSORS)",
                            len(result),
                        )
                        return

                    async with self._data_lock:
                        self.inverter_data.update(fast_data)

                    await self._publish_fast_mqtt(fast_data)

                    # Only the 10s loop should push to HA entities to avoid DB spam.
                    if not ultra:
                        self._notify_fast_listeners()
            finally:
                _CIRCUIT_BREAKER_CTX.reset(cb_token)

        except ReconnectionNeededError:
            await self.connection.notify_error()
            await self.connection.reconnect()
        except Exception as e:
            _LOGGER.warning("Fast update failed: %s", e)

    @callback
    def async_add_fast_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        self._fast_listeners.add(update_callback)

        @callback
        def remove_listener() -> None:
            self._fast_listeners.discard(update_callback)

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
        mqtt_topic_prefix: str | None = None,
        mqtt_publish_all: bool = False,
        use_ha_mqtt: bool = False,
    ) -> None:
        """Update connection settings. Full signature restored to support positional arguments."""
        if self.updating_settings:
            return
        self.updating_settings = True
        try:
            # Update Services
            self.connection.update_config(host, port)

            # Restart cache-cleanup timer so it fires relative to the new config change,
            # not from whenever the integration was first set up.
            if self._cache_cleanup_unsub:
                self._cache_cleanup_unsub()
            self._cache_cleanup_unsub = async_track_time_interval(
                self.hass,
                self._async_cleanup_cache,
                timedelta(seconds=300),
            )

            # FAILSAFE: If prefix argument is None (because __init__.py didn't pass it),
            # retrieve it from the ConfigEntry options/data directly.
            if mqtt_topic_prefix is None:
                mqtt_topic_prefix = self._config_entry.options.get(
                    CONF_MQTT_TOPIC_PREFIX,
                    self._config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "saj"),
                )

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
            new_interval = timedelta(seconds=int(scan_interval))
            if self.update_interval != new_interval:
                old_seconds = None
                try:
                    old_seconds = (
                        int(self.update_interval.total_seconds())
                        if self.update_interval
                        else None
                    )
                except Exception:
                    old_seconds = None

                self.update_interval = new_interval
                _LOGGER.info(
                    "Updating scan interval: %s -> %ss", old_seconds, int(scan_interval)
                )

                # DataUpdateCoordinator does not guarantee automatic rescheduling when
                # update_interval changes. Reschedule explicitly so Options changes take effect.
                try:
                    unsub = getattr(self, "_unsub_refresh", None)
                    if unsub:
                        unsub()
                    schedule = getattr(self, "_schedule_refresh", None)
                    if callable(schedule):
                        schedule()
                except Exception as e:
                    _LOGGER.debug(
                        "Failed to reschedule coordinator after interval change: %s", e
                    )

            self.fast_enabled = fast_enabled
            self.ultra_fast_enabled = ultra_fast_enabled
            self.use_ha_mqtt = use_ha_mqtt

            # Restart Fast Loop (Stop everything first, then restart based on flags)
            self._cleanup_fast_update_callbacks()

            # Start loops independently based on flags
            if self.fast_enabled or self.ultra_fast_enabled:
                await self.start_fast_updates()

            # Apply config changes immediately (and prime next refresh scheduling)
            await self.async_request_refresh()

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
        if self._cache_cleanup_unsub:
            try:
                self._cache_cleanup_unsub()
            except Exception as e:
                _LOGGER.debug("Error during cache cleanup unsub: %s", e)
            finally:
                self._cache_cleanup_unsub = None
        try:
            self.mqtt.stop()
        except Exception as e:
            _LOGGER.debug("Error during MQTT stop: %s", e)
        try:
            await self._setting_handler.shutdown()
        except Exception as e:
            _LOGGER.debug("Error during setting handler shutdown: %s", e)
        await self.connection.close()
        self._fast_listeners.clear()

    async def _cleanup_rmw_locks(self) -> None:
        """Clean up stale RMW locks (idle > TTL)."""
        now = time.monotonic()
        async with self._rmw_dict_lock:
            # Phase 1: TTL expired locks
            stale = [
                addr
                for addr, last_access in self._rmw_locks_last_access.items()
                if now - last_access > self._rmw_lock_ttl
            ]
            for addr in stale:
                if addr in self._rmw_locks:
                    del self._rmw_locks[addr]
                    del self._rmw_locks_last_access[addr]
                    _LOGGER.debug("Cleaned up stale RMW lock for 0x%04x (TTL)", addr)

            # Phase 2: Capacity check
            if len(self._rmw_locks) >= 64:
                # Evict oldest
                evict_addr = next(iter(self._rmw_locks))
                del self._rmw_locks[evict_addr]
                if evict_addr in self._rmw_locks_last_access:
                    del self._rmw_locks_last_access[evict_addr]
                _LOGGER.warning(
                    "RMW cache at capacity, evicted LRU lock for 0x%04x", evict_addr
                )

    async def _async_cleanup_cache(self, now=None) -> None:
        """Periodically clean up stale connection cache entries."""
        await self.connection.cleanup_cache()
        await self._cleanup_rmw_locks()

    @asynccontextmanager
    async def _lock_order_guard(self, name: str):
        """Track lock ordering to detect potential deadlocks in nested paths."""
        stack = _LOCK_STACK.get()
        if stack:
            prev = stack[-1]
            if _LOCK_ORDER.get(name, 99) < _LOCK_ORDER.get(prev, 99):
                _LOGGER.warning(
                    "Lock order warning: acquiring %s after %s (stack=%s)",
                    name,
                    prev,
                    "->".join(stack),
                )
        token = _LOCK_STACK.set((*stack, name))
        try:
            yield
        finally:
            _LOCK_STACK.reset(token)

    # --- HELPERS ---

    async def _write_register(
        self, address: int, value: int, *, allow_merge_locked: bool = False
    ) -> bool:
        """
        Helper for charge_control.py to write via connection service.

        Uses dedicated write lock with priority over read operations.
        """
        if not allow_merge_locked and address in self._merge_locks:
            raise ValueError(
                f"Direct write to merge-locked register 0x{address:04x} is not allowed; use merge_write_register()."
            )

        # Atomar: write_done löschen + ultra_fast_pending setzen
        async with self._write_lock:
            self._write_done.clear()
            self._ultra_fast_pending = True

        try:
            async with self._lock_order_guard("write"):
                client = await self.connection.get_client()
                return await try_write_registers(
                    client, self._write_lock, 1, address, value
                )
        finally:
            self._write_done.set()
            if self.ultra_fast_enabled and self._ultra_fast_pending:
                self._ultra_fast_pending = False
                create_logged_task(
                    self.hass, self._async_update_fast(ultra=True), logger=_LOGGER
                )

    async def _read_registers(self, address: int, count: int) -> list[int]:
        """
        Helper for charge_control.py to read via connection service.

        Waits for any pending write operation before reading.
        """
        # Wait for any pending write operation – bounded to prevent infinite hang
        # if _write_done is accidentally never set (defensive timeout).
        try:
            await asyncio.wait_for(self._write_done.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            _LOGGER.error(
                "_read_registers: _write_done not set after 15 s – "
                "write operation appears stuck. Resetting write state to prevent deadlock."
            )
            self._write_done.set()
            raise RuntimeError(
                "_read_registers: _write_done not set after 15 s – "
                "write operation appears stuck"
            )

        async with self._lock_order_guard("slow"):
            client = await self.connection.get_client()
            cb_token = _CIRCUIT_BREAKER_CTX.set(self.connection.circuit_breaker)
            try:
                return await try_read_registers(
                    client, self._read_lock, 1, address, count
                )
            finally:
                _CIRCUIT_BREAKER_CTX.reset(cb_token)

    async def merge_write_register(
        self,
        address: int,
        modifier: Callable[[int], int],
        label: str = "merge write",
    ) -> tuple[bool, int]:
        """Read-modify-write with per-register lock to preserve shared bits."""
        async with self._lock_order_guard("merge"):
            lock = self._merge_locks.get(address)
            if lock is None:
                async with self._rmw_dict_lock:
                    if address not in self._rmw_locks:
                        # Hard LRU cap: always evict the oldest entry before adding a new one.
                        # Should never exceed ~20 entries in normal operation.
                        if len(self._rmw_locks) >= 64:
                            evict_addr = next(iter(self._rmw_locks))
                            del self._rmw_locks[evict_addr]
                            if evict_addr in self._rmw_locks_last_access:
                                del self._rmw_locks_last_access[evict_addr]
                            _LOGGER.warning(
                                "merge_write_register: evicted RMW lock for 0x%04x "
                                "(LRU, capacity=64)",
                                evict_addr,
                            )
                        self._rmw_locks[address] = asyncio.Lock()
                    # Move to end so this entry is considered most-recently-used.
                    self._rmw_locks.move_to_end(address)
                    self._rmw_locks_last_access[address] = time.monotonic()
                lock = self._rmw_locks[address]
            async with lock:
                current_regs = await self._read_registers(address, 1)
                if not current_regs:
                    return False, 0
                current = current_regs[0]
                new_val = modifier(current)
                if new_val == current:
                    return True, current
                ok = await self._write_register(
                    address, new_val, allow_merge_locked=True
                )
                if ok:
                    _LOGGER.debug(
                        "%s: wrote merged value %s to 0x%04x", label, new_val, address
                    )
                    return True, new_val
                return False, current
