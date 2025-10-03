# Changelog (v2.6.0)

### 🚀 New Passive Charge/Discharging Input Methods Added 

* **New Input Registers:**

  - `SAJ Passive Charge Enable (Input)` - Register 3636H ...
  - `SAJ Passive Grid Charge Power (Input)` 
  - `SAJ Passive Grid Discharge Power (Input)`
  - `SAJ Passive Battery Charge Power (Input)` 
  - `SAJ Passive Battery Discharge Power (Input)` - ... Register 363AH
  

* These new input methods allow for precise control of passive battery charge & discharge power.
see Discussion https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions/105

---

### 🚀 New Fast Sensors Added

* **Fast Coordinator (10s) now includes additional sensors:**

  - `sensor.saj_ct_pv_power_watt`
  - `sensor.saj_ct_pv_power_va`
  - `sensor.saj_ct_grid_power_va`
  - `sensor.saj_ct_grid_power_watt`  

* These sensors are now updated every 10 seconds via the Fast Coordinator, ensuring more frequent updates for live data monitoring.

---

# Changelog (v2.5.0)

### 🚀 New Fast Coordinator (10s) for Live Data

* **High-frequency polling for key metrics (e.g., PV power, battery):**

  * Introduced a 10s fast coordinator 
  * Can be disabled via simple adjustment in hub.py, 
    
    Energy sensors are polled every 10 seconds: 

      - sensor.saj_total_load_power
      - sensor.saj_pv_power
      - sensor.saj_battery_power
      - sensor.saj_total_grid_power
      - sensor.saj_inverter_power
      - sensor.saj_grid_power


This is the default setting. Can be disabled in hub.py line 27:

`FAST_POLL_DEFAULT = True # True or False`


### Major Code Improvements & Feature Expansion

* **Complete refactor of `hub.py`** for better structure, robust Modbus handling, and future-proof extensibility.

### Updated

* **Sensor Polling:**

  * Modbus connections now reliably handled via `connect_if_needed()`.
  * Improved error handling and reconnection strategy.
  * Clear separation of volatile and static data reads.

* **Charging/Discharging Management:**

  * Introduced "optimistic push" logic: planned states are reflected in the UI before Modbus confirmation.
  * Clean detection of pending changes via `_has_pending()`.
  * Maintained dynamic generation of all setter methods for flexibility.

### Improvements

* **Efficient Modbus Access:**

  * Separated polling intervals reduce read load.
  * More resilient to timeouts and read errors.

* **Connection Stability:**

  * New connection check and auto-reconnect logic with `ensure_client_connected()`.
  * Graceful handling and logging of client shutdown errors.

* **Logging & UX:**

  * Suppresses repeated warnings for missing app mode/state values.
  * Enhanced debug logging for fast coordinator updates.

### Added

* **Fast update functionality (`start_fast_updates`)** with dedicated `DataUpdateCoordinator`.
* **Optimistic state overlay (`_optimistic_overlay`)** for faster UI feedback during pending changes.
* **Single-use warning logic (`_warned_missing_states`)** to reduce log noise for known issues.


# Changelog (v2.4.0)

## Big Code improvement and reducing

## Code was shortened by 380 lines or reduced by 17Kbytes.

### Updated

- Refactored `hub.py` to consolidate `_pending_*` attributes into a single `_pending_settings` dictionary for better maintainability.
- Updated `ChargeSettingHandler` in `charge_control.py` to use the `_pending_settings` dictionary instead of individual `_pending_*` attributes.
- Replaced repetitive `handle_*_settings` methods in `charge_control.py` with a generic `handle_settings` method.
- Updated `pending_handlers` in `hub.py` to dynamically call `handle_settings` for different modes (e.g., `charge`, `discharge`).
- Added debug logging in `hub.py` and `charge_control.py` to trace pending settings and Modbus operations.

### Improvements

- **Improved Charge/Discharge Day Mask and Power Percent Handling:**
  - Modified `charge_control.py` to default `day_mask` to 127 and `power_percent` to 5 when not explicitly provided.
  - Ensured that existing `day_mask` or `power_percent` values are read from the inverter and combined with new inputs if only one is provided.
  - Implemented a check to prevent redundant Modbus writes for day mask and power percent if the combined value has not changed.
- **Optimized Modbus Write Operations:**
  - Updated `hub.py` to only trigger `charge_control.py`'s `handle_charge_settings` when there are actual pending changes for charge start/end times, day mask, or power percent.

### Added

- Introduced `_read_phase_block` helper function for compact 3-phase block reading.

### Changed
- Refactored `read_discharge_data` to use a loop for dynamic decode instructions.
- Updated `_read_modbus_data` to handle missing keys or insufficient registers gracefully.
- Simplified and improved error handling in `read_anti_reflux_data`.
- Refactored `read_additional_modbus_data_4`, `read_inverter_phase_data`, and `read_offgrid_output_data` to use `_read_phase_block`.

### Removed

- Cleaned up unused imports (`Dict`, `NamedTuple`, `Any`, `UnitOfTime`) from `const.py` to reduce code noise.
- some more cleanup

# Changelog (v2.3.1)

### Bug Fixes

- **Modbus Client Compatibility Fix:**
  - Addressed `TypeError` in `ModbusClientMixin.read_holding_registers()` (and write operations) caused by unexpected `slave`/`device_id` keyword arguments in some Home Assistant environments.
  - Implemented a workaround by setting `client.unit_id` directly on the client object before each Modbus read/write operation.

### Code Improvements & Optimizations

- **Refactored Modbus Operation Logic:**
  - Consolidated common Modbus operation logic into a new helper function `_perform_modbus_operation` in `modbus_utils.py`. This makes `read_once` and `write_once` functions more compact and readable.
- **Centralized Type Aliases:**
  - Moved `ModbusClient` and `Lock` type aliases to `custom_components/saj_h2_modbus/const.py` for better code organization and maintainability.


# Changelog (v2.3.0)

### New Sensors

- **Added Smart Meter Sensors:**
  - New sensors for R, S, and T phase Meter voltage, current, frequency, power-factor, real-power and apparent-power (Registers `A03Dh` - `A04Eh`).
- **Added Inverter Phase Data Sensors:**
  - New sensors for R, S, and T phase inverter voltage, current, frequency, and power (Registers `4046h` - `4054h`).
- **Added Off-Grid Output Data Sensors:**
  - New sensors for R, S, and T phase off-grid output voltage, current, frequency, power, and DVI (Registers `4055h` - `4066h`).
- **Added Side-Net Data Sensors:**
  - New sensors for R, S, and T phase on-grid side-net voltage, current, frequency, and power (Registers `408Dh` - `4094h`).

### Bug Fixes

- **Apparent Power Sensor Unit Fix:**
  - Corrected unit of measurement for **all** apparent power sensors (VA) to ensure proper categorization with the `APPARENT_POWER` device class. This resolves unit mismatch errors and enables Home Assistant to store long-term statistics correctly.


# Changelog (v2.2.4)

### Added New Battery and Grid Power Limit Sensors

- **Added new sensors for monitoring power limits:**
  - Battery Charge Power Limit (Register 364Dh)
  - Battery Discharge Power Limit (Register 364Eh)
  - Grid Charge Power Limit (Register 364Fh)
  - Grid Discharge Power Limit (Register 3650h)
  - All sensors use a factor of 0.1 to display percentage values
  - Added to battery_sensors group with appropriate icons
  - Enabled by default for easy monitoring

### Code Improvements

- **Configuration Options Management**
  - **Changed:** Options are now stored in config_entry.options instead of config_entry.data
  - **Added:** Fallback mechanism to read values from data if not present in options
  - **Affected:** config_flow.py and __init__.py were modified to handle options correctly
  - **Benefit:** Better adherence to Home Assistant standards for configuration management

- **Unified unique_id Generation**
  - **Consistent Base:** All entities now use the hub name as the base for their unique_ids
  - **Affected:** number.py and text.py were modified to use the dynamic hub name instead of the fixed "saj_" prefix
  - **Benefit:** Better distinction between multiple instances and more consistent entity identification

- **Device Info Support**
  - **Added:** device_info is now set for all entities (number and text entities)
  - **Affected:** Base classes in number.py and text.py were modified to include device_info
  - **Benefit:** Proper device grouping and identification in Home Assistant


### Code Optimizations

- **Simplified Reset Time Logic:** Introduced `reset_period` attribute in `SajModbusSensorEntityDescription` to simplify `native_last_reset_time` logic. This makes the code more maintainable and less error-prone.
- **Code Cleanup:** Removed unused variable `self._closing` from SAJModbusHub class.

# Changelog (v2.2.3)

### Added Battery and Grid Power Limit Controls

Added new input entities for controlling battery and grid power limits:

- **Battery Power Limits**
  - `SAJ Battery On Grid Discharge Depth (Input)` - Register 0x3644
  - `SAJ Battery Off Grid Discharge Depth (Input)` - Register 0x3645
  - `SAJ Battery Capacity Charge Upper Limit (Input)` - Register 0x3646
  - `SAJ Battery Charge Power Limit (Input)` - Register 0x364D
  - `SAJ Battery Discharge Power Limit (Input)` - Register 0x364E

- **Grid Power Limits**
  - `SAJ Grid Max Charge Power (Input)` - Register 0x364F
  - `SAJ Grid Max Discharge Power (Input)` - Register 0x3650

All power limit entities (0x364D-0x3650) have:
- Range: 0-1100
- Step size: 100
- Default: 1100

## **Important: 1000 is 100%**

# Changelog (v2.2.2)

### Fix for Sensor Configuration of Periodic Energy Meters
- **Corrected `state_class`:** Changed `state_class` for periodically resetting energy sensors (e.g., `sensor.saj_sell_today_energy`, `sensor.saj_todayenergy`) from `TOTAL_INCREASING` to `TOTAL`. This resolves Home Assistant log warnings about non-strictly increasing values and ensures accurate sensor interpretation.
- **Added `native_last_reset_time`:** Introduced `native_last_reset_time` for these sensors, providing Home Assistant with precise reset times for improved Energy Dashboard accuracy and long-term statistics.
- **Default Activation:** The `sell_today_energy` sensor is now enabled by default.

### Improved Charge/Discharge Switch Status Detection
- **Enhanced Logic:** Updated the logic for determining the status of charge (register 0x3604) and discharge (register 0x3605) switches by also checking the App-Mode register (0x3647).
- **New Condition:** A switch is now shown as "active" only if:
  1. The specific status register indicates an active operation (value > 0).
  2. The App-Mode register (0x3647) is set to 1, confirming the operational mode for charge/discharge functions.
- **Benefit:** Prevents incorrect "active" status indications when the overarching App-Mode does not permit charging or discharging.

These changes ensure more accurate energy data representation and reliable switch status reporting in Home Assistant.


# Changelog (v2.2.1)

### Fixed

Fixed an issue where enabling multiple sensors caused the Modbus adapter to become unresponsive due to excessive read requests. Removed the custom `async_update` method (sensor.py), using the base class implementation instead. Sensors now update only via the coordinator's regular refresh interval, reducing load and preventing communication failures.

# Changelog (v2.2.0)

### Added

- **Support for multiple discharge time windows**

  - New input entity "SAJ Discharge_time_enable (Input)" for controlling the discharge **"Time Enable"** register (0x3605)
  - Direct access to the discharge time enable register for **binary** Time Slot selection (e.g., 1 = Time 1, 3 = Time 1 and Time 2,... 127 All 7 Slots)
  - Support for multiple discharge time windows (Discharge 1-7)
  - New entities for Discharge 2-7 start and end times
  - New entities for Discharge 2-7 day mask (weekday selection)
  - New entities for Discharge 2-7 power percent settings


- Support for `input_number` entities to provide a better user interface for numeric settings
- Bidirectional synchronization between `number` entities and `input_number` entities
- Thread-safe implementation for handling state changes from different threads


### Changed
- Improved error handling and logging for better troubleshooting
- Updated code to use thread-safe methods for asynchronous operations
- Code optimization in `number.py`: Parameterized classes for discharge entities
- Code optimization in `text.py`: Introduction of a base class for time entities
- Reduction of code duplication through dynamic method selection
- Change unit_of_measuremnt to show graphical chart for Inverter Power Factor R,S,T Phase

### Documentation
- Added instructions for setting up `input_number` entities in configuration.yaml
- Added explanation of how the integration works with or without `input_number` entities



# Changelog (v2.1.0)

#### ✨ New Sensor + Number Entity: "SAJ App Mode (Input)

- **sensor.saj_app_mode** added (register `0x3647`)
- A new number entity `saj_app_mode_input` was added for writing to Modbus register `0x3647`.
- Range: 0–3, step: 1, default: 0.
 
    **0 Self-use_mode** - Self-consumption mode
    **1 time_mode** - Time-controlled mode 
    **2 backup_mode** - Backup mode
    **3 passive_mode** - Passive mode


### Change Domain for HACS compatibility
- from saj_modbus to saj_h2_modbus, as there was already an integration with this domain in the HACS directory. 

### 🚀 Code Optimizations
- Introduced a robust `ModbusConnection` async context manager for auto-connect and safe close.
- Implemented retry logic with exponential backoff for all Modbus read/write operations via `_retry_with_backoff`.
- Added support for reconnecting if the Modbus client is disconnected mid-operation.

#### 🌐 Global Configuration
- Introduced `ModbusGlobalConfig` with `set_modbus_config()` to avoid redundant host/port arguments.
- Simplified usage in readers and hub: host/port only needs to be configured once.

#### 🧠 Error Handling Enhancements
- Unified logging across retries with optional `task_name` for better traceability.
- Improved error transparency for non-retriable exceptions and unexpected disconnections.

#### 🧩 Code Structure & Maintainability
- Extracted all charge/discharge/export logic into a new module: `charge_control.py`.
  - Centralizes logic for all pending settings.
  - Cleaner, more modular hub and platform code.


- **Refactored `charge_control.py` for Better Maintainability**
  - Introduced central `REGISTERS` constant for all register addresses.
  - Reduced code redundancy by creating shared helper methods:
    - `_handle_power_settings` for charge/discharge settings.
    - `_handle_power_state` for charging/discharging states.
    - `_handle_simple_register` for basic register operations.
  - Improved error handling consistency across all operations.
  - Added comprehensive German docstrings for better documentation.
  - Enhanced code structure with clearer method responsibilities.


