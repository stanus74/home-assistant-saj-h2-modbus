# AI Agent Instructions for SAJ H2 Modbus Integration

**Status:** Updated Jan 26 2026 (v2.8.1) | **Project:** Unofficial Home Assistant integration for SAJ H2 inverters (reverse-engineered Modbus registers)

## Quick Start for AI Agents

**Before modifying code, understand (see also `docs/architecture_overview.md`):**

1.  **3-tier polling architecture** with separate asyncio locks (`_slow_lock`, `_fast_lock`, `_ultra_fast_lock`).
    *   **Standard (60s)**: Sequential execution of all readers.
    *   **Fast (10s)**: High-frequency sensors only.
    *   **Ultra-Fast (1s)**: MQTT-only, fire-and-forget, skipped during write operations.
2.  **Configuration-driven** register parsing - add sensors via `_DATA_READ_CONFIG` dicts.
3.  **Command queue pattern** for all writes - `ChargeSettingHandler` uses `asyncio.Queue` to serialize and prioritize writes over reads.
4.  **Strategy pattern** for MQTT - prefers HA MQTT, falls back to paho-mqtt.
5.  **Connection caching** in `ModbusConnectionManager` (60s TTL).
6.  **Parallel Execution**: Non-critical reader groups use independent locks, allowing `asyncio.gather` to execute Modbus requests concurrently where possible.

**Recent Major Fixes (v2.8.x):**
- ✅ **Slot Logic**: All charge/discharge slots (1-7) use a unified 7-bit mask in registers 0x3604/0x3605.
- ✅ **Data Integrity**: `_read_modbus_data()` returns `(data, errors)` tuple, preventing total data loss on partial read failures.
- ✅ **Write Guard**: Direct writes to 0x3604/0x3605 are blocked; use `merge_write_register()` to preserve shared bits.
- ✅ **Lifecycle**: Fast listeners unregister cleanly; Charge queue drains on unload.
- ✅ **AppMode**: Switches validate `AppMode == 1` for active charging/discharging state.

## Project Overview

**Context:** Unofficial community integration for reading SAJ H2 inverters (8kW-10kW) via Modbus TCP.

**Key Files:**
- [hub.py](../custom_components/saj_h2_modbus/hub.py) - DataUpdateCoordinator, polling orchestration.
- [modbus_readers.py](../custom_components/saj_h2_modbus/modbus_readers.py) - Configuration-driven register parsing.
- [modbus_utils.py](../custom_components/saj_h2_modbus/modbus_utils.py) - Low-level Modbus TCP, retry logic, connection caching.
- [charge_control.py](../custom_components/saj_h2_modbus/charge_control.py) - Async command queue for write operations.
- [services.py](../custom_components/saj_h2_modbus/services.py) - ModbusConnectionManager, MqttPublisher.
- [const.py](../custom_components/saj_h2_modbus/const.py) - Sensor definitions.
- [switch.py](../custom_components/saj_h2_modbus/switch.py) - Charging/Discharging and Passive Mode switches.

## Architecture & Data Flow

### Multi-Level Polling System

1.  **Standard (60s)**: Reads all data. Uses `_slow_lock`. Critical groups run sequentially; non-critical groups run in parallel using `asyncio.gather`.
2.  **Fast (10s)**: Reads `FAST_POLL_SENSORS` only. Uses `_fast_lock`. Updates HA entities.
3.  **Ultra-Fast (1s)**: Reads `FAST_POLL_SENSORS`. Uses `_ultra_fast_lock`. Publishes to MQTT only. **Skipped if a write operation is in progress.**

### Component Responsibilities

**SAJModbusHub**:
- Orchestrates polling loops.
- Manages `_merge_locks` for registers 0x3604/0x3605.
- Holds `inverter_data` (source of truth).

**ChargeSettingHandler**:
- Queues all commands (`CommandType`).
- `process_queue` runs in background task.
- Uses `_write_register_with_backoff` for reliability.
- **Optimistic UI**: Updates `inverter_data` immediately after write command is queued/processed to give instant feedback.

**ModbusReader**:
- `_read_modbus_data()`: Returns `new_data` dict and `errors` list. Even if some registers fail, valid data is returned.
- **Configuration**: Use `_DATA_READ_CONFIG` to add new registers/sensors.

**Switch Entities**:
- **Charging/Discharging**: Controls registers 0x3604/0x3605 + AppMode (0x3647).
- **Passive Mode**: Controls `passive_charge_enable` and AppMode=3. Controlled via `PASSIVE_SWITCH_KEYS` in `switch.py`.

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

**Merge locks:** Registers 0x3604 (charge slots) and 0x3605 (discharge slots) are pure slot bitmasks (bit 0 = Slot 1 … bit 6 = Slot 7). Use `_merge_locks` for read-modify-write to prevent corruption. **Special Case:** When disabling charging/discharging entirely (via Switch), the register must be set to `0` (clearing all slots).

```python
async with self._merge_locks[0x3604]:
    current = await read_registers(0x3604, 1)
    new_val = modifier(current) # Returns 0 if disabling, else toggles Bit 0
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

**Reader Resilience:** `_read_modbus_data()` returns a tuple `(data, errors)`.
```python
data, errors = await _read_modbus_data(...)
# Log errors but process valid 'data'
if errors:
    _LOGGER.warning("Partial read failure: %s", errors)
```

**Connection errors:** Always re-raise `ReconnectionNeededError` so hub can trigger reconnect:
```python
except ReconnectionNeededError:
    raise  # Critical - don't swallow!
except OtherError as e:
    _LOGGER.warning("Handled error: %s", e)
    return {}, [str(e)]
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

### Entity Write Pattern (Queue-Based)

Entities (Number, Switch) do **not** wait for Modbus confirmation blocking the UI. They use a fire-and-forget pattern with Optimistic UI updates.

```python
async def async_set_native_value(self, value):
    val = int(value)
    
    # 1. Validation
    if not self._attr_native_min_value <= val <= self._attr_native_max_value:
        return
    
    # 2. Optimistic update (instant UI feedback)
    self._attr_native_value = val
    self.async_write_ha_state()
    
    # 3. Queue command to device (Fire & Forget)
    if self.set_method:
         await self.set_method(val) # This queues, doesn't block for Modbus
```

**Why?**
- Prevents UI freezing during Modbus timeouts.
- `ChargeSettingHandler` ensures serialization and retries in background.
- If write ultimately fails (logged in background), state remains "wrong" in UI until next poll corrects it.

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
- ✅ Use `_merge_locks` for 0x3604/0x3605.
- ✅ Check `PENDING_FIELDS` when modifying charge control entity names.
- ✅ Ensure `AppMode` is handled when changing power states (Active=1, Passive=3).
- ✅ Write `0` to 0x3604/0x3605 when disabling functionality to clear all slots.

**DON'T:**
- ❌ Block the event loop with synchronous Modbus calls (use executor).
- ❌ Swallow `ReconnectionNeededError`.
- ❌ Direct write to 0x3604/0x3605 without merge logic.

## Known Issues

1.  **Naming**: Some entities use camelCase instead of snake_case (legacy).
2.  **Tests**: No automated test suite.
3.  **Slot Logic**: Only 7 slots supported (firmware limit).
4.  **Entity Optimization**: Rollback on write failure is not fully implemented (relies on next poll).

## Reference Commands

```bash
# View integration logs (HA CLI)
ha logs follow | grep saj_h2_modbus

# Reload integration after code changes
# (in HA Developer Tools -> Services -> Reload integration)
```

## Important Notes for AI Agents

1.  **Always verify lock usage** - wrong lock causes race conditions or polling delays.
2.  **Configuration-driven architecture** - favor adding entries to `_DATA_READ_CONFIG`.
3.  **Test optimistic updates** - UI should reflect changes instantly.
4.  **Register addresses are reverse-engineered**.
5.  **Check PENDING_FIELDS mismatch first** if charge entities don't sync.
6.  **Register 0x3604/0x3605 are slot masks**. Writing `0` clears all slots.
7.  **Queue cleanup critical** - ensure `ChargeSettingHandler` is shutdown properly.
8.  **ReconnectionNeededError bubbles up** - never swallow this exception.
9.  **AppMode 3 is Passive Mode** - requires special handling in switches.
