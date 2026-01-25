# AI Agent Instructions for SAJ H2 Modbus Integration

**Status:** Updated Jan 2026 | **Project:** Unofficial Home Assistant integration for SAJ H2 inverters (reverse-engineered Modbus registers)

## Quick Start for AI Agents

**Before modifying code, understand (see also `/plans/architecture_overview.md`):**

1. **3-tier polling architecture** with separate asyncio locks (`_slow_lock`, `_fast_lock`, `_ultra_fast_lock`) - never consolidate into one
2. **Configuration-driven** register parsing - add sensors via `_DATA_READ_CONFIG` dicts, not by modifying decode logic
3. **Command queue pattern** for all writes - charge control uses `asyncio.Queue` to prevent race conditions
4. **Strategy pattern** for MQTT - prefers HA MQTT, falls back to paho-mqtt
5. **Connection caching** in `ModbusConnectionManager` (60s TTL) - reduces lock contention significantly
6. **7 functional domains** (see `/plans/FUNKTIONSBEREICHE-ANALYSE.md`): Modbus reads, HA entity updates, MQTT publishing, charge control, config flow, entity optimization

**Fixed problems from analyse-010126.md:**
- ✅ Fast/Ultra-Fast loop scheduling bug fixed (pending handle management)
- ✅ Register 0x3604 merge lock strategy implemented (prevents charging state corruption)
- ✅ Queue cleanup in `async_unload_entry` implemented (no zombie tasks)
- ✅ Fast-listener lifecycle fixed (sensors unregister via `async_on_remove`, no log spam after removal)

## Project Overview

**Context:** Unofficial community integration (not endorsed by SAJ) for reading SAJ H2 inverters (8kW-10kW) via Modbus TCP with charging/discharging control and export limits. Register mappings are **empirically determined** (reverse-engineered, not from official docs) - firmware updates may break compatibility. See `/plans/architecture_overview.md` for the current high-level structure (3 polling loops, lock assignments, services, and queue).

**3-Tier Polling Architecture:**
- **60s (Standard)** - All 330+ registers, high-latency tolerance
- **10s (Fast)** - High-frequency sensors only (power, battery state), UI-responsive
- **1s (Ultra-Fast)** - MQTT-only critical metrics, not stored in HA (fire-and-forget)

**Core Innovation:** Separate asyncio locks allow concurrent polling without blocking. A slow 60s register read doesn't prevent 1s MQTT publishes.

**Key Files:**
- [hub.py](../custom_components/saj_h2_modbus/hub.py) - DataUpdateCoordinator, polling orchestration, state management
- [modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py) - Configuration-driven register parsing (add sensors here, not in hub)
- [modbus_utils.py](../custom_components/saj_h2_modbus/modbus_utils.py) - Low-level Modbus TCP, retry logic, connection caching
- [charge_control.py](../custom_components/saj_h2_modbus/charge_control.py) - Async command queue for write operations (prevents register corruption)
- [services.py](../custom_components/saj_h2_modbus/services.py) - ModbusConnectionManager (caching), MqttPublisher (strategy pattern)
- [const.py](../custom_components/saj_h2_modbus/const.py) - 390+ sensor definitions, device class mappings

## Architecture & Data Flow

### Multi-Level Polling System

The hub uses **three independent polling loops** with separate locks:

1. **Standard (60s)** - All 330+ registers via `_slow_lock` - calls all reader functions sequentially
2. **Fast (10s)** - Only keys in `FAST_POLL_SENSORS` via `_fast_lock` - calls `read_additional_modbus_data_1_part_2()` only
3. **Ultra-Fast (1s)** - MQTT-only via `_ultra_fast_lock` - calls fast reader, publishes immediately, no HA update

**Why separate locks?** MQTT at 1s would block all Modbus reads if using single `_read_lock`. Separate locks enable true concurrency.

**Critical Detail:** `_write_lock` is **separate from read locks** and has priority - charge operations don't wait for 60s reads.

### Component Responsibilities

**SAJModbusHub** ([hub.py](../custom_components/saj_h2_modbus/hub.py)):
- DataUpdateCoordinator subclass running standard 60s polling
- Manages three independent update loops with separate locks
- Orchestrates `ModbusConnectionManager` (connection/caching) and `MqttPublisher` (publish strategy)
- Maintains `inverter_data` dict as single source of truth (read-only for entities)
- Processes pending charge operations via `ChargeSettingHandler` before each polling cycle
- Supports optimistic state updates (`_pending_*_state` flags) for instant UI feedback

**ModbusUtils** ([modbus_utils.py](../custom_components/saj_h2_modbus/modbus_utils.py)):
- `_connect_client()` - unified connection logic with timeout handling
- `ConnectionCache` - 60s TTL caching reduces lock acquisitions by ~98% (measured empirically)
- Retry logic with exponential backoff: reads (2-10s), writes (1-5s)
- Per-operation locks prevent concurrent writes to same register (bit corruption prevention)
- Executor pattern for blocking Modbus calls (avoids freezing HA event loop)

**ModbusReaders** ([modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py)):
- Configuration-driven register parsing via `_DATA_READ_CONFIG` and `_PHASE_READ_CONFIG` dicts
- `_read_modbus_data()` - generic read/decode function (⚠️ **CRITICAL BUG**: returns `{}` on any error, losing all data - Phase 1 fix in todo.md)
- Stateless decoder functions (`read_realtime_data`, `read_battery_data`, `read_charge_data`, etc.)
- Special handling: BCD time decoding, power scaling, fault message bit extraction
- **To add sensor:** create entry in appropriate `*_MAP`, add to `_DATA_READ_CONFIG`, add to const.py, add to fast poll if needed

**ChargeSettingHandler** ([charge_control.py](../custom_components/saj_h2_modbus/charge_control.py)):
- Async command queue (`asyncio.Queue`) serializes all write operations
- Command types: `CHARGE_SLOT`, `DISCHARGE_SLOT`, `CHARGING_STATE`, `PASSIVE_MODE`, `SIMPLE_SETTING`
- `PENDING_FIELDS` mapping links entity names (e.g., `"charge1_start"`) to dot-path register addresses
- Read-modify-write for mask registers (0x3604, 0x3605) prevents bit corruption
- Exponential backoff retry (2^attempt seconds, capped at 16s) on write failure

**MqttPublisher** ([services.py](../custom_components/saj_h2_modbus/services.py)):
- Strategy pattern: attempts HA MQTT first, falls back to paho-mqtt if unavailable
- Publishes topic format: `{prefix}/inverter/{field_name}` or JSON payload
- Filters data: only fast sensors OR all data based on `CONF_MQTT_PUBLISH_ALL` flag
- Non-blocking - failures don't interrupt polling loops

**ModbusConnectionManager** ([services.py](../custom_components/saj_h2_modbus/services.py)):
- Manages single shared `ModbusTcpClient` instance with connection caching
- Double-check locking pattern prevents thundering herd on reconnect
- Cache invalidation on reconnect forces fresh connection check
- Exposes `get_client()` (async, caching) and `reconnect()` (force new connection)

### 7 Functional Domains (from `/plans/FUNKTIONSBEREICHE-ANALYSE.md`)

The codebase is organized into 7 independent functional areas:

1. **Modbus Register Reading** - Data ingestion, decoding, caching
2. **HA Entity Updates** - State publishing, fast listeners, registry management
3. **MQTT Publishing** - Strategy pattern, filtering, async publishing
4. **Charge Control** - Command queue, write operations, optimization
5. **Configuration Flow** - Setup UI, options, validation
6. **Entity Optimization** - Write confirmation, optimistic updates, error recovery
7. **Performance & Lifecycle** - Lock management, startup/shutdown, resource cleanup

## Development Patterns & Conventions

### Lock Management (Critical - Do Not Skip)

**Problem:** Using a single lock for all polling serializes operations, blocking fast updates behind slow ones.

**Solution:** Use appropriate lock based on operation type:
```python
# Read high-frequency data (10s loop)
async with self._fast_lock:
    data = await modbus_readers.read_additional_modbus_data_1_part_2(client, lock)

# Read all data (60s loop)  
async with self._slow_lock:
    data = await modbus_readers.read_realtime_data(client, lock)

# Write operations (prioritized)
async with self._write_lock:
    success = await hub._write_register(address, value)
```

**Merge locks:** Registers 0x3604 (charge slots) and 0x3605 (discharge slots) are pure slot bitmasks (bit 0 = Slot 1 … bit 6 = Slot 7). Use `_merge_locks` for read-modify-write to prevent corruption:
```python
async with self._merge_locks[0x3604]:
    current = await read_registers(0x3604, 1)
    new_val = modifier(current)
    await write_registers(0x3604, new_val)
```

**Critical:** Do **not** invent a dedicated "state" bit inside these registers. `charge_time_enable`/`discharge_time_enable` report only which slots are planned. Whether charging/discharging is *active* must be derived elsewhere (see `switch.py::_is_power_state_active()`, which checks `AppMode == 1 and mask > 0`).

### Configuration Priority & Fallback

When accessing config, **always** follow this cascade:
```python
def _get_config_value(entry, key, default=None):
    return entry.options.get(key, entry.data.get(key, default))
```

**Why:** Users change options frequently (config_entry.options), but setup data persists. Always prefer user's latest choice.

### Error Handling & Logging

**⚠️ CRITICAL BUG in `_read_modbus_data()`:**
```python
except Exception as e:
    _LOGGER.log(log_level_on_error, "Error reading modbus data: %s", e)
    return {}  # ← LOSES ALL DATA, even if 100 fields succeeded!
```
**Phase 1 fix:** Return tuple `(data, errors)` with per-field try-catch blocks (see Dev-Protocol/todo.md).

**Connection errors:** Always re-raise `ReconnectionNeededError` so hub can trigger reconnect:
```python
except ReconnectionNeededError:
    raise  # Critical - don't swallow!
except OtherError as e:
    _LOGGER.warning("Handled error: %s", e)
    return {}  # Safe to return empty
```

**Logging levels:**
- `ERROR` - Connection lost, data corruption, unhandled exceptions
- `WARNING` - Recoverable errors (invalid field, timeout with retry), ignored operations
- `INFO` - Config changes, component lifecycle (start/stop), important feature state
- `DEBUG` - Register values, decode details, performance metrics (use lazy evaluation: `%s` not f-strings)

### Data Type Conversions

**Time values (BCD format):**
```python
# Register 0x1234 = 0x0830 means 08:30
def decode_time(value: int) -> str:
    return f"{(value >> 8) & 0xFF:02d}:{value & 0xFF:02d}"
```

**Power scaling:**
```python
# Many registers store watts * 0.1, apply factor in _DATA_READ_CONFIG:
("pvPower", "16i", 0.1)  # Divide by 10 to get watts
```

**Bit masks (slots enable/disable):**
```python
# charge_time_enable = 0x0F means slots 1,2,3,4 enabled
# Bit 0 = charging state, Bits 1-6 = slot 1-7 enables, Bit 7 = reserved
enable_slot_3 = (current_value | (1 << 3))  # Set bit 3
disable_slot_3 = (current_value & ~(1 << 3))  # Clear bit 3
```

**32-bit registers (energy totals):**
```python
# Use consecutive register pairs, decode as UINT32
("totalenergy", "32u", 0.01)  # Reads 2 consecutive registers
```

## Common Tasks & Patterns

### Entity Write Confirmation (number.py, text.py, switch.py)

**Pattern for optimistic updates + write confirmation** (see `/plans/entity-optimization-plan.md`):

```python
async def async_set_native_value(self, value):
    val = int(value)
    
    # 1. Validation
    if not self._attr_native_min_value <= val <= self._attr_native_max_value:
        _LOGGER.error(f"Invalid value: {val}")
        return
    
    # 2. Optimistic update (instant UI feedback)
    old_value = self._attr_native_value
    self._attr_native_value = val
    self.async_write_ha_state()
    
    # 3. Write to the device
    if self.set_method:
        success = await self.set_method(val)
        if not success:
            _LOGGER.error(f"Failed to write: {val}")
            # Roll back on failure
            self._attr_native_value = old_value
            self.async_write_ha_state()
            return
    
    # 4. Verification (optional read-back after a delay)
    # await asyncio.sleep(0.5)
    # actual_value = self._hub.inverter_data.get(self._get_data_key())
    # if actual_value != val:
    #     _LOGGER.warning(f"Mismatch: expected {val}, got {actual_value}")
```

**Why 3 steps?**
- Optimistic update: users see the change immediately
- Write: send the Modbus command to the inverter
- Verification: ensure the value was actually written

### Adding a New Sensor (Complete Checklist)

1. **Define in modbus_readers.py** - Add to `*_MAP`:
   ```python
   ADDITIONAL_DATA_1_PART_1_MAP = [
       ("myNewSensor", "16u", 0.1),  # name, type, factor
   ]
   ```

2. **Add to config dict** (if it's a new reader function):
   ```python
   _DATA_READ_CONFIG["my_data"] = {
       "address": 0x4000,
       "count": 10,
       "decode_map": MY_MAP,
       "data_key": "my_data",
   }
   ```

3. **Add to const.py** - Define sensor description:
   ```python
   {"name": "My Sensor", "key": "myNewSensor", "enable": True, "icon": "flash"}
   ```

4. **If high-frequency:** Add to `FAST_POLL_SENSORS` in hub.py:
   ```python
   FAST_POLL_SENSORS = {"myNewSensor", ...}
   ```

### Adding Charge Control (Register Write)

1. **Add to MODBUS_ADDRESSES** in charge_control.py:
   ```python
   "my_setting": {"address": 0x3650, "label": "my setting"},
   ```

2. **Add to PENDING_FIELDS** mapping:
   ```python
   ("my_setting", "my_setting")
   ```

3. **Create command handler** or reuse `_handle_simple_setting()`:
   ```python
   await self._write_register_with_backoff(0x3650, value, "my setting")
   self._update_cache({"my_setting": value})
   ```

### Debugging Modbus Issues

**Enable verbose logging:**
```bash
# In terminal, set env vars:
export SAJ_DEBUG_MODBUS_READ=1
export SAJ_DEBUG_MODBUS_WRITE=1
```

**Check in order:**
1. Connection status: `ModbusConnectionManager.connected` and retry count in logs
2. Register address: grep for register in `modbus_readers.py` maps
3. Data decoding: search field name, verify type (`16i` vs `16u`) and factor
4. Frame timing: watch logs for duration of fast coordinator iterations (should be <1s)

### Testing with Real Inverter

- No automated test suite; manual testing via HA UI only
- Enable `ADVANCED_LOGGING = True` in hub.py to trace lock contention
- Check MQTT topic format: `{prefix}/inverter/{field_name}`
- Verify register addresses are correct (firmware versions may differ)

## Critical Gotchas

**DO:**
- ✅ Use `_ultra_fast_lock` for 1s MQTT loop (separate from fast/slow)
- ✅ Check `PENDING_FIELDS` when modifying charge control (entity name must match)
- ✅ Call `self.hub.async_set_updated_data()` after optimistic updates
- ✅ Re-raise `ReconnectionNeededError` from readers (hub needs to see it)
- ✅ Return early if `self._is_removed` in sensor entity updates

**DON'T:**
- ❌ Consolidate locks - breaks concurrency (e.g., don't merge `_slow_lock` and `_fast_lock`)
- ❌ Return empty `{}` on partial read errors - makes debugging impossible (fix in Phase 1)
- ❌ Add new sensors to hub directly - use `modbus_readers.py` + `const.py` instead
- ❌ Ignore `ReconnectionNeededError` - swallowing it breaks charge operations
- ❌ Use f-strings in logging - use `%s` for lazy evaluation (log only if level enabled)

## Known Issues & TODOs

1. **Data Loss Bug** - `_read_modbus_data()` returns `{}` on any error (Phase 1 fix: tuple with per-field errors)
2. **Naming** - Some entities use camelCase instead of snake_case (plan in todo.md)
3. **No Tests** - Manual testing only; automated suite needed
4. **Charge Slots** - Hardcoded to 7 slots max (firmware limit)
5. **Ultra-Fast** - MQTT-only, requires separate MQTT configuration
6. **Entity Optimization** - write-back confirmation and rollback not yet implemented (see `/plans/entity-optimization-plan.md`)
7. **Slot 1 Enable Logic** - Slot 1 doesn't explicitly set enable bit (works via 0x3604 state), Slots 2-7 do (should be consistent)

## Reference Commands

```bash
# View integration logs (HA CLI)
ha logs follow | grep saj_h2_modbus

# Reload integration after code changes
# (in HA Developer Tools -> Services -> Reload integration)
```

## Important Notes for AI Agents

1. **Always verify lock usage** - wrong lock causes race conditions or polling delays that manifest randomly
2. **Configuration-driven architecture** - favor adding entries to `_DATA_READ_CONFIG` over writing new reader functions
3. **Test optimistic updates** - UI should reflect changes instantly, HA should persist them after write confirmation
4. **Register addresses are reverse-engineered** - always test changes with real inverter (simulator doesn't exist)
5. **Check PENDING_FIELDS mismatch first** if charge entities don't sync - most common source of charge control bugs
6. **Register 0x3604/0x3605 are slot masks** - Bits 0-6 map to slots 1-7 (charge vs discharge). Treat them as pure bitmasks; the actual charging/discharging *state* is `AppMode == 1` **and** mask > 0 (handled in `switch.py`). Still use `merge_write_register` to avoid corrupting other slot bits.
7. **Queue cleanup critical** - ensure ChargeSettingHandler queue is drained in `async_unload_entry` to prevent zombie tasks on reload
8. **Fast listener lifecycle matters** - entity must unsubscribe from fast updates in `async_remove()` or risk dangling callbacks
9. **ReconnectionNeededError bubbles up** - never swallow this exception, always re-raise so hub can trigger reconnect
10. **MQTT circuit breaker** - ultra-fast mode uses tighter thresholds (3 failures, 30s timeout) vs fast mode (5/60s)
