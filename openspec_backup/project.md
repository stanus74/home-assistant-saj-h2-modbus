# SAJ H2 Modbus Integration - Project Specification

## 🎯 Purpose

The SAJ H2 Modbus integration for Home Assistant aims to provide seamless control and monitoring of SAJ H2 inverters. It facilitates reading inverter data, publishing this data to Home Assistant entities, and enabling users to configure and write charge/discharge schedules back to the inverter.

## 🛠️ Tech Stack

*   **Primary Language:** Python
*   **Core Framework:** Home Assistant Core (HA-Core)
*   **Communication Protocol:** Modbus (for inverter interaction)
*   **Optional Data Export:** MQTT

## 🏗️ Key Architectural Decisions

*   **Modbus Communication Layer:** Implemented in `modbus_readers.py` and `modbus_utils.py`, this layer handles establishing connections, reading a comprehensive set of Modbus registers (over 300), decoding raw data, and managing connection retries with exponential backoff. It also addresses potential issues like data loss during errors and lock contention between different polling frequencies (1s, 10s, 60s).
*   **Home Assistant Entity Management:** Utilizes `DataUpdateCoordinator` in `hub.py` to manage the lifecycle and updates of Home Assistant entities (`sensor.py`). This includes registering/deregistering listeners for fast updates, handling entity removal race conditions, and optimizing state change detection to minimize unnecessary HA state writes.
*   **Charge/Discharge Scheduling:** The `charge_control.py` module orchestrates the scheduling functionality. It handles user input validation for time slots, power percentages, and day masks, manages pending states for UI feedback, and implements optimistic UI updates before Modbus write confirmation.
*   **Modbus Write Operations:** The integration supports writing schedules back to the inverter. This involves calculating register values, performing read-modify-write operations for bit fields (e.g., enabling/disabling slots), queuing commands to ensure sequential execution, and implementing retry logic with verification.
*   **MQTT Integration (Optional):** For users who wish to export data externally, an MQTT publisher is available. This component in `services.py` and `hub.py` can use either HA's built-in MQTT integration or a custom Paho client, supporting an ultra-fast 1-second update interval for specific data points.
*   **Configuration and Lifecycle Management:** Handled by `__init__.py`, `config_flow.py`, and `hub.py`, this covers the initial setup, configuration entry updates, initialization of Modbus connections and polling, and graceful shutdown. It includes logic for startup delays and handling configuration fallbacks.
*   **Robust Error Handling and Logging:** A cross-cutting concern, this ensures that errors during Modbus communication, data processing, or HA entity updates are logged effectively with sufficient context. It aims for clear, user-friendly error messages and provides debugging information to aid troubleshooting.
