# AI Agent Instructions for SAJ H2 Modbus Integration

This document helps AI agents understand the architecture and conventions of the SAJ H2 Modbus Home Assistant integration. answer in german language

## Project Overview

A Home Assistant integration for SAJ H2 inverters (8kW-10kW) that reads operational data via Modbus TCP and provides control over charging, discharging, and export limits. The integration uses **3-tier polling** (60s standard, 10s fast, 1s ultra-fast) with separate asyncio locks to prevent contention between polling levels.

**Key Files:**
- [custom_components/saj_h2_modbus/hub.py](../custom_components/saj_h2_modbus/hub.py) - Central coordinator and state manager
- [custom_components/saj_h2_modbus/modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py) - Data parsing/decoding
- [custom_components/saj_h2_modbus/modbus_utils.py](../custom_components/saj_h2_modbus/modbus_utils.py) - Low-level Modbus communication
- [custom_components/saj_h2_modbus/charge_control.py](../custom_components/saj_h2_modbus/charge_control.py) - Charge/discharge business logic
- [custom_components/saj_h2_modbus/config_flow.py](../custom_components/saj_h2_modbus/config_flow.py) - Configuration UI

## Architecture & Data Flow

### Multi-Level Polling System

The hub uses **three independent polling loops** with separate locks to prevent blocking:

1. **Standard (60s)** - All 330+ registers, uses `_slow_lock`
2. **Fast (10s)** - Only high-frequency sensors (power, battery status), uses `_fast_lock`  
3. **Ultra-Fast (1s)** - MQTT-only, critical metrics, uses `_ultra_fast_lock`

**Why separate locks?** MQTT operations at 1s intervals would block slower 60s reads. Separate locks allow concurrent polling at different speeds.

**Fast Poll Sensor Keys** (defined in [hub.py](../custom_components/saj_h2_modbus/hub.py)):
```python
FAST_POLL_SENSORS = {
    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower", "directionPV", "directionBattery",
    # ... (see hub.py for complete list)
}
```

### Component Responsibilities

**SAJModbusHub** - Orchestrates all operations:
- Manages Modbus connection via `ModbusConnectionManager`
- Publishes to MQTT via `MqttPublisher` 
- Processes charge/discharge requests via `ChargeSettingHandler`
- Maintains `inverter_data` dict as single source of truth
- Supports **optimistic updates** for instant UI feedback

**ModbusUtils** - Reliable communication:
- Retry logic with exponential backoff (2-10s for reads, 1-5s for writes)
- Connection caching with 60s TTL via `ConnectionCache`
- Async executor pattern to avoid blocking Home Assistant event loop
- Special handling for `ReconnectionNeededError` in charge operations

**ModbusReaders** - Data parsing:
- Stateless decoder functions (`_read_realtime_data`, `_read_battery_info`, etc.)
- Uses `_DATA_READ_CONFIG` and `_PHASE_READ_CONFIG` dicts to consolidate read parameters
- Handles special cases: fault message decoding, time format conversion (BCD)
- Returns `dict[str, Any]` (full dict even on partial errors - see todo.md for bug)

**ChargeSettingHandler** - Write operation queue:
- Serializes charge/discharge commands via `asyncio.Queue`
- Prevents race conditions during mask register merges
- Uses `PENDING_FIELDS` mapping to correlate entity names with Modbus registers
- Tracks "pending" charge settings before write confirmation

## Development Patterns & Conventions

### Lock Management (Critical for Concurrency)

When modifying polling logic:
- **Do NOT use single `_read_lock` for all polling** - this blocks fast/ultra-fast updates
- Use appropriate lock based on polling interval:
  ```python
  async with self._slow_lock:  # For 60s polling
      data = await try_read_registers(...)
  async with self._fast_lock:  # For 10s polling
      data = await try_read_registers(...)
  ```
- **Write operations use `_write_lock` (separate from read locks)** to prioritize writes over reads
- Merge locks (0x3604, 0x3605) exist for mask register operations that modify bit fields

### Error Handling & Logging

- Use structured logging: `_LOGGER.debug()`, `_LOGGER.info()`, `_LOGGER.warning()`
- **CRITICAL BUG:** `_read_modbus_data()` returns `{}` on ANY error, losing all read data. Phase 1 fix: tuple return `(data, errors)` with per-field try-catch (see [Dev-Protocol/todo.md](../Dev-Protocol/todo.md))
- Connection errors in charge operations catch `ReconnectionNeededError` for retry logic
- MQTT publish failures should NOT block main polling loops

### Data Type Handling

- Modbus registers return integers; decoding depends on field definition
- Time values: BCD format (0x0830 = 08:30) - decode in `_decode_time()`
- Power/energy: Often scaled (e.g., watts × 0.1 = actual value)
- Boolean flags: Often encoded in bit masks (e.g., `charge_time_enable` at bit 0x04)
- Device class mapping in [const.py](../custom_components/saj_h2_modbus/const.py) defines units and precision

### Configuration Priority

When accessing config values, follow this order:
1. `config_entry.options` (user-editable, takes priority)
2. `config_entry.data` (original setup values)
3. Default constant (fallback)

Example in [__init__.py](../custom_components/saj_h2_modbus/__init__.py):
```python
fast_enabled = _get_config_value(entry, CONF_FAST_ENABLED, False)
```

## Common Tasks & Examples

### Adding a New Sensor

1. Define in [modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py): Add to appropriate `*_MAP` dict
2. Add `SajModbusSensorEntityDescription` in [const.py](../custom_components/saj_h2_modbus/const.py)
3. Add to [sensor.py](../custom_components/saj_h2_modbus/sensor.py) entity factory
4. For high-frequency sensors, add key to `FAST_POLL_SENSORS` in [hub.py](../custom_components/saj_h2_modbus/hub.py)

### Adding Charge Control

1. Define pending field mapping in [charge_control.py](../custom_components/saj_h2_modbus/charge_control.py): `PENDING_FIELDS`
2. Add Modbus register addresses and validation in `ChargeSettingHandler`
3. Use `hub.charge_control_handler.queue_write()` to enqueue operation
4. Handler processes via asyncio Queue, merges mask registers, retries on failure

### Debugging Modbus Issues

Enable verbose logging in config, check:
1. Connection status via `ModbusConnectionManager` (retries 3x, logs on failure)
2. Register addresses in [modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py) map definitions
3. Data decoding in decoder functions (search for field name, check scaling/format)
4. Frame timing in fast coordinator (should complete in <1s per iteration)

## Known Limitations & TODOs

- **Data Loss Bug:** Empty `{}` returned on any read error instead of partial success (Phase 1 fix documented in todo.md)
- **File Naming:** Some modules use PascalCase (should be snake_case per todo.md)
- **Ultra-Fast Mode:** MQTT-only, requires explicit MQTT configuration
- **Charge Schedule:** Limited to 7 time slots per operation (hardcoded array size)

## Testing & Validation

- No automated test suite in main branch (see Dev-Protocol/ for analysis notes)
- Manual testing via Home Assistant UI: Services, automations, Lovelace cards
- Verify lock contention isn't blocking with debug logs: `ADVANCED_LOGGING = True` in [hub.py](../custom_components/saj_h2_modbus/hub.py)
- Check MQTT connectivity in ultra-fast mode: verify topic prefix and payload format

## Important Notes for AI Agents

1. **Always check PENDING_FIELDS mapping** when modifying charge-related code - mismatch breaks UI<->Modbus syncing
2. **Use appropriate locks** - wrong lock selection causes race conditions or polling delays
3. **Preserve optimistic updates** - instant UI feedback depends on `_optimistic_overlay` pattern
4. **Test with real inverter** - Modbus register addresses are reverse-engineered, edge cases exist
5. **Check lock contention first** if polling seems slow - likely culprit in concurrent operations
