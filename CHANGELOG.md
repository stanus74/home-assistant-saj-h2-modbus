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

- Reduced Modbus operations per cycle: 17 → 16
- Static data no longer polled every scan interval
- Optimized skip_bytes usage for register gaps

### Robustness
- **Enhanced Error Handling**: Implemented `try...except...finally` blocks in critical connection management functions. This ensures that system states (like the `_reconnecting` flag) are always reset correctly, preventing potential deadlocks and significantly improving the overall stability of the integration.


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

# Changelog (v2.6.5)

- Fixed Fast Coordinator error
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