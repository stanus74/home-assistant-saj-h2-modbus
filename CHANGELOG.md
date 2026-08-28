## v3.1.0

> **Stability release:** Closes three separate paths that could silently stop polling —
> the integration would go completely quiet, with no log output, until it was manually
> reloaded (issue #197). Also fixes a race in the settings write queue, makes ultra-fast
> MQTT actually deliver its 1-second resolution, and makes degraded devices visible in
> the log instead of silently dropping whole groups of sensors.


### Fixed

#### Polling stability

- **Ultra-Fast Alone Now Survives a Restart:** Enabling only Ultra-Fast, without also enabling Fast, is the sensible setup for anyone consuming the live data over MQTT — Ultra-Fast publishes to MQTT and deliberately does not update the 10-second Fast entities. But at startup the integration only checked the Fast option, so the 1-second loop never started and no MQTT data arrived until the options were saved again. It then worked until the next restart, when it silently stopped again. Both options are now checked at startup, matching what saving the options already did.
- **Polling No Longer Stops Silently (#197):** If a Modbus operation stalled — most commonly a connect against an unresponsive communication module, which pymodbus performs without any timeout of its own — the poll cycle never returned. Home Assistant's coordinator does not impose a timeout on an integration's update method, so it waited on that cycle forever: no further refresh was ever scheduled and nothing at all was logged. Polling stayed dead until the integration was manually reloaded, in one report for over 10 hours. Connect attempts are now capped at 10 seconds and the whole poll cycle is bounded, so a stalled cycle fails visibly and the next one runs as normal.
- **A Single Bad Poll No Longer Blanks Every Sensor (#197):** The integration replaced its entire data cache with each poll cycle's result. If one cycle came back with little or nothing — likely when several register blocks are unsupported and already excluded — every other sensor lost its value and showed as `unknown`, while the update still counted as successful so the entities stayed "available". Cycle results are now merged into the cache, so a degraded cycle leaves previously known values intact. Values belonging to a register block that gets permanently disabled are dropped explicitly, so nothing keeps displaying a frozen reading.
- **Changing the Scan Interval Can No Longer Stop Polling (#197):** When the scan interval was changed in the options, the integration cancelled the coordinator's refresh timer and then scheduled a new one. If that second step failed, polling was left with no timer at all — the integration went quiet until it was reloaded, and the only trace was a debug message invisible at normal log levels. The manual cancellation is gone (Home Assistant's scheduler already replaces the timer itself), so the window no longer exists, and any failure is now logged as an error.

#### Settings writes

- **Enabling a Slot No Longer Discards Your Operating Mode:** Activating a charge or discharge slot switches the inverter to App Mode 1 (Time of Use), which is intended — slots only take effect in that mode. But clearing the last slot again always dropped the inverter to App Mode 0 (Self Consumption), whatever mode had been selected before. Anyone running e.g. Peak Shaving who briefly enabled a slot was silently moved to Self Consumption and had to notice and set the mode back by hand. The previously selected mode is now remembered when slots take over and restored when the last one is cleared; Self Consumption remains the fallback when there is nothing to restore. Passive Mode keeps its own precedence and its existing restore path.
- **No More Concurrent Command Queue Workers:** Settings writes are serialized through a single command queue worker, but `process_pending()` — called on every 60-second poll — checked the "worker already running" flag without holding the queue lock. If that check happened to interleave with a write triggered from an entity, a second worker could start and drain the same queue in parallel. Two workers issuing read-modify-write sequences at the same time could clobber each other on the shared charge/discharge registers (`0x3604`/`0x3605`), so a slot enable/disable could silently get lost. Worker startup now happens in one place under the queue lock, and the worker task is always tracked so it is reliably cancelled on unload.
- **Settings Writes No Longer Wait Behind a Full Poll Cycle:** The 60-second poll now waits for any in-flight register write to finish before it starts reading, which the 1-second ultra-fast loop and the read-modify-write path already did. Previously a poll could start mid-write and refresh the cached inverter data with pre-write values, so a following read-modify-write operation read a stale value as "current" — and writes triggered from the UI could be delayed by the length of a poll cycle.
- **App Mode 10 (Peak Shaving) Allowed Again:** `number.saj_app_mode` had its allowed values locked down in v2.8.6 to `[0, 1, 2, 3, 12]` to block undefined intermediate values, but this accidentally also blocked the valid and documented mode `10` (Peak Shaving Mode). It is now back in the whitelist.

#### MQTT

- **Ultra-Fast Mode Now Actually Publishes Every Second:** MQTT publishing throttled repeat values of the same key to one every 2 seconds — but ultra-fast polling reads every 1 second, so every second update was silently discarded and topics only refreshed every 2-3 seconds. The rate limit now follows the poll mode (0.5 s with ultra-fast enabled, 2 s otherwise), so ultra-fast delivers the resolution it promises. Behaviour in the 10-second and 60-second modes is unchanged.
- **MQTT Topics No Longer Vanish After Restart:** Sensor values are now published with the MQTT `retain` flag set, so the broker keeps the last known value for each topic. Previously, if no publisher (Realtime/Ultra-Fast polling or "Publish all sensors") ran again after a Home Assistant restart, the whole `saj` topic tree stayed empty until a value was published again.

#### Entities

- **Number and Time Inputs Now Initialize from Live Inverter Data:** After a Home Assistant restart, writable Number and Text entities for charge/discharge settings used to show hard-coded default values until the next 60-second poll refreshed them. They now read their current value from the hub cache as soon as the entity is added, so the UI reflects the inverter's actual state immediately.
- **Device Info Shows Firmware and Hardware Versions:** The SAJ device page now displays the inverter's software and hardware versions (read from the static inverter data after the first successful refresh) and a model hint.
- **Reduced Database Writes for Power Sensors:** Power and apparent-power sensors no longer use `force_update=True`, so Home Assistant only records a state change when the value actually changes instead of writing every 10-second fast-poll tick to the database.
- **Defensive Circuit Breaker Context Reset:** The ContextVar that routes each Modbus call to the correct per-instance circuit breaker is now reset defensively. If a task is cancelled during cleanup, the reset no longer raises an unhandled exception.

### Changed

- **Switch Names No Longer Repeat the Device Name:** The four control switches built their name as `"<device> <label>"` while Home Assistant prefixed the device name again, so the UI showed entries like *SAJ H2 SAJ H2 Charging Control*. They now use `has_entity_name`, matching how the sensors already worked, and display as *Charging Control*, *Discharging Control*, *Passive Charge Control* and *Passive Discharge Control* under the device. **Only the displayed names change** — `unique_id` and `entity_id` are untouched, so existing automations, scripts and dashboards keep working. Anything that referenced a switch by its friendly name will need updating.
- **Disabled Register Blocks Are Now Reported Regularly (#197):** When a register block turns out to be unsupported by the inverter's firmware, it is excluded from polling and logged once. After that there was no trace of it at all, so a partially degraded device looked completely healthy in the log while entire groups of sensors silently stopped updating. The integration now logs a summary of all currently excluded blocks once an hour.

### Code Quality

- **Single Owner for the Pending-Write Flag:** Flipping a charging, discharging or passive switch set the `_pending_<x>_state` attribute in the hub and then again in the settings handler, with the same value, and additionally spawned a task to start the queue worker that `queue_command()` already starts on its own since the queue fix in this release. Both duplicates are gone; the handler is now the single writer of the flag and runs before the state push, so the switch's `pending_write` attribute is set the moment Home Assistant reads it.
- **One Source of Truth for Config Keys:** Four configuration keys (`ultra_fast_enabled`, `mqtt_topic_prefix`, `mqtt_publish_all`, `use_ha_mqtt`) were defined as identical string literals in both `const.py` and `config_flow.py`, and two of them a third time in `services.py` where nothing used them. Renaming a key in `const.py` would silently not have reached the config flow, so an option could stop taking effect with no error anywhere. The config flow now imports these from `const.py`, and the unused pair in `services.py` is gone along with a stale comment claiming an import cycle that never existed.
- **Consistent Future Annotations:** Added `from __future__ import annotations` to `const.py`, `config_flow.py`, `sensor.py`, `text.py`, and `utils.py` for consistent forward-reference handling and modern type annotations across the integration.
- **Removed a Dead Cache Write on Slot Time Changes:** After writing a charge/discharge slot start or end time, the handler stored the new value in the hub cache under a key (`charge1_start`) that no reader, sensor or entity ever reads. The entry had no effect and is gone. The writable time entities are input fields; the inverter's actual slot times are shown by the corresponding sensors, which the reader refreshes on the next poll.
- **Fast-Poll Listener Active Flag Renamed:** The internal `_is_removed_event` flag in `sensor.py` was inverted (`set()` meant "active"). It is now named `_is_active` and its semantics are explicit, making the cleanup path easier to follow and reducing the chance of mis-reading the listener state.

---

## v3.0.0

> **Home Assistant 2026 readiness:** This release brings the integration in line with the current
> Home Assistant integration requirements (2026) — optional MQTT via `after_dependencies`, explicit
> `integration_type`, a modernized options flow, config-entry `runtime_data`, and the current
> config-entry entity callbacks — without changing any entity IDs, so existing automations and
> dashboards keep working.

### Added New Sensors

- **Inverter/Battery Setpoint Registers (0x4023-0x4030):** New reader `read_inverter_settings_data` exposes previously unread registers as sensors: `InvDisPowerSet`, `InvChgPowerSet`, `BatDisCurrSet`, `BatChgCurrSet`, `BatStatusDisp`, `BatProtocolSet`, `BatChgSocUpLimit`, `BatDisSocDowLimit`, `BatDODSet`, `BatResSoc`, and `MeterModeSet`. These closed a previously unread gap between `realtime_data` (ending at `0x4016`) and `additional_data_4` (starting at `0x4031`). `BatDisCurrSet` (`0x4025`) and `BatChgCurrSet` (`0x4026`) 

### Added
- **Daily Exclusion-List Auto-Reset:** Unsupported register block exclusions now reset automatically every 24 hours. This allows firmware updates (e.g. overnight) to take effect without requiring an HA restart, and prevents permanent blocking of registers that may be added in future updates.

### Improved

- **Register Block Exclusion Resilience:** The permanent exclusion mechanism for unsupported register blocks (e.g. `additional_data_3_2` on certain H1/H2 hardware) is now more resilient to firmware updates and temporary network issues. Blocks are re-tested daily instead of remaining excluded until HA restarts.


### Fixed

- **MQTT Is Now an Optional Dependency:** `mqtt` was declared as a hard `dependencies` entry in the manifest, which forced Home Assistant's MQTT integration to be set up before this integration could load — even though MQTT here is entirely optional (internal Paho client, HA MQTT, or none). It is now an `after_dependencies` entry, so the integration loads without HA MQTT configured and still switches to the HA MQTT strategy automatically once that integration loads later.

- **Inverter Card: Opening a Slot No Longer Activates It (v1.3.0):**
In the Lovelace card, expanding a charge/discharge slot to edit it is now separate from activating it. Clicking the slot header only expands/collapses the editor (no register write); the checkbox is a dedicated per-slot activation that writes the time-enable bit. Previously slots 2-7 wrote the enable bitmask the moment they were opened, a slot counted as "enabled" as soon as any of its time/power fields had a pending write, and activating another slot could clobber (deactivate) a just-activated slot because the new mask was based on the lagging sensor value. The enable state now reflects only the hardware bitmask (optimistically the pending activation write), and activation reads the last written mask to avoid lost updates.

- **MQTT Strategy No Longer Gets Stuck After a Config Change:**
The MQTT publisher's `stop()` used to detach its component-loaded listener, but it was also called on every strategy/config switch in `update_config`, not just on unload. Once detached, the publisher could no longer notice HA's MQTT integration loading later, so the strategy stayed stuck on `NONE`/`PAHO` until the integration was reloaded. Client shutdown and listener teardown are now split (`stop_paho()` vs. `stop()`); config switches only stop the Paho client and keep the listener alive, so switching to HA MQTT after a later load works again.

- **Editing a Charge/Discharge Slot No Longer Re-Enables It:** Previously, changing any field of a time slot (start/end time, day mask or power percent) unconditionally set that slot's bit in the `charge_time_enable`/`discharge_time_enable` bitmask. A slot the user had intentionally disabled reappeared as active whenever its values were adjusted. Slot edits now leave the enable bitmask untouched; enabling/disabling a slot is done solely through the dedicated time-enable entity.

- **Fast-Poll Sensors Ignored Disabled-by-Default Setting:** The fast variant of a fast-poll sensor forced `entity_registry_enabled_default = True`, so sensors that are disabled by default (or that the user intentionally disabled in their base description) reappeared as an enabled "Fast …" entity. Fast variants now inherit the base sensor's enabled-default.

- **Passive Battery Block Never Excluded on Unsupported Firmware:** `read_passive_battery_data` (register block `0x3636`) swallowed the internal `BlockUnsupportedError`, so on devices that do not serve this block the hub retried it every 60 s poll cycle and logged repeated errors indefinitely. The error is now propagated so the block is permanently excluded after 3 consecutive rejections (with daily re-test), consistent with all other register blocks.

- **Circuit Breaker Stuck in HALF_OPEN:**
Fixed a bug where the Modbus circuit breaker could remain permanently in the HALF_OPEN state if a recovery probe reached the device but raised a non-connection error (e.g. an unsupported register or IO error). In that case every subsequent Modbus call was rejected with "Circuit Breaker is HALF_OPEN (probe in progress)" until the integration was reloaded. The breaker now correctly closes when the probe proves the connection is healthy, letting the non-connection error propagate normally.

---

## v2.9.1

- **Permanent Block Exclusion for Unsupported Registers (Issues #177, #180, #183):** Register blocks that are not served by the device firmware (e.g. `additional_data_3_2` on SAJ H1 models and certain H2 hardware variants returning `ExceptionResponse` with code 65 or similar) are now automatically and permanently excluded from polling after 3 consecutive rejections. Previously, each poll wasted up to 10+ seconds on retries and filled the log with retry warnings before the circuit breaker opened and blanked all entities. Now: the first 3 rejections are logged at DEBUG level; on the 3rd, a single WARNING is emitted (`Block … permanently disabled: not supported by this device firmware`) and the block is skipped for the remainder of the session. No manual configuration or source-code edits required.
- **Non-retriable ExceptionResponse:** All `ExceptionResponse` codes returned by the device (except code 4 — "Slave Device Failure", which may be transient) are now treated as deterministic rejections and raise immediately without retrying. This eliminates the 3-attempt backoff loop (previously ~10 s) whenever a device signals an unsupported register.

### Performance & Architecture
- **Per-Inverter Reconnect Lock (Multi-Inverter)**: The in-retry reconnect handler used a module-level reconnect lock/event shared across every configured inverter, so a hanging reconnect on one device stalled reconnect handling for all of them. Reconnect now takes the per-connection socket lock instead, so each inverter recovers independently — and, because it is the same lock reads/writes use, the socket can no longer be closed under an in-flight operation.
- **Unified Modbus Socket Lock (Reads/Writes/Reconnect)**: Reads and writes previously used two independent locks, so a poll cycle and a register write could touch the same `AsyncModbusTcpClient` socket at the same time — pymodbus cannot serve concurrent operations on one TCP connection, which could mix up request/response pairs and corrupt entity values under load. A single per-connection socket lock (owned by the connection manager) now serialises all reads, writes and the hub-level reconnect, and the reconnect holds that lock while closing/re-opening the socket so it can no longer be torn down under an in-flight operation. Writer priority and the ultra-fast skip logic are unchanged.
- **Direct Writes to Packed Slot Registers Rejected**: Extended the read-modify-write guard in `hub._write_register` beyond the two merge-locked state/mask registers (`0x3604`/`0x3605`) to also cover all packed charge/discharge slot registers (day-mask in the high byte, power-percent in the low byte). A direct write to these would clobber the sibling field; such calls now raise instead, forcing the safe `merge_write_register` path. Defensive hardening — no current caller triggered this, and all legitimate merged writes are unaffected.
- **Lock Management & Deadlock Prevention**: Replaced `threading.Lock` with `asyncio.Lock` in `hub.py`. Eliminated potential deadlocks when using nested `_lock_order_guard` and `_write_lock` combinations in the read-modify-write path.
- **Entity State Updates (Fast-Poll)**: Overhauled `_cleanup_fast_listener` in `sensor.py` using a thread-safe `asyncio.Event` to eliminate race conditions and database-heavy double registrations during entity reloads.
- **UI Responsiveness (Dual-Debounce)**: Re-wrote optimistic UI state flushes in `charge_control.py`. Immediate UI confirmation happens after 200 ms (`_FIRST_FLUSH_DELAY`), while rapid sequential slides/clicks are throttled at 500 ms.
- **Queue Stall Prevention**: Capped the exponential backoff for failing Modbus writes in `charge_control.py` to a maximum of 2 seconds (with random jitter) instead of stalling the command queue for up to 7 seconds.
- **Cache Eviction Fix**: RMW-Lock cache limit (64 locks) logic is now completely robust, leveraging LRU and TTL sweeps combined to smoothly avoid infinite caching and silent eviction failures.
- **Startup Sync Tuning**: Fast-poll loops now explicitly wait for the `EVENT_HOMEASSISTANT_STARTED` event instead of static 30s delays, eliminating boot-sequence race conditions.

### Fixes & Code Quality
- **`AddConfigEntryEntitiesCallback`**: All entity platforms now type their add-entities callback as `AddConfigEntryEntitiesCallback`, the current config-entry-aware variant (no behavior change).
- **Config Entry `runtime_data`**: Per-entry state (the hub and its device info) is now stored in the typed `entry.runtime_data` instead of a manual `hass.data[DOMAIN][entry_id]` dictionary, following current Home Assistant conventions. No user-visible change; simplifies setup/unload and removes global bookkeeping.
- **Modernized Options Flow**: The options flow no longer uses the deprecated `OptionsFlowWithConfigEntry` base class and no longer receives the config entry via its constructor; it uses the `self.config_entry` property provided by Home Assistant (no behavior change).
- **Dropped Deprecated `CONNECTION_CLASS`**: Removed the obsolete `CONNECTION_CLASS` attribute from the config flow; the connection class is already conveyed by `iot_class` in the manifest (no behavior change).
- **Explicit `integration_type`**: The manifest now declares `"integration_type": "hub"` explicitly instead of relying on the default, as recommended by the Home Assistant integration spec (no behavior change).
- **Fast Coordinator Started After Platform Setup**: `start_fast_updates()` now runs after `async_forward_entry_setups` in `async_setup_entry`, so the fast/ultra-fast loop is only started once the entity platforms (and their fast listeners) are registered. Robustness hardening — the first tick was already ≥1 s in the future, so no behavior change in practice.
- **Modernized Type Annotations**: `modbus_readers.py` now uses `from __future__ import annotations` and builtin `dict`/`list` generics instead of `typing.Dict`/`typing.List`, aligning it with the rest of the integration (no behavior change).
- **Future Annotations in `switch.py`**: Added the missing `from __future__ import annotations` import to `switch.py` for consistency with the rest of the integration (no behavior change).
- **HA-Native Flush Scheduling**: The debounced UI state flush in `charge_control.py` now uses Home Assistant's `async_call_later` helper instead of the raw `hass.loop.call_later`/`call_soon` timers, so the scheduled callback is properly tracked and cancelled by HA's event system.
- **Module-Level `random` Import**: Moved the `random` import in `charge_control.py` out of the write-retry loop to module scope (minor cleanup, no behavior change).
- **Correct Fast-Update Debug Log**: The fast-poll debug log (`Fast update for … : old -> new`) printed the new value on both sides because the cached value was overwritten before logging. It now captures the previous value first and shows the real transition.
- **Removed Unused Switch Entity Registry**: The switch platform stored its entities in `hass.data[DOMAIN][entry.entry_id]["entities"]`, but nothing ever read that list. Removed the dead storage, which also prevented the list from growing across failed reloads.
- **Async Unload Robustness**: Wrapped each step in `async_unload_entry` in explicit `try/except` guards to ensure `connection.close()` executes even if tasks like `mqtt.stop()` crash, preventing socket memory leaks.
- **TOCTOU Race Condition**: Fixed a TOCTOU (Time-Of-Check to Time-Of-Use) loop evasion in `_async_update_fast`, ensuring ultra-fast callbacks reliably pause during write operations and catch up correctly via atomic lock flags.
- **Duplicate MQTT Publishing**: Mitigated a bug where fast-poll/ultra-fast sensors were accidentally pushed to the broker twice (once by the fast loop, once via 60s slow loop `mqtt_publish_all`).
- **Decoupling Global State**: Removed instance collision paths by stripping `ModbusGlobalConfig` singletons and pushing host/port contexts directly to the Modbus client objects.
- **API Modernization**: Switched deprecated `async_create_background_task` calls to the standard `async_create_task` HA Core API in `utils.py`.
- **Socket Tear-Down Handling**: Covered bare exceptions (`except Exception: pass`) with correct logger output to catch elusive connection termination errors during cache invalidations.



## Release v2.9.0 – Performance, Architecture & Entity Optimization

### Added

**`number.saj_tou_outside_mode_input` — Register 0x365F**
New writable number entity controlling the inverter mode outside TOU charge/discharge windows.
- `0` = Standby
- `1` = Self Use Mode

**`number.saj_time_bat_dis_input` — Register 0x3660**
New writable number entity to allow or block battery discharging during time-sharing periods.
- `0` = Not allow
- `1` = Allow

Both entities use `allowed_values = [0, 1]` validation and appear in HA under the Config entity category. Corresponding read-only sensor entities (`sensor.saj_tou_outside_mode`, `sensor.saj_time_bat_dis`) are added for dashboard display. Values are read via the existing 60 s `read_passive_battery_data` call (register block 0x3636, count extended from 39 to 43).


### Performance & Architecture
- **Native Asyncio for Modbus:** Eliminated `async_add_executor_job` wrappers for Modbus calls. Pymodbus calls are now executed natively, significantly reducing thread context-switching overhead and latency.
- **Lock Consolidation:** Consolidated redundant read locks into a single `_read_lock` since Modbus polling inherently runs sequentially on the same TCP connection.
- **RMW Lock Garbage Collection:** Added a 1-hour TTL garbage collection for Read-Modify-Write (RMW) locks in `hub.py`. Prevents memory leaks for rarely accessed UI configuration registers.
- **Entity Deduplication (Fast-Poll):** Fixed the creation of duplicate entities for high-frequency sensors. Now registers exactly one sensor entity per configure metric, automatically plugging into the fast-poll routine if enabled.
- **MQTT Rate-Limiting:** Introduced local timestamp tracking in `MqttPublisher` to prevent identical rapid-fire state updates from flooding the Home Assistant event bus in the 1-second ultra-fast mode.

### Stability & Fixes
- **ModbusClient Cache Safety:** Fixed a race condition inside `get_cached_client` by re-evaluating `_connection_healthy` inside the cache lock, eliminating the leakage of stale Modbus connection instances on network drops.
- **Circuit Breaker ModbusIOException:** The `ModbusCircuitBreaker` now properly captures `ModbusIOException`, triggering rate-limits upon Modbus protocol errors.
- **Entity Lifecycle Races:** Fixed double-cleanup bugs in `sensor.py` during plugin teardown utilizing an atomic `_is_removed_flag` boolean to squash double-writes.
- **Thread-safe LRU Eviction:** Fixed read-modify-write (RMW) lock rotation logic in `hub.py` to ensure active locks are never forcibly safely evicted from the LRU cache.
- **Code Quality:** Added full type annotations to `number.py`, stripped obsolete imports (F401), and moved module docstrings to valid module-level targets.

**RMW Lock LRU Eviction** (`hub.py`)
`_rmw_locks` (OrderedDict, cap=64) previously used a `for...else` loop that only evicted unlocked entries. If all entries were locked the dict grew to 65+ entries unboundedly. Now always evicts the oldest entry via `next(iter(...))`, with a WARNING log if the evicted entry was still locked.

**`asyncio.Event` for Removal Guards** (`sensor.py`)
`_is_removed` and `_on_remove_cleanup_registered` were plain `bool` flags, which are not safe in concurrent asyncio code. Both are now `asyncio.Event` objects — the standard Python pattern for inter-coroutine signalling. Eliminates a potential double-cleanup race condition on entity removal.

**Circuit Breaker for Write Operations** (`modbus_utils.py`)
`try_write_registers()` was not protected by the shared `ModbusCircuitBreaker`. Consecutive write failures could spin indefinitely without tripping the breaker. The write path is now wrapped identically to reads: `get_modbus_circuit_breaker().call(operation, should_trip=...)`.

**`_write_done.set()` Exception Safety** (`hub.py`)
The `finally` block of `_write_register()` called `self._write_done.set()` without any guard. An unexpected exception here would propagate out of `finally`, masking the original error. The call is now wrapped in `try/except Exception: pass`.

**`ReconnectionNeededError` Propagation on Reconnect Failure** (`modbus_utils.py`)
When `_on_modbus_retry()` failed to reconnect the Modbus client it only logged a warning and silently continued the backoff loop, so the caller never learned about the persistent connection problem. It now raises `ReconnectionNeededError` immediately, which is the correct signal for the hub to initiate a full reconnect cycle.

**Untracked `asyncio.create_task` Calls** (`charge_control.py`)
Two `asyncio.create_task(...)` calls in `_queue_command_async()` and `process_pending()` created fire-and-forget tasks whose exceptions were silently discarded. Both are replaced with `create_logged_task(self.hub.hass, ..., logger=_LOGGER)` so exceptions are caught and logged by the HA task infrastructure.

**ContextVar Token not Reset in `_async_update_fast` / `_read_registers`** (`hub.py`)
`_CIRCUIT_BREAKER_CTX.set(...)` was called without saving the returned token, making it impossible to restore the previous context value. In nested calls within the same asyncio Task the circuit breaker context was permanently overwritten. Both methods now follow the correct `cb_token = ctx.set(...); try: ...; finally: ctx.reset(cb_token)` pattern.

**MQTT Strategy not Re-evaluated after Late MQTT Load** (`services.py`)
`MqttPublisher._determine_strategy()` cached the selected strategy at startup. If the HA MQTT integration loaded after the SAJ integration (e.g. slow boot), the publisher stayed on the Paho fallback forever. The publisher now subscribes to `EVENT_COMPONENT_LOADED` and forces a strategy re-evaluation when the `mqtt` component becomes available.

**Cache-Cleanup Timer not Restarted on Config Change** (`hub.py`)
The Modbus connection cache cleanup timer (300 s TTL) was created once at startup and never restarted when connection settings changed via Options Flow. Stale cache entries from the old host/port could persist. `update_connection_settings()` now cancels and recreates the timer on every config update.

**`create_logged_task` Used Deprecated `async_create_task`** (`utils.py`)
`hass.async_create_task()` is deprecated since HA Core 2023.6. Migrated to `hass.async_create_background_task(coro, name=name)`. The optional `name` parameter is forwarded so tasks appear with a meaningful label in HA diagnostics.

**Redundant `get_client()` Call in `process_pending_now`** (`hub.py`)
`process_pending_now()` called `await self.connection.get_client()` before delegating to `process_pending()`. The connection is established lazily inside `_write_register → get_client()` anyway, so the pre-call was a no-op that added unnecessary overhead on every switch toggle.

---


## Release v2.8.6 – Code Quality & Refactoring

### Changed

**`number.saj_app_mode_input` now accepts value 12 (AI Saving)**
The `app_mode` number entity previously had `max: 3`, making it impossible to restore AI Saving mode (value 12) from Home Assistant after it was overwritten. The upper bound is now `max: 12`.

To prevent users from accidentally writing undefined intermediate values (4–11), an `allowed_values` whitelist `[0, 1, 2, 3, 12]` has been added. Attempts to set any value outside this list are rejected with an error log and leave the inverter unchanged. Automations that need to restore AI Saving mode can now set `number.saj_app_mode_input` to `12` directly.


**Grid Energy Sensors Enabled by Default**
`Sum All Phases Feed-In Total` (`sensor.saj_sum_all_phases_feed_in_total`) and `Sum All Phases Sell Total` (`sensor.saj_sum_all_phases_sell_total`) are now enabled by default (`enable: True`).

Both sensors are required for the Home Assistant Energy Dashboard:
- **Feed-In Total** → Grid Consumption (import from grid)
- **Sell Total** → Grid Export (feed into grid)

Previously users had to manually enable these entities after installation. Existing installations are unaffected (already-enabled or already-disabled states persist in the HA entity registry).

### Refactoring

**Lint Errors Eliminated**
All 40 Ruff lint errors resolved across 7 files: module-level docstring moved before `from __future__` in `hub.py` (21× E402), 8 unused imports removed (F401), undefined name `SAJModbusHub` in `__init__.py` fixed via `TYPE_CHECKING` block (F821), inline `if`/return statements split (E701), unused variable removed (F841).

**Legacy Typing Modernised**
Replaced `Optional[X]`, `Dict[K,V]`, `List[X]`, `Union[X,Y]` from `typing` with native Python 3.10+ builtins (`X | None`, `dict`, `list`, `X | Y`) in `hub.py`, `charge_control.py`, `modbus_utils.py` and `services.py`.

**Type Hints Added to `number.py`**
`number.py` was the only file with 0% type hint coverage. All 5 functions/methods now fully annotated including the HA platform signature (`HomeAssistant`, `ConfigEntry`, `AddEntitiesCallback`).

**Generic `CircuitBreaker` Base Class**
Extracted shared circuit breaker logic (~40 duplicate lines) into a single `CircuitBreaker` base class in `modbus_utils.py`. `ModbusCircuitBreaker` and `MqttCircuitBreaker` are now slim two-line subclasses with unchanged defaults and identical runtime behaviour. Also fixes an f-string log call to use `%s` format.

**`hub.__init__()` Split into Focused Helpers**
The 126-line `__init__` has been reduced to ~74 lines by extracting three private methods:
- `_init_locks()` — all `asyncio.Lock` / `Event` / `OrderedDict` objects
- `_init_fast_poll_state()` — fast/ultra-fast callback handles and listener registry
- `_init_charge_control()` — `ChargeSettingHandler`, pending states, setters, cache cleanup timer

**`DEFAULT_CONFIG_SCHEMA` Constant Extracted**
The 12-key config-defaults dict was duplicated verbatim in `hub.__init__()` and `async_update_options()` in `__init__.py` (with minor inconsistencies: raw strings vs. constants, `1883` vs. `DEFAULT_MQTT_PORT`). Both are now replaced by a single `DEFAULT_CONFIG_SCHEMA: dict[str, Any]` constant in `const.py`.
Also moved from `hub.py` to `const.py`: `CONF_ULTRA_FAST_ENABLED`, `CONF_MQTT_TOPIC_PREFIX`, `CONF_MQTT_PUBLISH_ALL`, `CONF_USE_HA_MQTT`, `DEFAULT_MQTT_PORT`, `DEFAULT_MQTT_TOPIC_PREFIX`. Removed local redefinitions of `DEFAULT_MODBUS_PORT` and `DEFAULT_SCAN_INTERVAL` that duplicated existing `const.py` values.

**`_determine_strategy()` Refactored into Pure Helpers**
Extracted two single-responsibility helpers from the 60-line strategy method in `services.py`:
- `_is_ha_mqtt_available()` — single source of truth for HA MQTT component check (was duplicated inline)
- `_select_strategy(clean_host)` — pure priority logic returning a strategy constant; no side-effects

`_determine_strategy()` now only handles caching, host normalisation, logging, and assignment. No behaviour changes.

**`_async_update_fast()` Split into Focused Helpers**
The 97-line monolithic fast-poll method has been refactored into three single-responsibility helpers:
- `_run_fast_modbus_read(client, lock, ultra)` — Modbus read with one-shot retry; returns `None` on double failure
- `_publish_fast_mqtt(fast_data)` — delegates MQTT publishing
- `_notify_fast_listeners()` — notifies HA entity callbacks (10 s loop only)

`_async_update_fast()` is now a lean ~45-line orchestrator. No behaviour changes.


---

## [v2.8.5]

## Stability & Code Quality

This version closes multiple potential data corruption and race condition issues and improves the robustness of the entire polling system.

### Key Fixes

**Data Corruption from Write/Read Conflicts Prevented**
A timeout while waiting for a write operation to complete previously allowed a Modbus read to start anyway – potentially while the socket was still occupied by a write. The read is now aborted instead of proceeding.

**Race Condition in Cache Updates Fixed**
`_update_cache()` in `charge_control.py` was writing to `inverter_data` without a lock. This could cause inconsistent states when slow or fast polls were running concurrently. All 7 call sites now use `_data_lock`.

**Double Reconnect in Fast Poll Removed**
Every error in fast poll was calling `reconnect()` twice – once internally and once in the outer handler. This behavior is now correct.

**TOCTOU Gap in Ultra-Fast/Write Conflict Closed**
A write could start exactly during `await get_client()` and occupy the socket. A second guard immediately after `get_client()` closes this timing window.

**Unhandled Background Task Errors Now Visible**
Exceptions in background tasks disappeared silently. New `create_logged_task()` helper logs all errors including full stack trace.

### Further Improvements

- **Static Inverter Data (Serial Number, Firmware) Refreshed Hourly** – Changes after a firmware update are picked up without HA restart
- **Per-Instance Circuit Breaker**: A failed inverter no longer blocks a second independently configured inverter
- **Connection Cache TTL** reduced: 60 s → 30 s, health-check interval 30 s → 5 s – silent disconnects are detected faster
- **LRU Limit for Internal RMW Locks** now enforced (previously only WARNING log)
- **Lock-Order Guard** now covers fast/ultra-fast polling – potential deadlocks are detected earlier

### Fixed
- **`_write_done` timeout raises instead of proceeding** (`hub.py`): `_read_registers()`
  caught `asyncio.TimeoutError` after the 5 s `_write_done` guard and silently continued
  with the Modbus read while a write might still be using the socket.
  Now raises `RuntimeError` instead, propagating the error to the caller so the read
  is cleanly aborted rather than risking a corrupted Modbus frame (F10).
- **Dead code removed** (`hub.py`, `modbus_utils.py`):
  - `hub.py`: `_process_reader_result()` was never called after the reader loop
    was refactored; method deleted (F14).
  - `modbus_utils.py`: `ensure_client_connected()` and `connect_if_needed()` were
    "backward compatibility wrappers" with no remaining callers; both functions
    and their section comment deleted (F14).

---

### Changed
- **`reader_groups` promoted to module constant** (`hub.py`): The 7-element reader-group
  list was re-created as a local variable on every 60 s slow-poll cycle.
  Moved to a module-level constant `_READER_GROUPS`; `_run_reader_methods()` now
  iterates the shared constant instead (F16).
- **Document `pv1Power`/`pv2Power` update frequency** (`hub.py`): Added a comment
  in `FAST_POLL_SENSORS` clarifying that these two keys are populated by
  `read_additional_modbus_data_1_part_1` (read in the 10 s fast loop) but not
  in the 1 s ultra-fast loop (which only reads `part_2`). They therefore update
  at 10 s in fast mode and at 60 s in ultra-fast mode (F17).
- **Lock-Order Guards for Fast/Ultra-Fast poll** (`hub.py`): `_async_update_fast()` lacked
  a `_lock_order_guard` context, so nested lock acquisitions in the fast/ultra-fast path
  were invisible to the deadlock-detection mechanism.
  Added `async with self._lock_order_guard("fast" | "ultra_fast")` wrapping the read
  and result-processing block, consistent with the existing `"slow"` guard in
  `_run_reader_methods()` and `"write"` guard in `_write_register()` (F8).
- **`_rmw_locks` hard LRU cap** (`hub.py`): The dynamic RMW lock dict was guarded only by
  a `WARNING` log when reaching 64 entries; the dict continued to grow unboundedly.
  Changed to `OrderedDict` and added LRU eviction: when the capacity limit is reached,
  the oldest unlocked entry is removed before inserting the new address.
  Every cache hit calls `move_to_end()` to track recency.
  If all 64 entries happen to be locked simultaneously, a `WARNING` is emitted instead
  of evicting an in-use lock (F7).
- **Static Inverter Data TTL** (`hub.py`): `_inverter_static_data` (serial number, firmware
  version, model) was loaded only once and held indefinitely. A `_STATIC_DATA_TTL = 3600 s`
  constant and a `_inverter_static_data_loaded_at` monotonic timestamp are introduced.
  The cache is now refreshed every hour, picking up firmware updates or inverter
  replacements without requiring a Home Assistant restart.
  On read failure the timestamp is still recorded, so the next retry is deferred by 1 h
  instead of hammering the bus every 60 s (F3).
- **Per-Instance Circuit Breaker** (`modbus_utils.py`, `services.py`, `hub.py`):  
  The global `_MODBUS_CIRCUIT_BREAKER` module singleton is replaced by a per-instance  
  `_circuit_breaker` member on `ModbusConnectionManager`.  
  A `ContextVar` (`_CIRCUIT_BREAKER_CTX`) propagates the active breaker through the  
  coroutine call chain (readers, `try_read_registers`) without changing all function  
  signatures. Hub.py sets the ContextVar at each read entry point (`_run_reader_methods`,  
  `_async_update_fast`, `_read_registers`).  
  Effect: a tripped breaker for one failing inverter no longer blocks reads/connects  
  for a second independently configured inverter (F13).
- **Connection Cache TTL optimised** (`modbus_utils.py`, `services.py`, `hub.py`):  
  Reduced `ConnectionCache` default TTL from 60 s to 30 s and health-check interval  
  from 30 s to 5 s for faster detection of silent disconnects.  
  Added `notify_error()` to `ConnectionCache` and `ModbusConnectionManager`: sets  
  `_cache_expiry = 0` immediately so concurrent tasks no longer receive the stale  
  cached client during the window between a read failure and `reconnect()` completing.  
  `hub.py` calls `notify_error()` before every `reconnect()` call (F5).


### Fixed
- **Cache Update Lock Safety** (`charge_control.py`): `_update_cache()` is now `async` and  
  always acquires `_data_lock` before writing to `inverter_data`; all 7 call sites updated.
  Direct dict write in `_set_app_mode` likewise wrapped in `_data_lock`.  
  Prevents race condition between write operations and the slow/fast poll loops (F11).
- **Double Reconnect in Fast Poll** (`hub.py`): v2.8.4 added `raise` in the inner
  `except ReconnectionNeededError` handlers, but the preceding `await reconnect()` call
  remained, causing a double-reconnect on every fast-poll error.
  These redundant `reconnect()` calls are now removed; only the outer handler reconnects (F12).
- **TOCTOU Write/Ultra-Fast Conflict** (`hub.py`): v2.8.4 added a `_write_done` check
  *before* `get_client()`. However, a write could still start during the `await get_client()`
  coroutine, leaving the socket exposed. A second guard immediately after
  `await get_client()` closes this race window (F19).
- **Unhandled Background Task Exceptions** (`utils.py`, `hub.py`, `services.py`):  
  Introduced `create_logged_task()` helper that wraps `hass.async_create_task()` with a  
  done-callback logging any unhandled exception (incl. full stack trace).  
  Replaced all 5 bare `async_create_task()` calls in `hub.py` and `services.py` (F18).
- **Silent Empty Fast Poll Results** (`hub.py`): Added `WARNING` log when the fast poll  
  returns an empty result dict, and a separate warning when none of the returned keys  
  match `FAST_POLL_SENSORS` (F4).

### Changed
- **Remove dead `CRITICAL_READER_GROUPS` code** (`hub.py`): The `if group_idx in CRITICAL_READER_GROUPS` /  
  `else` branches in `_run_reader_methods()` were identical; collapsed into a single loop.  
  `CRITICAL_READER_GROUPS` constant removed. Reader error log now includes `method.__name__` (F6/F15).


## [v2.8.4]

### Fixed
- **Modbus Circuit Breaker**: Add a shared circuit breaker for Modbus reads/connects to reduce repeated failure storms and improve recovery.
  - `modbus_utils.py`
  - `services.py`
- **Fast Cache Safety**: Protect inverter cache updates and fast listener iteration against concurrent access.
  - `hub.py`
- **Ultra-Fast Reconnect Handling**: Re-raise `ReconnectionNeededError` during fast poll retry path.
  - `hub.py`
- **Paho Circuit Breaker**: Route internal MQTT publishes through the circuit breaker.
  - `services.py`
- **Write-Done Timeout**: `_read_registers` now uses a bounded `asyncio.wait_for` (5 s) on `_write_done` instead of an unbounded wait, preventing a theoretical infinite hang on write cancellation.
  - `hub.py`
- **RMW Locks Bound Guard**: `merge_write_register` logs a WARNING when `_rmw_locks` exceeds 64 entries to surface unexpected register iteration bugs.
  - `hub.py`
- **Connection Cache Race**: Serialize client cache access to avoid stale Modbus clients under concurrent load.
  - `services.py`
- **Write/Read Coordination**: Ultra-fast polling waits for writes and schedules a catch-up update; reads no longer busy-wait.
  - `hub.py`


### Changed
- **Remove dead `_write_in_progress` flag**: Flag was set/cleared in `_write_register` but never read anywhere – all write/read coordination already uses the `_write_done` asyncio Event. Removed to reduce misleading state.
  - `hub.py`
- **Ultra-Fast Mode**: Disable 10s fast polling when 1s ultra-fast mode is enabled to avoid read bursts.
  - `hub.py`

- **Cache Cleanup**: Periodic cleanup of stale Modbus cache entries and disconnected clients.
  - `modbus_utils.py`
  - `services.py`
  - `hub.py`

- **Config Cache**: Consolidated option/data lookups into a single cached read in hub and options update.
  - `hub.py`
  - `__init__.py`
  - `utils.py`

- **Lock Order Guard**: Added lock ordering warnings for nested Modbus access paths.
  - `hub.py`

- **Sequential Modbus Reads**: Enforced sequential reads for all reader groups to avoid parallel Modbus access.
  - `hub.py`

- **Reader Lock Consistency**: Slow polling reader groups now share the same lock to avoid ad-hoc lock usage.
  - `hub.py`



## [v2.8.3]

### Fixed
- **Runtime Safety**: Removed unsafe import-time type annotation and made fast-poll sensor updates HA-compatible.
  - `__init__.py`
  - `sensor.py`
- **Pending State Cleanup**: Normalized pending flag cleanup for passive mode paths.
  - `charge_control.py`
- **Options Interval Apply**: Reschedule coordinator when `scan_interval` changes so options take effect immediately.
  - `hub.py`
- **RMW Locking**: `merge_write_register()` uses per-address locks for non-merge registers to avoid lock re-entry/deadlocks.
  - `hub.py`

### Changed
- **Register RMW Consolidation**: Unified read-modify-write path via hub merge write to reduce duplication.
  - `charge_control.py`
- **Charge Control Helpers**: Centralized integer coercion and write+cache flow for schedule and setting updates.
  - `charge_control.py`
- **Schedule Readers**: Unified charge/discharge schedule decoding into a shared helper.
  - `modbus_readers.py`
- **Options Flow Simplification**: Removed direct entry data updates in options flow to avoid double-apply behavior.
  - `config_flow.py`
- **Host Uniqueness Check**: Duplicate-host detection now respects values stored in options (options -> data).
  - `config_flow.py`
- **Fast Poll Coverage**: Added `pv1Power`/`pv2Power` to 10s fast polling and included part 1 data in the fast loop.
  - `hub.py`


## [v2.8.2]

### New Features
- **Duplicated Fast-Poll Entities**: Each fast-poll sensor now creates two entities:
  - Normal entity (e.g., `sensor.saj_pvpower`): normal (60s) updates **with** database recording
  - Fast variant (e.g., `sensor.saj_fast_pvpower`): 10s updates **without** database recording
  - Fast variants use `state_class = None` to prevent database flooding while maintaining live UI updates
  - Fast variants are always enabled by default, even if the normal entity is disabled
- **Config Value Utility**: Centralized configuration value retrieval

  - New `utils.py` module with `get_config_value()` function
  
  - Eliminates code duplication across `hub.py`, `__init__.py`, and `config_flow.py`
  - Single source of truth for config value retrieval (options → data → default)

### Fixed
- **Passive Charge Enable Number Entity**: Setting the number entity no longer automatically changes AppMode
  - Users can now freely switch between Standby (0), Discharge (1), and Charge (2) while remaining in Passive Mode (3)
  - Switches continue to automatically manage AppMode:
    - Charging/Discharging switches: AppMode = 1 (Force Charge/Discharge) on activation
    - Passive Charge/Discharge switches: AppMode = 3 (Passive) on activation
    - All switches restore previous mode on deactivation
  - Fixes issue where setting Passive Charge Enable to 0 would unexpectedly switch back to Self-use Mode

### Changed
- **Code Quality Improvements**:
  - Removed ~44 lines of duplicated `_get_config_value()` implementations
  - Consolidated all config value access through centralized utility function
- **Slot Entity Generation Utility**: Refactored charge/discharge slot entity creation
  - New `generate_slot_definitions()` function in `utils.py` generates all 28 slot entities (14 number + 14 text)
  - Eliminated ~126 lines of duplicated loop code from `number.py` and `text.py`
  - Centralized slot definition logic for easier maintenance and future changes

  - revert passive charge/discharge power to 100% (max input value 1100)
---

## [v2.8.1] 

### Fixed
- **Charge Slot Logic**: Fixed incorrect handling of Slot 1 (Bit 0) in charge/discharge control. All slots (1-7) are now treated identically as a 7-bit mask in registers 0x3604/0x3605.
- **Modbus Reconnect**: Critical readers now properly trigger a reconnection sequence upon connection failure instead of swallowing the error.
- **Poll Performance**: Non-critical reader groups now use independent locks, allowing `asyncio.gather` to execute Modbus requests truly in parallel (client permitting).
- **Partial Modbus Data Loss**: `_read_modbus_data()` now returns `(data, errors)` so single-field decoding issues no longer wipe the entire block and the log reports exactly which registers misbehaved.
- **Register 0x3604/0x3605 Guard**: Direct writes to the shared state/mask registers are rejected unless performed through `merge_write_register()`, preventing accidental clearing of the charging state during slot updates.
- **Fast Listener Cleanup**: Sensor entities now deregister their fast-poll callbacks via an `async_on_remove` hook, so disabling/removing an entity immediately stops 10 s updates and avoids race conditions or log spam from stale listeners.
- **Charge Queue Shutdown**: The charge/discharge command handler now cancels and drains its queue cleanly on reload/unload, eliminating zombie tasks that previously kept running after the integration restarted.
- **AppMode-Aware Switches**: Charging/discharging switches once again validate that `AppMode` (0x3647) equals `1` in addition to the bitmask registers.

### Changed
- **Charge/Discharge Power Percent**: Increased both the HA number entities and the inverter card sliders to allow 0‑100 % instead of capping at 50 %, aligning the UI with the inverter’s actual power scaling.


## [v2.8.0]

### New Features
- **Passive Charge/Discharge Switches**: Added dedicated switches for passive charge and discharge modes , explained here https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions/105

### Changed

*Read >* https://github.com/stanus74/home-assistant-saj-h2-modbus/issues/141


- **Dedicated Write Lock**: Implemented a dedicated write lock with priority over read operations. Write operations no longer wait for read operations to complete, and ultra-fast polling (1s) is skipped during write operations to prevent lock contention and improve performance.
- **Charge Control Simplification**: Removed complex locking mechanisms and artificial delays. The integration now updates the internal cache immediately after a successful Modbus write, providing instant feedback in the UI (Optimistic UI).

- and some more code refactoring


## [v2.7.2]
  
### New Features
- **Ultra Fast Polling (1s)**: Added a new "Ultra Fast" mode that polls critical power sensors every second.
- **Direct MQTT Configuration**: Added specific configuration fields (Host, Port, User, Password) for an MQTT broker in the integration options.

  - Added configurable MQTT topic prefix for fast sensor updates.
  - Introduced option to publish the full sensor cache on each main interval.

- **Internal MQTT Client**: Implemented a fallback internal MQTT client. If the Home Assistant MQTT integration is not found, the integration connects directly to the configured broker to publish fast-poll data.


### Improvements
- **Database Protection**: When "Ultra Fast" mode is enabled, Home Assistant entities are *not* updated every second to prevent database flooding. Data is published exclusively to MQTT. Regular entities still update at the standard scan interval (default 60s).
- **Dynamic Reconfiguration**: Changing MQTT settings or polling modes in the options flow now immediately applies changes (restarts clients/timers) without requiring a full restart.

### Fixed
- **CoreState Compatibility**: Fixed a crash on startup/reload caused by `CoreState.RUNNING` vs `CoreState.running` enum changes in newer Home Assistant versions.

## [v2.7.1]

### Changed
- **Flexible Schedule Updates**: Removed the strict validation requiring Start, End, and Power to be set simultaneously. Users can now update individual schedule parameters (e.g., only Start Time) independently.
- **Refactored Charge Control**: Replaced dynamic method generation ("magic") in `charge_control.py` with explicit dictionary-based lookups. This improves code readability, debuggability, and static analysis support.

- **Single Value Updates**: Resolved where updating a single parameter (like Power %) without changing others was ignored. This should prevent incorrect time frames.
It is important to always check the start and end times.

### Fixed
- **Configuration Persistence**: Fixed a bug where connection settings (Host, Port) changed via the Options Flow were ignored upon restart, reverting to the initial configuration.
- **Options Flow Defaults**: The configuration options form now correctly displays the currently active settings instead of defaults.


## [v2.7.0]

### New Inverter Card Version 1.2.1

- **Enhanced UI Visualization**: Active slots are now clearly highlighted with green indicators and background styling for better visibility.
- **Instant Write Operations**: Settings changes are now written immediately to Modbus, improving responsiveness.

### Configuration

- **Fast Polling Toggle**: Added a new configuration option to enable/disable high-frequency data updates (Fast Poll). Default is set to `False` to reduce bus load.

### Improved
- **Modernized Hub Initialization**: The integration now fully utilizes Home Assistant's `ConfigEntry` for configuration management. This aligns the code with HA best practices, improves maintainability, and simplifies the internal setup process.
- **Code Simplification**: Removed redundant internal methods and simplified logic to reduce code complexity and potential sources of error.

### Performance
- **Optimized Logging**: Standardized all logging calls to use `%s` placeholders instead of f-strings. This improves performance by avoiding unnecessary string operations when logging at a less verbose level.
- **Reduced Redundant Operations**: Eliminated a redundant connection check within the main data update cycle, leading to a minor performance gain.
- **Optimized Memory Usage**: Moved Modbus decoding maps to static constants to prevent unnecessary memory allocation during every poll cycle.

- Reduced Modbus operations per cycle: 17 → 16
- Static data no longer polled every scan interval
- Optimized skip_bytes usage for register gaps

### Robustness
- **Enhanced Error Handling**: Implemented `try...except...finally` blocks in critical connection management functions. This ensures that system states (like the `_reconnecting` flag) are always reset correctly, preventing potential deadlocks and significantly improving the overall stability of the integration.
- **Event Loop Protection**: Migrated Modbus communication to run in a separate thread executor using synchronous `ModbusTcpClient`. This ensures that network delays or timeouts no longer freeze the Home Assistant core loop.

### Fixed
- **Integration Reload**: Fixed a `NoneType` error occurring during integration reload or unload due to the synchronous Modbus client's close method not being awaitable.
- **Executor Job Arguments**: Fixed a `TypeError` in `async_add_executor_job` by correctly using `functools.partial` to pass keyword arguments (like `address` and `count`) to the Modbus client methods running in the executor.

### Added
- **Full Charge/Discharge Schedule Support**: All 7 time slots for charging and discharging
  - 28 new charge sensors (`charge2-7`: start/end time, day mask, power percent)
  - 28 new discharge sensors (`discharge2-7`: start/end time, day mask, power percent)
  - All schedule sensors enabled by default

### Changed
- **Optimized Modbus Communication** (~15-20% traffic reduction):
  - Static inverter data cached (read once at startup)
  - Consolidated register reads: Charge (23), Discharge (21), Passive/Battery/Anti-Reflux (39)
  - Removed duplicate `read_anti_reflux_data` function

---

# Changelog (v2.7.4) - Refactoring for HA 2025 Standards

### Refactoring and Improvements:
- **Centralized MQTT Constants**: MQTT constants (`CONF_MQTT_TOPIC_PREFIX`, `CONF_MQTT_PUBLISH_ALL`) moved to `const.py`.
- **Optimistic Overlay Removed**: Unused optimistic overlay feature removed from `hub.py` and `charge_control.py`.
- **Pending States Simplified**: Redundant initialization of pending states in `charge_control.py` removed.
- **Lock System Consolidated**: Redundant `_read_lock` removed from `hub.py`.
- **Helper Methods Centralized**: `_write_register` and `_read_registers` moved from `hub.py` to `ModbusConnectionManager` in `services.py`.
- **Redundant Variables Removed**: Unused `_warned_missing_states` removed from `hub.py`.
- **Code Documentation Improved**: Docstrings added/enhanced in `hub.py`.
- **Circular Dependencies Managed**: `TYPE_CHECKING` import in `charge_control.py` confirmed as standard practice.
- **Config Handling Refactored**: Configuration passing reviewed and deemed appropriate.
- **Architectural Review**: Integration design assessed against HA 2025 standards, confirming adherence to best practices.

# Changelog (v2.7.3)
- Added more charging slots (all 7)
- Fixed minor error

---

# Changelog (v2.6.4)

## ⚠️ Important Notice – New InverterCard Version

### To avoid inconsistent system states caused by using the **InverterCard simultaneously in a browser and the Home Assistant smartphone app**, the card has been reworked.

### 🔁 Cache Notice – Required After Updating the InverterCard:

##### 📱 **For Home Assistant App Users (Smartphones):**

The app uses an internal browser engine that caches JavaScript files.
➡️ You **must clear the app’s data and cache** via your **phone settings**:
Go to *Apps → Home Assistant → Storage → Clear Cache and Data*.
⚠️ You will need to **log in again** afterwards.
**Skipping this step may result in a broken or outdated InverterCard!**

##### 🖥️ **For Browser Users (Desktop or Mobile):**

1. Press **F12** (opens Developer Tools)
2. Go to the **“Network” tab**
3. Enable **“Disable cache”**
4. Reload the page with **F5**

✅ Make sure the **correct InverterCard version number** appears in the card header.
**❌ If it doesn't, you're still using a cached (old) version.**

---

#### 🔧 New Behavior:

* Values for time and power must always be set (overwrite default).

* These are also written without activating/deactivating the charge/discharge button.

### Discharging Switch State Fix

- **Discharging Switch showed incorrect state**: The switch displayed "ON" when only register 0x3605 (Discharge Slots Bitmask) was set, but AppMode (register 0x3647) was still at 0
  - `switch.py`: `is_on` property now checks BOTH registers (discharging_enabled > 0 AND AppMode == 1)
  - Removed blocking `asyncio.run_coroutine_threadsafe()` calls → Reads directly from cache (synchronous, fast)
  - No more "took 1.001 seconds" warnings
