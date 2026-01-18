# OpenSpec Proposal: SAJ H2 Modbus Charge/Discharge Scheduling Improvement

## Objective

To enhance the reliability and robustness of the charge/discharge scheduling functionality for the SAJ H2 Modbus integration by addressing potential issues in time format validation, Modbus communication, and error handling.

## Analysis of Current Implementation

This section details how schedules are currently sent to the SAJ inverter, based on an analysis of the relevant code files (`custom_components/saj_h2_modbus/charge_control.py`, `custom_components/saj_h2_modbus/hub.py`, `custom_components/saj_h2_modbus/modbus_utils.py`).

### `charge_control.py`
- Manages a command queue (`_command_queue`) for sending commands to the inverter via `ChargeSettingHandler`.
- Defines `CommandType` enums for operations like `CHARGE_SLOT`, `DISCHARGE_SLOT`, `SIMPLE_SETTING`.
- **Slot Settings (`_handle_slot_setting`)**:
    - Uses `MODBUS_ADDRESSES["slots"]` to map charge/discharge slots (1-7) to Modbus registers for `start`, `end`, and `day_mask_power`.
    - Time values (`start`, `end`) are converted using `_parse_time_to_register` (expects "HH:MM" string).
    - `day_mask` and `power_percent` use read-modify-write via `_update_day_mask_and_power`.
    - Ensures slot `time_enable` bits are set via `_ensure_slot_enabled`.
- **Simple Settings (`_handle_simple_setting`)**:
    - Handles general settings using `MODBUS_ADDRESSES["simple_settings"]`.
    - `charge_time_enable` and `discharge_time_enable` use a modifier to merge with existing state bits in registers 0x3604/0x3605.
- **Power States (`_handle_power_state`)**:
    - Handles `CHARGING_STATE` and `DISCHARGING_STATE` by writing to 0x3604/0x3605 using a modifier.
- **Write Operations**:
    - Uses `_write_register_with_backoff` for single writes (includes retries).
    - Uses `_modify_register` for read-modify-write.
- **Time Parsing**: `_parse_time_to_register` converts "HH:MM" to `(hours << 8) | minutes`.

### `hub.py`
- Contains `SAJModbusHub`, the central coordinator.
- Holds `ChargeSettingHandler` instance.
- Provides methods (`set_charging_state`, `set_pending`) that queue commands.
- `_write_register` and `_read_registers` delegate to `modbus_utils` and manage locks.
- `merge_write_register` is used for operations needing to preserve bits in shared registers, utilizing per-register locks.

### `modbus_utils.py`
- Provides low-level Modbus communication utilities.
- `try_write_registers` and `try_read_registers` implement retry logic with exponential backoff and handle connection errors (reconnection attempts).
- `_perform_modbus_operation` wraps blocking Modbus calls in an executor.
- Uses `ModbusGlobalConfig` for global connection details.

**Overall Schedule Sending:**
User services queue commands via `SAJModbusHub`, which are processed by `ChargeSettingHandler`. This handler translates commands into Modbus writes using `MODBUS_ADDRESSES` and calls `hub._write_register` or `hub.merge_write_register`. These methods use `modbus_utils` for communication, including retries and reconnection. The command queue ensures sequential processing of requests.

## Tasks

This proposal outlines the following key tasks:

### 1. Validierung der Zeitformate (Validation of Time Formats)
- **Description:** Ensure that all time inputs for scheduling are validated rigorously to prevent errors caused by incorrect formats. This includes checking for valid hours, minutes, and potentially AM/PM indicators if applicable.
- **Goal:** Prevent scheduling errors due to malformed time strings.

### 2. Prüfung der Modbus-Registerantwort (Checking Modbus Register Response)
- **Description:** Implement checks to verify the responses received from the SAJ inverter after attempting to write scheduling data to Modbus registers. This involves confirming that the write operation was acknowledged and that the data was written correctly.
- **Goal:** Ensure that scheduling commands are successfully received and processed by the inverter.

### 3. Hinzufügen von Logging für fehlgeschlagene Schreibvorgänge (Adding Logging for Failed Write Operations)
- **Description:** Introduce comprehensive logging for any instances where writing scheduling data to the Modbus registers fails. This logging should capture relevant details such as the attempted write, the error response, and the timestamp.
- **Goal:** Improve debuggability and provide clear insights into scheduling failures.
