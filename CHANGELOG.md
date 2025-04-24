# Changelog (v2.1.0)

#### ✨ New Sensor + Number Entity: "SAJ App Mode (Input)

  - **sensor.saj_app_mode** added (register `0x3647`)
  - A new number entity `saj_app_mode_input` was added for writing to Modbus register `0x3647`.
  - Range: 0–3, step: 1, default: 0.
 

  - **0x00 Self-use_mode** - Self-consumption mode
  - **0x01 time_mode** - Time-controlled mode 
  - **0x02 backup_mode** - Backup mode
  - **0x03 passive_mode** - Passive mode



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
