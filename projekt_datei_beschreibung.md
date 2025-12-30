## `custom_components/saj_h2_modbus/modbus_utils.py`

*   **Name:** `modbus_utils.py`
*   **Function:** This file provides utility functions for Modbus communication. It includes robust error handling with retry mechanisms (`_retry_with_backoff`) that implement exponential backoff for both read and write operations. It manages Modbus client connections, including reconnection logic (`_connect_client`, `ReconnectionNeededError`) and a caching mechanism (`ConnectionCache`) to optimize connection reuse. It also provides helper functions for performing Modbus read and write operations, ensuring they are executed in an executor to avoid blocking the Home Assistant event loop.
*   **Architecture Role:** Modbus Communication Utilities. This module encapsulates low-level Modbus communication logic, including connection management, error handling, retries, and executor-based operation execution, making Modbus interactions reliable and efficient.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## ⚡ 2. Modernisierung & 2025 Updates)

## `custom_components/saj_h2_modbus/hub.py`

*   **Name:** `hub.py`
*   **Function:** This file defines the `SAJModbusHub` class, which serves as the central state manager and coordinator for the SAJ Modbus integration. It orchestrates Modbus communication, data updates, and configuration management. Key responsibilities include:
    *   Managing connection settings (host, port, scan interval).
    *   Implementing different polling intervals (normal, fast, ultra-fast) with dedicated asyncio locks (`_ultra_fast_lock`, `_fast_lock`, `_slow_lock`) for performance optimization and reduced contention.
    *   Handling MQTT publishing through `MqttPublisher`.
    *   Integrating with `ChargeSettingHandler` for managing pending charge/discharge settings.
    *   Supporting optimistic updates and processing pending settings.
    *   Ensuring Modbus operations are non-blocking by using `hass.async_add_executor_job` implicitly through `modbus_utils`.
*   **Architecture Role:** Central Hub/Coordinator. This component is the heart of the integration, managing the overall state, coordinating data flow between Modbus communication (`modbus_utils.py`), data readers (`modbus_readers.py`), and charge control logic (`charge_control.py`). It ensures efficient and responsive operation by managing polling intervals and locks.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## ⚡ 2. Modernisierung & 2025 Updates)

## `custom_components/saj_h2_modbus/charge_control.py`

*   **Name:** `charge_control.py`
*   **Function:** This file implements the `ChargeSettingHandler` class, responsible for managing all charge and discharge settings. It utilizes an `asyncio.Queue` to process commands sequentially, ensuring robust Modbus write operations with exponential backoff retries (`_write_register_with_backoff`). It maps various settings, including charge/discharge slots, power limits, and application modes, to specific Modbus addresses defined in `MODBUS_ADDRESSES`. Key features include handling state synchronization, capturing and restoring previous application modes, and ensuring operations do not block the Home Assistant event loop by leveraging the hub's non-blocking read/write methods.
*   **Architecture Role:** Charge Control Logic. This module encapsulates the core business logic for scheduling and controlling charging/discharging operations. It acts as a crucial layer between the `hub.py` (which queues commands) and the low-level Modbus communication utilities, ensuring that complex setting changes are applied reliably and efficiently.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🛠 3. API-Änderungen & Deprecations)

## `custom_components/saj_h2_modbus/config_flow.py`

*   **Name:** `config_flow.py`
*   **Function:** This file defines the configuration flow for the SAJ Modbus integration, including the initial setup (`SAJModbusConfigFlow`) and options editing (`SAJModbusOptionsFlowHandler`). It handles user input validation for connection parameters (host, port, scan interval) and MQTT settings. It ensures unique configurations per host and provides mechanisms to update the integration's settings dynamically after initial setup, including calling `hub.update_connection_settings` when options are modified.
*   **Architecture Role:** Configuration Management. This module is responsible for the user-facing setup and configuration of the SAJ Modbus integration, ensuring that all necessary parameters are collected, validated, and applied correctly according to Home Assistant's configuration entry system.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/const.py`

*   **Name:** `const.py`
*   **Function:** This file centralizes all constants, default values, and definitions for the SAJ Modbus integration. It defines domain names, configuration keys, Modbus addresses, and crucially, provides detailed `SajModbusSensorEntityDescription` objects for all supported sensors, including their units, icons, device classes, and state classes. It also includes mappings for device statuses and fault messages, ensuring a consistent representation of inverter data.
*   **Architecture Role:** Constants and Definitions. This module serves as the central registry for all static data and configuration parameters, promoting code clarity, reusability, and maintainability across the integration. It defines the structure and metadata for entities exposed to Home Assistant.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/manifest.json`

*   **Name:** `manifest.json`
*   **Function:** This file contains essential metadata for the SAJ H2 Modbus Home Assistant integration. It defines the integration's domain (`saj_h2_modbus`), name, version, dependencies (`mqtt`), requirements (`pymodbus`), and configuration flow status. It also specifies the `iot_class` as `local_polling` and provides links to documentation and issue tracking.
*   **Architecture Role:** Integration Metadata. This file is crucial for Home Assistant to identify, load, and manage the integration. It declares dependencies and requirements, ensuring the integration can function correctly within the Home Assistant ecosystem.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## ⚡ 2. Modernisierung & 2025 Updates)

## `custom_components/saj_h2_modbus/modbus_readers.py`

*   **Name:** `modbus_readers.py`
*   **Function:** This file contains functions responsible for reading and decoding data from the SAJ inverter via Modbus. It utilizes configurable decoding maps and helper functions (`_read_modbus_data`, `_read_configured_data`) to parse raw Modbus register values into structured data. It handles various data types, including real-time operating data, battery information, meter readings, phase-specific data, and charge/discharge schedules, ensuring that data is correctly interpreted and scaled.
*   **Architecture Role:** Data Decoding and Parsing. This module is the primary component for translating raw Modbus communication into usable data points for Home Assistant entities. It acts as a crucial layer between the low-level Modbus communication utilities and the higher-level integration logic, defining how inverter data is structured and interpreted.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/sensor.py`

*   **Name:** `sensor.py`
*   **Function:** This file defines the `SajSensor` class, which is responsible for creating and managing individual sensor entities within Home Assistant. It utilizes sensor descriptions from `const.py` to configure each sensor's properties and integrates with the `SAJModbusHub` via `CoordinatorEntity` for data updates. It specifically handles the registration and deregistration of sensors that support fast polling (10-second intervals), ensuring efficient updates for critical data points.
*   **Architecture Role:** Entity Management. This module is responsible for the lifecycle and data presentation of sensor entities. It bridges the gap between the data provided by the hub and the entities exposed to the user in Home Assistant, managing updates and configuration.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## ⚡ 2. Modernisierung & 2025 Updates)

## `custom_components/saj_h2_modbus/services.py`

*   **Name:** `services.py`
*   **Function:** This file defines the `ModbusConnectionManager` and `MqttPublisher` classes. The `ModbusConnectionManager` handles Modbus TCP connections, including robust reconnection logic, locking, and connection caching for performance optimization. The `MqttPublisher` manages MQTT communication, supporting both Home Assistant's native MQTT integration and an internal Paho MQTT client, incorporating a circuit breaker pattern for reliability. It also handles configuration updates for both services.
*   **Architecture Role:** Connection Management and Communication Services. This module provides the essential services for reliable Modbus communication and data publishing via MQTT. It abstracts complex connection handling, error management, and retry mechanisms, ensuring the integration can communicate effectively with the inverter and the MQTT broker.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/switch.py`

*   **Name:** `switch.py`
*   **Function:** This file defines the `BaseSajSwitch` class, responsible for creating and managing switch entities that control functionalities like charging, discharging, and passive modes. It interacts with the `SAJModbusHub` to set these states, utilizing pending attributes for managing state changes and includes a time lock mechanism to prevent rapid consecutive operations.
*   **Architecture Role:** Switch Entity Implementation. This module is responsible for providing user-configurable switches that control specific operational modes of the SAJ inverter, translating user actions into commands for the hub.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/text.py`

*   **Name:** `text.py`
*   **Function:** This file defines `SajTimeTextEntity`, which creates writable text entities for setting charge and discharge start/end times in `HH:MM` format. It validates user input against a regex pattern and calls specific setter methods on the `SAJModbusHub` to update the inverter's configuration. It avoids redundant Modbus requests by not using `async_update`.
*   **Architecture Role:** Writable Text Entity Implementation. This module provides entities that allow users to input and modify time-based settings for charging and discharging schedules, translating user input into Modbus commands via the hub.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/__init__.py`

*   **Name:** `__init__.py`
*   **Function:** This file serves as the main entry point for the SAJ Modbus integration. It handles the setup and unloading of the integration, creates the central `SAJModbusHub` instance (which manages data fetching and coordination), and forwards the setup to the relevant platforms (sensor, switch, number, text). It also manages the integration's lifecycle, including unloading and option updates.
*   **Architecture Role:** Integration Entry Point and Coordinator Setup. This file initializes the integration, sets up the central `SAJModbusHub` (acting as the coordinator), and directs the setup process to the appropriate platform integrations, managing the overall lifecycle of the SAJ Modbus integration within Home Assistant.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)

## `custom_components/saj_h2_modbus/number.py`

*   **Name:** `number.py`
*   **Function:** This file defines `SajGenericNumberEntity`, which creates writable number entities for various configuration parameters such as export limits, app modes, battery power limits, and passive mode settings. It uses `NUMBER_DEFINITIONS` to configure each entity's properties (key, name, min/max values, step, unit, setter method) and interacts with the `SAJModbusHub` to update these settings on the inverter.
*   **Architecture Role:** Number Entity Implementation. This module provides entities that allow users to input and modify numerical settings for the SAJ inverter, translating user input into Modbus commands via the hub.

Referenz: Basierend auf Informationen aus `/docs/index.md` (Sektion: ## 🏗 1. Architektur & Grundlagen)
