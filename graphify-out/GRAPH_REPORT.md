# Graph Report - .  (2026-07-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 513 nodes · 924 edges · 20 communities (18 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 30 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2bb0d5ea`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ChargeSettingHandler
- modbus_utils.py
- modbus_readers.py
- __init__.py
- SajTimeTextEntity
- SajSensor
- MqttPublisher
- CodeAnalyzer
- CodeAnalyzer
- ModbusConnectionManager
- BaseSajSwitch
- ._async_update_data
- SAJModbusHub
- .__init__
- ._cleanup_fast_update_callbacks
- create_logged_task
- .merge_write_register
- CoordinatorEntity
- Logger
- ._async_update_fast

## God Nodes (most connected - your core abstractions)
1. `SAJModbusHub` - 44 edges
2. `ChargeSettingHandler` - 39 edges
3. `MqttPublisher` - 24 edges
4. `ModbusConnectionManager` - 21 edges
5. `_read_configured_data()` - 17 edges
6. `SajSensor` - 16 edges
7. `ConnectionCache` - 15 edges
8. `BaseSajSwitch` - 15 edges
9. `try_read_registers()` - 14 edges
10. `create_logged_task()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `CommandType` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `Command` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `ChargeSettingHandler` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `SAJModbusHub` --uses--> `BlockUnsupportedError`  [INFERRED]
  custom_components/saj_h2_modbus/hub.py → custom_components/saj_h2_modbus/modbus_utils.py
- `SAJModbusHub` --uses--> `ReconnectionNeededError`  [INFERRED]
  custom_components/saj_h2_modbus/hub.py → custom_components/saj_h2_modbus/modbus_utils.py

## Import Cycles
- None detected.

## Communities (20 total, 2 thin omitted)

### Community 0 - "ChargeSettingHandler"
Cohesion: 0.06
Nodes (33): ChargeSettingHandler, Command, Any, Handler for all Charge/Discharge-Settings using a Command Queue., Adds a new command to the queue and starts processing if needed., Processes the command queue., Executes a single command based on its type., Stop queue processing and drain pending commands. (+25 more)

### Community 1 - "modbus_utils.py"
Cohesion: 0.07
Nodes (44): SAJ Modbus Hub with optimized processing and fixed interval system., CircuitBreaker, _connect_client_inplace(), ConnectionCache, _create_retry_handlers(), _exponential_backoff(), get_modbus_circuit_breaker(), ModbusCircuitBreaker (+36 more)

### Community 2 - "modbus_readers.py"
Cohesion: 0.13
Nodes (46): decode_time(), _decode_time_power_slots(), _log_partial_errors(), Lock, ModbusTcpClient, Emit a single log entry for partial decode failures., Helper function to read and decode Modbus data with partial-error resilience., Reads basic inverter data using the pymodbus 3.9 API. (+38 more)

### Community 3 - "__init__.py"
Cohesion: 0.07
Nodes (36): host_valid(), HomeAssistant, Return the options flow to allow configuration changes after setup., Handle an options flow for SAJ Modbus., Prefer non-empty option prefix, fallback to data, then 'saj'., Return True if hostname or IP address is valid., Return the hosts already configured., SAJ Modbus configflow. (+28 more)

### Community 4 - "SajTimeTextEntity"
Cohesion: 0.06
Nodes (29): async_setup_entry(), AddConfigEntryEntitiesCallback, Any, ConfigEntry, HomeAssistant, SAJModbusHub, SAJ H2 Modbus number entities., Base class for SAJ writable number entities. (+21 more)

### Community 5 - "SajSensor"
Cohesion: 0.07
Nodes (27): CoordinatorEntity, create_sensor_descriptions(), A class that describes SAJ H2 sensor entities., SajModbusSensorEntityDescription, SensorGroup, async_setup_entry(), FastPollSensor, AddConfigEntryEntitiesCallback (+19 more)

### Community 6 - "MqttPublisher"
Cohesion: 0.09
Nodes (17): MqttPublisher, Any, Manages MQTT publishing via HA or internal Paho client., Compute strategy cache key based on relevant inputs., Return True if the HA MQTT integration is loaded and available., Derive the correct MQTT strategy from the current configuration.          Priori, Decide once which MQTT strategy to use with minimal logging., Load paho.mqtt.client in executor to avoid blocking the event loop. (+9 more)

### Community 7 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 8 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 9 - "ModbusConnectionManager"
Cohesion: 0.09
Nodes (14): ModbusConnectionManager, HomeAssistant, Lock, ModbusTcpClient, Forces a reconnection by closing and re-opening the single client socket., Close the socket on the single client without destroying the client object., Close the socket. The client object itself is kept alive for reuse., Mark connection cache as immediately expired after a read/write error. (+6 more)

### Community 10 - "BaseSajSwitch"
Cohesion: 0.12
Nodes (10): async_setup_entry(), BaseSajSwitch, AddConfigEntryEntitiesCallback, ConfigEntry, CoordinatorEntity, HomeAssistant, Set the switch state with shared logic.          Sets pending state and triggers, Check cached bitmask + AppMode for charging/discharging switches. (+2 more)

### Community 11 - "._async_update_data"
Cohesion: 0.33
Nodes (4): Any, Regular poll cycle (slow)., Executes all readers using the provided client., Publish fast-poll sensor values to MQTT.

### Community 12 - "SAJModbusHub"
Cohesion: 0.22
Nodes (5): Set a power state with pending flag and trigger processing., Immediately process pending settings., Clean up stale RMW locks (idle > TTL)., Periodically clean up stale connection cache entries and reset daily exclusions., SAJModbusHub

### Community 13 - ".__init__"
Cohesion: 0.22
Nodes (5): ConfigEntry, HomeAssistant, Initialise fast/ultra-fast polling callback handles and listener registry., Initialise charge/discharge control handler, setters and cache cleanup timer., Initializes dynamic setters.

### Community 14 - "._cleanup_fast_update_callbacks"
Cohesion: 0.18
Nodes (5): Start an update loop with the given interval., Schedule an update loop robustly based on HA startup state., Start fast update loops based on configuration., Update connection settings. Full signature restored to support positional argume, Clean up all fast update callbacks.

### Community 15 - "create_logged_task"
Cohesion: 0.22
Nodes (9): CommandType, Enum, Optimized charge control with exponential backoff and improved error handling., # NOTE: Editing a slot's time/day-mask/power does NOT auto-enable it., create_logged_task(), HomeAssistant, Schedule a coroutine as a background HA task and log any unhandled exception., Logger (+1 more)

### Community 16 - ".merge_write_register"
Cohesion: 0.27
Nodes (5): Track lock ordering to detect potential deadlocks in nested paths., Helper for charge_control.py to write via connection service.          Uses dedi, Wait for any pending write operation to finish – bounded to prevent         infi, Helper for charge_control.py to read via connection service.          Waits for, Read-modify-write with per-register lock to preserve shared bits.

### Community 19 - "._async_update_fast"
Cohesion: 0.22
Nodes (5): Lock, Initialise all asyncio locks and synchronisation primitives., Execute Modbus read with one-shot retry for fast poll cycle.          Returns th, Notify HA entity listeners about updated fast-poll sensor data.          Only ca, Perform fast update of sensor data with performance optimizations.          PERF

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SAJModbusHub` connect `SAJModbusHub` to `ChargeSettingHandler`, `modbus_utils.py`, `modbus_readers.py`, `__init__.py`, `MqttPublisher`, `ModbusConnectionManager`, `BaseSajSwitch`, `._async_update_data`, `.__init__`, `._cleanup_fast_update_callbacks`, `create_logged_task`, `.merge_write_register`, `._async_update_fast`?**
  _High betweenness centrality (0.245) - this node is a cross-community bridge._
- **Why does `ChargeSettingHandler` connect `ChargeSettingHandler` to `modbus_utils.py`, `SAJModbusHub`, `.__init__`, `create_logged_task`?**
  _High betweenness centrality (0.186) - this node is a cross-community bridge._
- **Why does `MqttPublisher` connect `MqttPublisher` to `modbus_utils.py`, `SAJModbusHub`, `.__init__`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `SAJModbusHub` (e.g. with `ChargeSettingHandler` and `Command`) actually correct?**
  _`SAJModbusHub` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `MqttPublisher` (e.g. with `SAJModbusHub` and `CircuitBreaker`) actually correct?**
  _`MqttPublisher` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `ChargeSettingHandler` be split into smaller, more focused modules?**
  _Cohesion score 0.0574400723654455 - nodes in this community are weakly interconnected._
- **Should `modbus_utils.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06721215663354763 - nodes in this community are weakly interconnected._