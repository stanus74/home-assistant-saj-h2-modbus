# Graph Report - .  (2026-07-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 518 nodes · 902 edges · 19 communities (13 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 27 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d66629ca`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ChargeSettingHandler
- SAJModbusHub
- modbus_utils.py
- modbus_readers.py
- SajSensor
- SajTimeTextEntity
- MqttPublisher
- CodeAnalyzer
- CodeAnalyzer
- utils.py
- ModbusConnectionManager
- BaseSajSwitch
- __init__.py
- Any
- Lock
- AddConfigEntryEntitiesCallback
- CoordinatorEntity
- SAJModbusHub
- Logger

## God Nodes (most connected - your core abstractions)
1. `SAJModbusHub` - 46 edges
2. `ChargeSettingHandler` - 37 edges
3. `MqttPublisher` - 21 edges
4. `ModbusConnectionManager` - 18 edges
5. `_read_configured_data()` - 17 edges
6. `SajSensor` - 17 edges
7. `ConnectionCache` - 15 edges
8. `BaseSajSwitch` - 15 edges
9. `CodeAnalyzer` - 13 edges
10. `CodeAnalyzer` - 13 edges

## Surprising Connections (you probably didn't know these)
- `CommandType` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `Command` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `ChargeSettingHandler` --uses--> `SAJModbusHub`  [INFERRED]
  custom_components/saj_h2_modbus/charge_control.py → custom_components/saj_h2_modbus/hub.py
- `read_passive_battery_data()` --indirect_call--> `ReconnectionNeededError`  [INFERRED]
  custom_components/saj_h2_modbus/modbus_readers.py → custom_components/saj_h2_modbus/modbus_utils.py
- `ModbusConnectionManager` --uses--> `CircuitBreaker`  [INFERRED]
  custom_components/saj_h2_modbus/services.py → custom_components/saj_h2_modbus/modbus_utils.py

## Import Cycles
- None detected.

## Communities (19 total, 6 thin omitted)

### Community 0 - "ChargeSettingHandler"
Cohesion: 0.05
Nodes (37): ChargeSettingHandler, Command, CommandType, Any, Enum, Optimized charge control with exponential backoff and improved error handling., Handler for all Charge/Discharge-Settings using a Command Queue., Adds a new command to the queue and starts processing if needed. (+29 more)

### Community 1 - "SAJModbusHub"
Cohesion: 0.05
Nodes (29): Any, ConfigEntry, HomeAssistant, Initialise all asyncio locks and synchronisation primitives., Initialise fast/ultra-fast polling callback handles and listener registry., Initialise charge/discharge control handler, setters and cache cleanup timer., Initializes dynamic setters., Set a power state with pending flag and trigger processing. (+21 more)

### Community 2 - "modbus_utils.py"
Cohesion: 0.07
Nodes (43): CircuitBreaker, _connect_client_inplace(), ConnectionCache, _create_retry_handlers(), _exponential_backoff(), get_modbus_circuit_breaker(), ModbusCircuitBreaker, _on_modbus_retry() (+35 more)

### Community 3 - "modbus_readers.py"
Cohesion: 0.13
Nodes (46): decode_time(), _decode_time_power_slots(), _log_partial_errors(), Lock, ModbusTcpClient, Emit a single log entry for partial decode failures., Helper function to read and decode Modbus data with partial-error resilience., Reads basic inverter data using the pymodbus 3.9 API. (+38 more)

### Community 4 - "SajSensor"
Cohesion: 0.07
Nodes (27): AddConfigEntryEntitiesCallback, CoordinatorEntity, create_sensor_descriptions(), A class that describes SAJ H2 sensor entities., SajModbusSensorEntityDescription, SensorGroup, SAJ Modbus Hub with optimized processing and fixed interval system., async_setup_entry() (+19 more)

### Community 5 - "SajTimeTextEntity"
Cohesion: 0.06
Nodes (29): async_setup_entry(), AddConfigEntryEntitiesCallback, Any, ConfigEntry, HomeAssistant, SAJModbusHub, SAJ H2 Modbus number entities., Base class for SAJ writable number entities. (+21 more)

### Community 6 - "MqttPublisher"
Cohesion: 0.08
Nodes (22): MqttPublisher, Any, Manages MQTT publishing via HA or internal Paho client., Compute strategy cache key based on relevant inputs., Return True if the HA MQTT integration is loaded and available., Derive the correct MQTT strategy from the current configuration.          Priori, Decide once which MQTT strategy to use with minimal logging., Load paho.mqtt.client in executor to avoid blocking the event loop. (+14 more)

### Community 7 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 8 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 9 - "utils.py"
Cohesion: 0.11
Nodes (20): host_valid(), HomeAssistant, Return the options flow to allow configuration changes after setup., Handle an options flow for SAJ Modbus., Prefer non-empty option prefix, fallback to data, then 'saj'., Return True if hostname or IP address is valid., Return the hosts already configured., SAJ Modbus configflow. (+12 more)

### Community 10 - "ModbusConnectionManager"
Cohesion: 0.09
Nodes (14): ModbusConnectionManager, HomeAssistant, Lock, ModbusTcpClient, Forces a reconnection by closing and re-opening the single client socket., Close the socket on the single client without destroying the client object., Close the socket. The client object itself is kept alive for reuse., Mark connection cache as immediately expired after a read/write error. (+6 more)

### Community 11 - "BaseSajSwitch"
Cohesion: 0.12
Nodes (10): async_setup_entry(), BaseSajSwitch, AddConfigEntryEntitiesCallback, ConfigEntry, CoordinatorEntity, HomeAssistant, Set the switch state with shared logic.          Sets pending state and triggers, Check cached bitmask + AppMode for charging/discharging switches. (+2 more)

### Community 12 - "__init__.py"
Cohesion: 0.17
Nodes (18): async_setup(), async_setup_entry(), async_unload_entry(), async_update_options(), _create_device_info(), _create_hub(), ConfigEntry, HomeAssistant (+10 more)

## Knowledge Gaps
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SAJModbusHub` connect `SAJModbusHub` to `ChargeSettingHandler`, `BaseSajSwitch`, `SajSensor`, `__init__.py`?**
  _High betweenness centrality (0.301) - this node is a cross-community bridge._
- **Why does `ChargeSettingHandler` connect `ChargeSettingHandler` to `SAJModbusHub`?**
  _High betweenness centrality (0.170) - this node is a cross-community bridge._
- **Why does `create_logged_task()` connect `MqttPublisher` to `ChargeSettingHandler`, `utils.py`, `modbus_utils.py`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `SAJModbusHub` (e.g. with `ChargeSettingHandler` and `Command`) actually correct?**
  _`SAJModbusHub` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `ChargeSettingHandler` be split into smaller, more focused modules?**
  _Cohesion score 0.0528169014084507 - nodes in this community are weakly interconnected._
- **Should `SAJModbusHub` be split into smaller, more focused modules?**
  _Cohesion score 0.052600818234950324 - nodes in this community are weakly interconnected._
- **Should `modbus_utils.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06829573934837092 - nodes in this community are weakly interconnected._