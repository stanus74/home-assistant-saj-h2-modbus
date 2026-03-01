## [v2.8.6]

### Changed
- **Sequential Modbus Reads**: Enforced sequential reads for all reader groups to avoid parallel Modbus access.
  - `custom_components/saj_h2_modbus/hub.py`


## [v2.8.5]

### Changed
- **Reader Lock Consistency**: Slow polling reader groups now share the same lock to avoid ad-hoc lock usage.
  - `custom_components/saj_h2_modbus/hub.py`


## [v2.8.4]

### Fixed
- **Connection Cache Race**: Serialize client cache access to avoid stale Modbus clients under concurrent load.
  - `custom_components/saj_h2_modbus/services.py`
- **Write/Read Coordination**: Ultra-fast polling waits for writes and schedules a catch-up update; reads no longer busy-wait.
  - `custom_components/saj_h2_modbus/hub.py`


## [v2.8.3]

### Fixed
- **Runtime Safety**: Removed unsafe import-time type annotation and made fast-poll sensor updates HA-compatible.
  - [`custom_components/saj_h2_modbus/__init__.py`](custom_components/saj_h2_modbus/__init__.py)
  - [`custom_components/saj_h2_modbus/sensor.py`](custom_components/saj_h2_modbus/sensor.py)
- **Pending State Cleanup**: Normalized pending flag cleanup for passive mode paths.
  - [`custom_components/saj_h2_modbus/charge_control.py`](custom_components/saj_h2_modbus/charge_control.py)
- **Options Interval Apply**: Reschedule coordinator when `scan_interval` changes so options take effect immediately.
  - [`custom_components/saj_h2_modbus/hub.py`](custom_components/saj_h2_modbus/hub.py)
- **RMW Locking**: `merge_write_register()` uses per-address locks for non-merge registers to avoid lock re-entry/deadlocks.
  - [`custom_components/saj_h2_modbus/hub.py`](custom_components/saj_h2_modbus/hub.py)

### Changed
- **Register RMW Consolidation**: Unified read-modify-write path via hub merge write to reduce duplication.
  - [`custom_components/saj_h2_modbus/charge_control.py`](custom_components/saj_h2_modbus/charge_control.py)
- **Charge Control Helpers**: Centralized integer coercion and write+cache flow for schedule and setting updates.
  - [`custom_components/saj_h2_modbus/charge_control.py`](custom_components/saj_h2_modbus/charge_control.py)
- **Schedule Readers**: Unified charge/discharge schedule decoding into a shared helper.
  - [`custom_components/saj_h2_modbus/modbus_readers.py`](custom_components/saj_h2_modbus/modbus_readers.py)
- **Options Flow Simplification**: Removed direct entry data updates in options flow to avoid double-apply behavior.
  - [`custom_components/saj_h2_modbus/config_flow.py`](custom_components/saj_h2_modbus/config_flow.py)
- **Host Uniqueness Check**: Duplicate-host detection now respects values stored in options (options -> data).
  - [`custom_components/saj_h2_modbus/config_flow.py`](custom_components/saj_h2_modbus/config_flow.py)
- **Fast Poll Coverage**: Added `pv1Power`/`pv2Power` to 10s fast polling and included part 1 data in the fast loop.
  - [`custom_components/saj_h2_modbus/hub.py`](custom_components/saj_h2_modbus/hub.py)


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
