# Graph Report - .  (2026-07-25)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 505 nodes · 928 edges · 21 communities
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b28e3b98`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20

## God Nodes (most connected - your core abstractions)
1. `SAJModbusHub` - 54 edges
2. `ChargeSettingHandler` - 39 edges
3. `MqttPublisher` - 24 edges
4. `ModbusConnectionManager` - 21 edges
5. `_read_configured_data()` - 17 edges
6. `SajSensor` - 17 edges
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

## Communities (21 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (32): ChargeSettingHandler, Command, Any, Handler for all Charge/Discharge-Settings using a Command Queue., Adds a new command to the queue and starts processing if needed., Processes the command queue., Executes a single command based on its type., Stop queue processing and drain pending commands. (+24 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (30): CircuitBreaker, ConnectionCache, ModbusCircuitBreaker, Circuit breaker pattern for Modbus operations (reads/connect)., Caches Modbus client connections to reduce connection overhead.      PERFORMANCE, Initialize connection cache.          Args:             cache_ttl: Time to live, Internal invalidate without lock. Must be called while holding _cache_lock., Get cached client if still valid.          Returns:             Cached client if (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (46): decode_time(), _decode_time_power_slots(), _log_partial_errors(), Lock, ModbusTcpClient, Emit a single log entry for partial decode failures., Helper function to read and decode Modbus data with partial-error resilience., Reads basic inverter data using the pymodbus 3.9 API. (+38 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (26): create_sensor_descriptions(), A class that describes SAJ H2 sensor entities., SajModbusSensorEntityDescription, SensorGroup, async_setup_entry(), FastPollSensor, AddConfigEntryEntitiesCallback, ConfigEntry (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (21): CodeAnalyzer, generate_report(), IssueReport, AST, AsyncFunctionDef, ClassDef, Enum, FunctionDef (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (17): MqttPublisher, Any, Manages MQTT publishing via HA or internal Paho client., Compute strategy cache key based on relevant inputs., Return True if the HA MQTT integration is loaded and available., Derive the correct MQTT strategy from the current configuration.          Priori, Decide once which MQTT strategy to use with minimal logging., Load paho.mqtt.client in executor to avoid blocking the event loop. (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (27): _connect_client_inplace(), _create_retry_handlers(), _exponential_backoff(), get_modbus_circuit_breaker(), _on_modbus_retry(), _perform_modbus_operation(), Any, Lock (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (11): Set the passive mode., async_setup_entry(), BaseSajSwitch, AddConfigEntryEntitiesCallback, ConfigEntry, CoordinatorEntity, HomeAssistant, Set the switch state with shared logic.          Sets pending state and triggers (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (13): host_valid(), HomeAssistant, Handle an options flow for SAJ Modbus., Prefer non-empty option prefix, fallback to data, then 'saj'., Return True if hostname or IP address is valid., Return the hosts already configured., SAJ Modbus configflow., Return True if host exists in configuration. (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (12): async_setup_entry(), AddConfigEntryEntitiesCallback, Any, ConfigEntry, HomeAssistant, SAJ H2 Modbus number entities., Base class for SAJ writable number entities., Generic class for SAJ number entities. (+4 more)

### Community 11 - "Community 11"
Cohesion: 0.18
Nodes (15): async_setup(), async_setup_entry(), async_unload_entry(), async_update_options(), _create_device_info(), _create_hub(), ConfigEntry, HomeAssistant (+7 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (7): Any, Regular poll cycle (slow)., Executes all readers using the provided client., Execute Modbus read with one-shot retry for fast poll cycle.          Returns th, Publish fast-poll sensor values to MQTT., Notify HA entity listeners about updated fast-poll sensor data.          Only ca, Perform fast update of sensor data with performance optimizations.          PERF

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (5): Set a power state with pending flag and trigger processing., Immediately process pending settings., Clean up stale RMW locks (idle > TTL)., Periodically clean up stale connection cache entries and reset daily exclusions., SAJModbusHub

### Community 14 - "Community 14"
Cohesion: 0.27
Nodes (9): SAJ Modbus Hub with optimized processing and fixed interval system., The SAJ Modbus integration., get_config_value(), get_config_values(), Any, ConfigEntry, Utility functions for SAJ H2 Modbus integration., Get multiple config values with fallback: options -> data -> default. (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.17
Nodes (7): ConfigEntry, HomeAssistant, Lock, Initialise all asyncio locks and synchronisation primitives., Initialise fast/ultra-fast polling callback handles and listener registry., Initialise charge/discharge control handler, setters and cache cleanup timer., Initializes dynamic setters.

### Community 16 - "Community 16"
Cohesion: 0.18
Nodes (5): Start an update loop with the given interval., Schedule an update loop robustly based on HA startup state., Start fast update loops based on configuration., Update connection settings. Full signature restored to support positional argume, Clean up all fast update callbacks.

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (9): CommandType, Enum, Optimized charge control with exponential backoff and improved error handling., # NOTE: Editing a slot's time/day-mask/power does NOT auto-enable it., create_logged_task(), HomeAssistant, Logger, Schedule a coroutine as a background HA task and log any unhandled exception. (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.27
Nodes (5): Track lock ordering to detect potential deadlocks in nested paths., Helper for charge_control.py to write via connection service.          Uses dedi, Wait for any pending write operation to finish – bounded to prevent         infi, Helper for charge_control.py to read via connection service.          Waits for, Read-modify-write with per-register lock to preserve shared bits.

### Community 19 - "Community 19"
Cohesion: 0.25
Nodes (8): async_setup_entry(), AddConfigEntryEntitiesCallback, ConfigEntry, HomeAssistant, Platform for writable SAJ Modbus time entities., Set up the writable time entities for Charge and Discharge., generate_slot_definitions(), Generate slot entity definitions for charge/discharge schedules.      This funct

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (6): Base class for SAJ writable time entities., Initialize the entity., Update is not used here to avoid additional Modbus requests., Set a new time value (Format 'HH:MM')., SajTimeTextEntity, TextEntity

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SAJModbusHub` connect `Community 13` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 14`, `Community 15`, `Community 16`, `Community 17`, `Community 18`?**
  _High betweenness centrality (0.354) - this node is a cross-community bridge._
- **Why does `ChargeSettingHandler` connect `Community 0` to `Community 8`, `Community 13`, `Community 14`, `Community 15`, `Community 17`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `MqttPublisher` connect `Community 6` to `Community 1`, `Community 13`, `Community 14`, `Community 15`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `SAJModbusHub` (e.g. with `ChargeSettingHandler` and `Command`) actually correct?**
  _`SAJModbusHub` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `MqttPublisher` (e.g. with `SAJModbusHub` and `CircuitBreaker`) actually correct?**
  _`MqttPublisher` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05961538461538462 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.0512987012987013 - nodes in this community are weakly interconnected._