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
