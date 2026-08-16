# Graph Report - home-assistant-saj-h2-modbus  (2026-08-01)

## Corpus Check
- 15 files · ~25,083 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 518 nodes · 946 edges · 18 communities (17 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ef746614`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SAJModbusHub
- __init__.py
- modbus_readers.py
- hub.py
- SajSensor
- MqttPublisher
- CodeAnalyzer
- CodeAnalyzer
- ModbusConnectionManager
- BaseSajSwitch
- number.py
- SajTimeTextEntity
- ._async_update_fast
- ChargeSettingHandler
- .__init__
- .merge_write_register
- ._schedule_update_loop
- ._async_cleanup_cache

## God Nodes (most connected - your core abstractions)
1. `SAJModbusHub` - 55 edges
2. `ChargeSettingHandler` - 40 edges
3. `MqttPublisher` - 24 edges
4. `ModbusConnectionManager` - 21 edges
5. `_read_configured_data()` - 17 edges
6. `SajSensor` - 17 edges
7. `ConnectionCache` - 15 edges
8. `BaseSajSwitch` - 15 edges
9. `try_read_registers()` - 14 edges
10. `CodeAnalyzer` - 13 edges

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

## Communities (18 total, 1 thin omitted)

### Community 0 - "SAJModbusHub"
Cohesion: 0.20
Nodes (6): Set a power state with pending flag and trigger processing., Immediately process pending settings., Start fast update loops based on configuration., Update connection settings. Full signature restored to support positional…, Clean up all fast update callbacks., SAJModbusHub

### Community 1 - "__init__.py"
Cohesion: 0.07
Nodes (39): host_valid(), callback, HomeAssistant, Return the options flow to allow configuration changes after setup., Handle an options flow for SAJ Modbus., Prefer non-empty option prefix, fallback to data, then 'saj'., Return True if hostname or IP address is valid., Return the hosts already configured. (+31 more)

### Community 2 - "modbus_readers.py"
Cohesion: 0.13
Nodes (45): decode_time(), _decode_time_power_slots(), _log_partial_errors(), Lock, ModbusTcpClient, Emit a single log entry for partial decode failures., Helper function to read and decode Modbus data with partial-error resilience., Reads basic inverter data using the pymodbus 3.9 API. (+37 more)

### Community 3 - "hub.py"
Cohesion: 0.07
Nodes (44): SAJ Modbus Hub with optimized processing and fixed interval system., BlockUnsupportedError, CircuitBreaker, _connect_client_inplace(), ConnectionCache, _create_retry_handlers(), _exponential_backoff(), get_modbus_circuit_breaker() (+36 more)

### Community 4 - "SajSensor"
Cohesion: 0.08
Nodes (27): create_sensor_descriptions(), A class that describes SAJ H2 sensor entities., SajModbusSensorEntityDescription, SensorGroup, async_setup_entry(), FastPollSensor, AddConfigEntryEntitiesCallback, callback (+19 more)

### Community 5 - "MqttPublisher"
Cohesion: 0.07
Nodes (25): MqttCircuitBreaker, MqttPublisher, Any, HomeAssistant, Circuit breaker pattern for MQTT publishing., Manages MQTT publishing via HA or internal Paho client., Compute strategy cache key based on relevant inputs., Return True if the HA MQTT integration is loaded and available. (+17 more)

### Community 6 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 7 - "CodeAnalyzer"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 8 - "ModbusConnectionManager"
Cohesion: 0.09
Nodes (13): ModbusConnectionManager, Lock, ModbusTcpClient, Forces a reconnection by closing and re-opening the single client socket. Never…, Close the socket on the single client without destroying the client object., Close the socket. The client object itself is kept alive for reuse., Mark connection cache as immediately expired after a read/write error. Call…, Clean up stale cache entries and close socket if disconnected. (+5 more)

### Community 9 - "BaseSajSwitch"
Cohesion: 0.11
Nodes (11): Set the passive mode., async_setup_entry(), BaseSajSwitch, AddConfigEntryEntitiesCallback, ConfigEntry, CoordinatorEntity, HomeAssistant, Set the switch state with shared logic. Sets pending state and triggers… (+3 more)

### Community 10 - "number.py"
Cohesion: 0.12
Nodes (13): async_setup_entry(), AddConfigEntryEntitiesCallback, Any, ConfigEntry, HomeAssistant, SAJ H2 Modbus number entities., Base class for SAJ writable number entities., Generic class for SAJ number entities. (+5 more)

### Community 11 - "SajTimeTextEntity"
Cohesion: 0.11
Nodes (15): async_setup_entry(), AddConfigEntryEntitiesCallback, ConfigEntry, HomeAssistant, Platform for writable SAJ Modbus time entities., Update is not used here to avoid additional Modbus requests., Set a new time value (Format 'HH:MM')., Set up the writable time entities for Charge and Discharge. (+7 more)

### Community 12 - "._async_update_fast"
Cohesion: 0.18
Nodes (7): Any, Regular poll cycle (slow)., Executes all readers using the provided client., Execute Modbus read with one-shot retry for fast poll cycle. Returns the raw…, Publish fast-poll sensor values to MQTT., Notify HA entity listeners about updated fast-poll sensor data. Only called…, Perform fast update of sensor data with performance optimizations. PERFORMANCE…

### Community 13 - "ChargeSettingHandler"
Cohesion: 0.05
Nodes (38): ChargeSettingHandler, Command, CommandType, Any, callback, Enum, Optimized charge control with exponential backoff and improved error handling., Handler for all Charge/Discharge-Settings using a Command Queue. (+30 more)

### Community 14 - ".__init__"
Cohesion: 0.17
Nodes (7): ConfigEntry, HomeAssistant, Lock, Initialise all asyncio locks and synchronisation primitives., Initialise fast/ultra-fast polling callback handles and listener registry., Initialise charge/discharge control handler, setters and cache cleanup timer., Initializes dynamic setters.

### Community 15 - ".merge_write_register"
Cohesion: 0.27
Nodes (5): Track lock ordering to detect potential deadlocks in nested paths., Helper for charge_control.py to write via connection service. Uses dedicated…, Wait for any pending write operation to finish – bounded to prevent infinite…, Helper for charge_control.py to read via connection service. Waits for any…, Read-modify-write with per-register lock to preserve shared bits.

### Community 16 - "._schedule_update_loop"
Cohesion: 0.40
Nodes (3): callback, Start an update loop with the given interval., Schedule an update loop robustly based on HA startup state.

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SAJModbusHub` connect `SAJModbusHub` to `__init__.py`, `hub.py`, `SajSensor`, `MqttPublisher`, `ModbusConnectionManager`, `BaseSajSwitch`, `number.py`, `._async_update_fast`, `ChargeSettingHandler`, `.__init__`, `.merge_write_register`, `._schedule_update_loop`, `._async_cleanup_cache`?**
  _High betweenness centrality (0.362) - this node is a cross-community bridge._
- **Why does `ChargeSettingHandler` connect `ChargeSettingHandler` to `SAJModbusHub`, `BaseSajSwitch`, `hub.py`, `.__init__`?**
  _High betweenness centrality (0.197) - this node is a cross-community bridge._
- **Why does `MqttPublisher` connect `MqttPublisher` to `SAJModbusHub`, `hub.py`, `.__init__`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `SAJModbusHub` (e.g. with `ChargeSettingHandler` and `Command`) actually correct?**
  _`SAJModbusHub` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `MqttPublisher` (e.g. with `SAJModbusHub` and `CircuitBreaker`) actually correct?**
  _`MqttPublisher` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `__init__.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06914893617021277 - nodes in this community are weakly interconnected._
- **Should `modbus_readers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13429951690821257 - nodes in this community are weakly interconnected._