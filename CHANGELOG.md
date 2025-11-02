# Changelog (v2.6.3)

### 🔧 Fix: Discharge Power Percent Reset

* Problem: When changing only the end time of a discharge slot, the `power_percent` was incorrectly reset to the default 5% instead of keeping the previously configured value.
* Solution: `_update_day_mask_and_power` now preserves the current `power_percent` read from the register when no pending `power_percent` is provided. `_reset_pending_values` is only called after a successful write in `handle_settings`.
* Impact: User-set `power_percent` values for discharge slots remain unchanged when only the time is edited.

### 🔧 Default Values for Time and Power Settings

* Implemented sensible defaults:
  - Default start time for charge/discharge slots: `01:00`
  - Default end time for charge/discharge slots: `01:10`
  - Default power percent for charge/discharge slots: `5%`
* Ensured `00:00` is not sent to Modbus as a default time.
* Defaults are applied only when a switch is enabled and no pending values are present.
* Enabled discharge slots persist across card reloads.
* Affected files: `text.py`, `switch.py`, `number.py`
* Benefit: Better user experience with sensible defaults and more reliable persistence.


### 🚀 Handler Architecture Refactor — Decorator Pattern & Central Handler Registry

- Centralized handler registration using `ChargeSettingHandler._register_handler()` (Decorator pattern).
- All pending handlers are registered in a single `_handlers` map; removed previous magic strings and distributed registration.
- Dynamically generated handlers (from `SIMPLE_REGISTER_MAP`) are correctly bound to the instance (unbound → bound using `__get__()`).
- Unified handler invocation in the hub — handlers are now called uniformly with no special case call signatures.
- Strict verification at initialization: missing handlers raise `RuntimeError` (fail-fast).
- Result: much improved maintainability, elimination of magic strings, easier addition of new handlers, and clearer logs.
- Quantitative: ~80% reduction in complexity within `_process_pending_settings`.

---

# Changelog (v2.6.2)

### 🔧 Enhanced Fast Coordinator and Connection Handling

* Fast coordinator lifecycle improvements:
  - Added `_fast_unsub` to store and manage unsubscribe callbacks.
  - `start_fast_updates()` now attaches listeners correctly using `async_add_listener()`.
  - `restart_fast_updates()` performs comprehensive cleanup of previous listeners and coordinators.
  - Improved error handling when attaching listeners.

* Modbus client management:
  - Added `_close_client()` for safe async client close.
  - Connection handling and reconnection logic improved with proper client cleanup and recreation.
  - Better logging and error handling across connection lifecycle.

* Handler name generation compatibility:
  - Handler naming keeps backward compatibility for `charging_state` and `discharging_state` while simplifying names for other attributes.
  - Smooth refactor without breaking existing behavior.

* Benefits: more robust fast coordinator handling, improved connection stability, and better resource management.

---

# Changelog (v2.6.1)

### 🚀 Handler Architecture: Decorator Pattern & Central Registration

* Centralized handler registration with `_register_handler` inside `ChargeSettingHandler`.
* `_handlers` dictionary is the single source of truth for all handlers.
* All handlers (dynamic and special cases) now registered from one place and correctly bound to the instance.
* Initialization verifies handler presence and raises on missing handlers.
* Simplified invocation: all handlers are called uniformly (`await handler_func()`).
* Benefits: improved maintainability, easier to add new handlers, clearer logs.

---

# Changelog (v2.6.0)

### 🚀 New Passive Charge/Discharge Input Registers

* Added input registers for passive charge/discharge controls:
  - Passive Charge Enable (input)
  - Passive Grid Charge Power (input)
  - Passive Grid Discharge Power (input)
  - Passive Battery Charge Power (input)
  - Passive Battery Discharge Power (input)
* These enable more granular passive battery charge/discharge control.

### 🚀 New Fast Sensors

* Fast coordinator (10s) now updates additional CT sensors:
  - `sensor.saj_ct_pv_power_watt`
  - `sensor.saj_ct_pv_power_va`
  - `sensor.saj_ct_grid_power_va`
  - `sensor.saj_ct_grid_power_watt`
* These sensors receive higher-frequency updates for improved live monitoring.

---

# Changelog (v2.5.0)

### 🚀 Fast Coordinator (10s) for Live Data

* Introduced a 10s fast coordinator for high-frequency polling of key metrics.
* Default: enabled. Can be disabled by configuring `FAST_POLL_DEFAULT = False` in `hub.py`.
* Energy sensors polled every 10s, including total load, PV, battery, grid, and inverter power.

### Major improvements

* Complete `hub.py` refactor for more robust Modbus handling and extensibility.
* Optimistic overlay for UI (shows planned state changes until Modbus confirms).
* Improved `_has_pending()` detection and safer setter generation.

---

# Changelog (v2.4.0)

### Code reduction and restructures

* Consolidated many `_pending_*` attributes into a single `_pending_settings` structure to improve maintainability.
* `ChargeSettingHandler` updated to use `_pending_settings`.
* Replaced many repetitive handlers with a generic `handle_settings` method.
* Added debug logging to trace pending settings and Modbus operations.
* Improvements to Modbus read handling and helper utilities (e.g., `_read_phase_block`).

---

# Changelog (v2.3.1)

### 🔧 Fix: Discharge Power Percent Reset

* Problem: Changing only the end time could reset `power_percent` to the default.
* Fix: Preserve existing `power_percent` when a pending `power_percent` is not provided. Only reset pending values after successful writes.

---

# Changelog (v2.3.0)

### 🔧 Default Values for Times and Power Percent

* Implemented defaults to avoid `00:00` and provide sensible startup values:
  - Start: `01:00`
  - End: `01:10`
  - Power percent: `5%`
* Defaults are applied on enable if no pending values exist. Improved persistence of enabled slots.

---

# Changelog (v2.2.2)

### 🔧 Fast Coordinator & Connection Handling Improvements

* Improved fast coordinator lifecycle management and listener cleanup.
* Added `_close_client()` and better reconnection/cleanup logic.
* Compatible handler naming during refactor to preserve existing behavior.

---

# Notes

* The changelog above summarizes the main changes and fixes across multiple releases (v2.2.2 → v2.6.3).
* Entries have been translated to English and consolidated for clarity.
* If you'd like the changelog split into separate dated entries or adjusted wording, tell me which sections to refine.
