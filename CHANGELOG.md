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
