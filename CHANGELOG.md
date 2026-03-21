## [v2.8.5]

---

## Release v2.8.5 – Stabilität & Code-Qualität

Diese Version schließt mehrere potenzielle Datenkorruptions- und Race-Condition-Probleme und verbessert die Robustheit des gesamten Polling-Systems.

### Wichtigste Fixes

**Datenkorruption bei Schreib-/Lese-Konflikten verhindert**
Ein Timeout beim Warten auf das Ende einer Schreiboperation führte bisher dazu, dass ein Modbus-Lesevorgang trotzdem gestartet wurde – möglicherweise während der Socket noch von einem Write belegt war. Der Lesevorgang wird jetzt abgebrochen statt fortzufahren.

**Race Condition bei Cache-Updates behoben**
`_update_cache()` in `charge_control.py` schrieb ohne Lock in `inverter_data`. Das konnte zu inkonsistenten Zuständen führen, wenn gleichzeitig Slow- oder Fast-Poll liefen. Alle 7 Aufrufstellen verwenden jetzt `_data_lock`.

**Doppelter Reconnect im Fast-Poll entfernt**
Bei jedem Fehler im Fast-Poll wurde `reconnect()` zweimal aufgerufen – einmal intern und einmal im äußeren Handler. Das Verhalten ist jetzt korrekt.

**TOCTOU-Lücke beim Ultra-Fast/Write-Konflikt geschlossen**
Ein Write konnte genau während `await get_client()` starten und den Socket belegen. Ein zweiter Guard direkt nach `get_client()` schließt dieses Zeitfenster.

**Unbehandelte Background-Task-Fehler sichtbar gemacht**
Exceptions in Background-Tasks verschwanden lautlos. Neuer `create_logged_task()`-Helper loggt alle Fehler inkl. vollständigem Stack-Trace.

### Weitere Verbesserungen

- **Statische Inverterdaten (Seriennummer, Firmware) werden stündlich neu gelesen** – Änderungen nach einem Firmware-Update werden ohne HA-Neustart übernommen
- **Pro-Instanz Circuit Breaker**: Ein fehlgeschlagener Inverter blockiert jetzt nicht mehr den zweiten parallel konfigurierten Inverter
- **Connection Cache TTL** verkürzt: 60 s → 30 s, Health-Check-Interval 30 s → 5 s – stille Verbindungsabbrüche werden schneller erkannt
- **LRU-Limit für interne RMW-Locks** tatsächlich durchgesetzt (vorher nur WARNING-Log)
- **Lock-Order-Guard** deckt jetzt auch Fast/Ultra-Fast-Polling ab – potenzielle Deadlocks werden früher erkannt
- Toten Code entfernt: `_process_reader_result()`, `ensure_client_connected()`, `connect_if_needed()`
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
