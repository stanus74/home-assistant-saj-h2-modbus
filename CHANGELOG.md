## [v2.7.3]

### New Features
- **Passive Charge/Discharge Switches**: Added dedicated switches for passive charge and discharge modes , explained here https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions/105

- **Charge Control** and **Number Entities**: Implementation of an asynchronous command queue for immediate execution of setting changes, independent of the polling interval.


### Changed

- **Number Entities**: Reduced maximum value for passive power settings (`passive_grid_charge_power`, `passive_grid_discharge_power`, etc.) to 500.
- **Number Entities**: Reduced maximum value for power percentages of charge/discharge time slots (`chargeX_power_percent`, `dischargeX_power_percent`) to 50%.

*Read >* https://github.com/stanus74/home-assistant-saj-h2-modbus/issues/141

- **Inverter Card**: Bumped version to 1.2.2.
- Adjusted slider range for power percentages to 0-50%.
- Added debouncing for sliders, time input fields, and weekday checkboxes.                    

### Improvements
- **Dedicated Write Lock**: Implemented a dedicated write lock with priority over read operations. Write operations no longer wait for read operations to complete, and ultra-fast polling (1s) is skipped during write operations to prevent lock contention and improve performance.
- **Charge Control Simplification**: Removed complex locking mechanisms and artificial delays. The integration now updates the internal cache immediately after a successful Modbus write, providing instant feedback in the UI (Optimistic UI).
- **MQTT Backoff**: Home Assistant MQTT failures now trigger an exponential cooldown with adaptive re-checks, cutting CPU and network load during broker outages while reconnecting automatically after recovery.


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

