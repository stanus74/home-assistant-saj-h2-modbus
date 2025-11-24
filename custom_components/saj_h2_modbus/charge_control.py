"""Optimized charge control with exponential backoff and improved error handling."""
import asyncio
import logging
import re
from typing import Optional, Any, List, Dict, Tuple, Callable

_LOGGER = logging.getLogger(__name__)

# Retry configuration for handler write operations
MAX_HANDLER_RETRIES = 3
HANDLER_RETRY_DELAY = 1.0  # seconds

# --- Definitions for Pending Setter ---
PENDING_FIELDS: List[tuple[str, str]] = (
    [
        (f"charge{i}_{suffix}", f"charges[{i-1}][{suffix}]")
        for i in range(1, 8)
        for suffix in ["start", "end", "day_mask", "power_percent"]
    ]
    + [
        (f"discharge{i}_{suffix}", f"discharges[{i-1}][{suffix}]")
        for i in range(1, 8)
        for suffix in ["start", "end", "day_mask", "power_percent"]
    ]
    + [
        ("export_limit", "export_limit"),
        ("charging", "charging_state"),
        ("discharging", "discharging_state"),
        ("app_mode", "app_mode"),
        ("charge_time_enable", "charge_time_enable"),
        ("discharge_time_enable", "discharge_time_enable"),
        ("battery_on_grid_discharge_depth", "battery_on_grid_discharge_depth"),
        ("battery_off_grid_discharge_depth", "battery_off_grid_discharge_depth"),
        ("battery_capacity_charge_upper_limit", "battery_capacity_charge_upper_limit"),
        ("battery_charge_power_limit", "battery_charge_power_limit"),
        ("battery_discharge_power_limit", "battery_discharge_power_limit"),
        ("grid_max_charge_power", "grid_max_charge_power"),
        ("grid_max_discharge_power", "grid_max_discharge_power"),
        ("passive_charge_enable", "passive_charge_enable"),
        ("passive_grid_charge_power", "passive_grid_charge_power"),
        ("passive_grid_discharge_power", "passive_grid_discharge_power"),
        ("passive_bat_charge_power", "passive_bat_charge_power"),
        ("passive_bat_discharge_power", "passive_bat_discharge_power"),
    ]
)

# --- Centralized Modbus Address Definitions ---
CHARGE_BLOCK_START_ADDRESSES = [0x3606 + i * 3 for i in range(7)]
DISCHARGE_BLOCK_START_ADDRESSES = [0x361B + i * 3 for i in range(7)]

# --- Register Definitions ---
REGISTERS = {
    **{
        f"charge{i+1}": {
            "start_time": CHARGE_BLOCK_START_ADDRESSES[i],
            "end_time": CHARGE_BLOCK_START_ADDRESSES[i] + 1,
            "day_mask_power": CHARGE_BLOCK_START_ADDRESSES[i] + 2,
        }
        for i in range(7)
    },
    **{
        f"discharge{i+1}": {
            "start_time": DISCHARGE_BLOCK_START_ADDRESSES[i],
            "end_time": DISCHARGE_BLOCK_START_ADDRESSES[i] + 1,
            "day_mask_power": DISCHARGE_BLOCK_START_ADDRESSES[i] + 2,
        }
        for i in range(7)
    },
    "export_limit": 0x365A,
    "app_mode": 0x3647,
    "charging_state": 0x3604,
    "charge_time_enable": 0x3604,
    "discharging_state": 0x3605,
    "discharge_time_enable": 0x3605,
    "battery_on_grid_discharge_depth": 0x3644,
    "battery_off_grid_discharge_depth": 0x3645,
    "battery_capacity_charge_upper_limit": 0x3646,
    "battery_charge_power_limit": 0x364D,
    "battery_discharge_power_limit": 0x364E,
    "grid_max_charge_power": 0x364F,
    "grid_max_discharge_power": 0x3650,
    "passive_charge_enable": 0x3636,
    "passive_grid_charge_power": 0x3637,
    "passive_grid_discharge_power": 0x3638,
    "passive_bat_charge_power": 0x3639,
    "passive_bat_discharge_power": 0x363A,
}

# Mapping of simple pending attributes to their register addresses and labels
SIMPLE_REGISTER_MAP: Dict[str, Tuple[int, str]] = {
    "export_limit": (REGISTERS["export_limit"], "export limit"),
    "app_mode": (REGISTERS["app_mode"], "app mode"),
    "charge_time_enable": (REGISTERS["charge_time_enable"], "charge time enable"),
    "discharge_time_enable": (REGISTERS["discharge_time_enable"], "discharge time enable"),
    "battery_on_grid_discharge_depth": (
        REGISTERS["battery_on_grid_discharge_depth"],
        "battery on grid discharge depth",
    ),
    "battery_off_grid_discharge_depth": (
        REGISTERS["battery_off_grid_discharge_depth"],
        "battery off grid discharge depth",
    ),
    "battery_capacity_charge_upper_limit": (
        REGISTERS["battery_capacity_charge_upper_limit"],
        "battery capacity charge upper limit",
    ),
    "battery_charge_power_limit": (
        REGISTERS["battery_charge_power_limit"],
        "battery charge power limit",
    ),
    "battery_discharge_power_limit": (
        REGISTERS["battery_discharge_power_limit"],
        "battery discharge power limit",
    ),
    "grid_max_charge_power": (
        REGISTERS["grid_max_charge_power"],
        "grid max charge power",
    ),
    "grid_max_discharge_power": (
        REGISTERS["grid_max_discharge_power"],
        "grid max discharge power",
    ),
    "passive_charge_enable": (
        REGISTERS["passive_charge_enable"],
        "passive charge enable",
    ),
    "passive_grid_charge_power": (
        REGISTERS["passive_grid_charge_power"],
        "passive grid charge power",
    ),
    "passive_grid_discharge_power": (
        REGISTERS["passive_grid_discharge_power"],
        "passive grid discharge power",
    ),
    "passive_bat_charge_power": (
        REGISTERS["passive_bat_charge_power"],
        "passive battery charge power",
    ),
    "passive_bat_discharge_power": (
        REGISTERS["passive_bat_discharge_power"],
        "passive battery discharge power",
    ),
}


def _make_simple_handler(pending_attr: str, address: int, label: str):
    """Factory for simple register handlers with exponential backoff retry logic."""
    
    async def handler(self) -> bool:
        # Get pending value from hub
        value = getattr(self._hub, f"_pending_{pending_attr}", None)
        if value is None:
            _LOGGER.debug("Skip %s: no pending value", pending_attr)
            return False

        if address is None:
            _LOGGER.warning("%s register not configured; skip write", pending_attr)
            return False

        # Use exponential backoff retry
        ok = await self._write_register_with_backoff(address, int(value), label)
        if ok:
            try:
                setattr(self._hub, f"_pending_{pending_attr}", None)
            except Exception:
                pass
            return True
        
        _LOGGER.error("Failed to write %s after %d attempts with exponential backoff",
                     label, MAX_HANDLER_RETRIES)
        return False

    return handler


def make_pending_setter(attr_path: str):
    """Factory: returns an async method that sets a nested attribute on the hub."""
    
    async def setter(self, value: Any) -> None:
        """Sets a pending value on the hub."""
        try:
            if "[" in attr_path:
                parts = attr_path.replace("]", "").split("[")
                obj = getattr(self, f"_pending_{parts[0]}")
                for i, key in enumerate(parts[1:]):
                    if i == len(parts) - 2:
                        obj[int(key) if key.isdigit() else key] = value
                        break
                    obj = obj[int(key) if key.isdigit() else key]
            else:
                setattr(self, f"_pending_{attr_path}", value)
            
            # Invalidate pending cache when a value is set (for both nested and simple)
            if hasattr(self, '_invalidate_pending_cache'):
                self._invalidate_pending_cache()
        except Exception as e:
            _LOGGER.error(
                f"Error setting pending attribute '{attr_path}': {e}", exc_info=True
            )

    return setter


class ChargeSettingHandler:
    """Handler for all Charge/Discharge-Settings with Decorator-Pattern."""
    
    def __init__(self, hub):
        self._hub = hub
        self._handlers: Dict[str, Callable] = {}
        self._time_enable_cache: Dict[str, int] = {}  # Cache to avoid duplicate writes
        self._register_handlers()
    
    def _register_handler(self, pending_attr: str) -> Callable:
        """Decorator for registering handler functions."""
        def decorator(func: Callable) -> Callable:
            self._handlers[pending_attr] = func
            _LOGGER.debug(f"Registered handler for '{pending_attr}': {func.__name__}")
            return func
        return decorator
    
    def get_handlers(self) -> Dict[str, Callable]:
        """Return all registered handlers."""
        return self._handlers.copy()
    
    def _register_handlers(self) -> None:
        """Register all handlers: dynamically from SIMPLE_REGISTER_MAP + special cases."""
        # 1. Dynamic handlers from SIMPLE_REGISTER_MAP
        for attr_name in SIMPLE_REGISTER_MAP:
            addr, label = SIMPLE_REGISTER_MAP[attr_name]
            pending_attr = f"_pending_{attr_name}"
            unbound_handler = _make_simple_handler(attr_name, addr, label)
            bound_handler = unbound_handler.__get__(self, self.__class__)
            self._handlers[pending_attr] = bound_handler
            _LOGGER.debug(f"Registered dynamic handler for '{pending_attr}'")
        
        # 2. Power State Handler
        self._handlers["_pending_charging_state"] = self.handle_charging_state
        _LOGGER.debug("Registered special handler for '_pending_charging_state'")
        
        self._handlers["_pending_discharging_state"] = self.handle_discharging_state
        _LOGGER.debug("Registered special handler for '_pending_discharging_state'")
        
        _LOGGER.debug("time_enable handlers NOW ACTIVE via SIMPLE_REGISTER_MAP")

    # ========== HELPER METHODS ==========
    
    def _is_valid_time_format(self, time_str: str) -> bool:
        """Validates time format HH:MM."""
        if not isinstance(time_str, str):
            return False
        
        parts = time_str.split(":")
        if len(parts) != 2:
            return False
        
        try:
            hours, minutes = map(int, parts)
            return 0 <= hours < 24 and 0 <= minutes < 60
        except (ValueError, TypeError):
            return False

    async def handle_settings(self, mode: str, label: str) -> None:
        """Handles settings dynamically based on mode (charge1-7 or discharge1-7) with optimized batch processing."""
        _LOGGER.info(f"[PENDING DEBUG] handle_settings called for mode={mode}, label={label}")
        
        try:
            registers = REGISTERS[mode]
            _LOGGER.info(f"[PENDING DEBUG] Registers for {mode}: {registers}")

            # Determine if this is a charge or discharge slot
            if mode.startswith("charge"):
                index = int(mode.replace("charge", "")) - 1
                slot_pending = self._hub._pending_charges[index]
                is_charge = True
                time_enable_entity_id = REGISTERS["charge_time_enable"]
            else:  # discharge
                index = int(mode.replace("discharge", "")) - 1
                slot_pending = self._hub._pending_discharges[index]
                is_charge = False
                time_enable_entity_id = REGISTERS["discharge_time_enable"]

            start_value = slot_pending.get("start")
            end_value = slot_pending.get("end")
            day_mask_value = slot_pending.get("day_mask")
            power_percent_value = slot_pending.get("power_percent")

            # Only write if there are pending values for this slot
            if not any(v is not None for v in [start_value, end_value, day_mask_value, power_percent_value]):
                _LOGGER.debug(f"No pending values for {mode}, skipping write.")
                return

            # IMPORTANT: Check if slot has complete data (start, end, power are REQUIRED)
            has_complete_data = (
                start_value is not None and
                end_value is not None and
                power_percent_value is not None
            )

            if not has_complete_data:
                _LOGGER.warning(
                    f"[PENDING DEBUG] {label} incomplete: start={start_value}, end={end_value}, power={power_percent_value}. "
                    f"Skipping time_enable write. Please provide start time, end time AND power."
                )
                self._reset_pending_values(mode)
                return

            # Batch write operations for better performance
            write_operations = []
            
            # Add start and end times if available
            if start_value is not None:
                if not self._is_valid_time_format(start_value):
                    _LOGGER.error(f"Invalid time format for start ({start_value}) of {label}.")
                else:
                    _LOGGER.info(f"[PENDING DEBUG] Adding start time: {start_value}")
                    write_operations.append((registers["start_time"], self._time_to_register_value(start_value), f"{label} start"))
    
            if end_value is not None:
                if not self._is_valid_time_format(end_value):
                    _LOGGER.error(f"Invalid time format for end ({end_value}) of {label}.")
                else:
                    _LOGGER.info(f"[PENDING DEBUG] Adding end time: {end_value}")
                    write_operations.append((registers["end_time"], self._time_to_register_value(end_value), f"{label} end"))

            # Handle day mask and power percent
            if "day_mask_power" in registers:
                # Read current day_mask from inverter cache if not provided
                if day_mask_value is None:
                    # Try to get current day_mask from inverter data cache
                    cache_key = f"{mode}_day_mask"
                    if cache_key in self._hub.inverter_data:
                        # Extract day_mask from cached day_mask_power value
                        cached_day_mask_power = self._hub.inverter_data.get(f"{mode}_day_mask_power", 0)
                        effective_day_mask = (cached_day_mask_power >> 8) & 0xFF
                        _LOGGER.debug(f"[PENDING DEBUG] Using cached day_mask for {label}: {effective_day_mask}")
                    else:
                        # Fallback to default if not in cache
                        effective_day_mask = 127
                        _LOGGER.debug(f"[PENDING DEBUG] Using default day_mask for {label}: {effective_day_mask}")
                else:
                    effective_day_mask = day_mask_value
                
                if power_percent_value is not None and not (0 <= power_percent_value <= 100):
                    _LOGGER.error(f"Invalid power range for {label}: {power_percent_value}%. Expected 0-100.")
                    power_percent_value = None

                day_mask_power_value = self._calculate_day_mask_power_value(effective_day_mask, power_percent_value)
                if day_mask_power_value is not None:
                    _LOGGER.info(f"[PENDING DEBUG] Adding day_mask_power update for {label}")
                    write_operations.append((
                        registers["day_mask_power"],
                        day_mask_power_value,
                        f"{label} day_mask_power"
                    ))
                else:
                    _LOGGER.warning(f"[PENDING DEBUG] Skipping day_mask_power update for {label} - power_percent is None")
            else:
                _LOGGER.warning(f"[PENDING DEBUG] No day_mask_power register found for {mode}")

            # Execute all write operations in parallel where possible
            if write_operations:
                _LOGGER.info(f"[PENDING DEBUG] Executing {len(write_operations)} write operations for {label}")
                
                # Write all operations except time_enable
                for address, value, label in write_operations[:-1]:  # Exclude time_enable
                    await self._write_register_with_backoff(address, value, label)
                
                # Reset pending values for this specific slot
                _LOGGER.info(f"[PENDING DEBUG] Resetting pending values for {mode}")
                self._reset_pending_values(mode)
                
                # Handle time_enable separately for slots 2-7
                if index > 0:  # index 0 = Slot 1, skip it
                    cache_key = f"{'charge' if is_charge else 'discharge'}_time_enable"
                    
                    _LOGGER.info(f"[PENDING DEBUG] Starting time_enable update for {label} (index {index})")
                    
                    # Add delay to allow inverter to process previous writes
                    await asyncio.sleep(1.0)
                    
                    # Read current time_enable value
                    current_regs = await self._hub._read_registers(time_enable_entity_id, 1)
                    if not current_regs:
                        _LOGGER.error(f"[PENDING DEBUG] Failed to read current time_enable for {label}")
                        return
                    
                    current_mask = current_regs[0]
                    # IMPORTANT: Bit ADD (OR), not replace!
                    new_mask = current_mask | (1 << index)
                    
                    # Check cache to avoid duplicate writes
                    if cache_key in self._time_enable_cache and self._time_enable_cache[cache_key] == new_mask:
                        _LOGGER.debug(f"[PENDING DEBUG] {label} time_enable already cached with value {new_mask}, skipping write")
                        return
                    
                    if new_mask == current_mask:
                        _LOGGER.debug(f"[PENDING DEBUG] {label} already enabled in time_enable ({current_mask})")
                        # Update cache even if no write needed
                        self._time_enable_cache[cache_key] = new_mask
                        return
                    
                    _LOGGER.info(
                        f"[PENDING DEBUG] Enabling {label} in time_enable register: "
                        f"{current_mask} (binary: {bin(current_mask)}) → {new_mask} (binary: {bin(new_mask)})"
                    )
                    write_ok = await self._write_register_with_backoff(
                        time_enable_entity_id, new_mask, f"{label} time_enable"
                    )
                    
                    if not write_ok:
                        _LOGGER.error(f"[PENDING DEBUG] Failed to write time_enable for {label}")
                        return
                    
                    # Update cache immediately after successful write
                    self._time_enable_cache[cache_key] = new_mask
                    
                    # Wait for write to complete
                    await asyncio.sleep(0.3)
                    
                    # IMPORTANT: Read back to confirm
                    verify_regs = await self._hub._read_registers(time_enable_entity_id, 1)
                    if not verify_regs:
                        _LOGGER.error(f"[PENDING DEBUG] Failed to verify time_enable write for {label}")
                        return
                    
                    actual_value = verify_regs[0]
                    _LOGGER.info(
                        f"[PENDING DEBUG] Verified time_enable after write: {actual_value} (binary: {bin(actual_value)}) "
                        f"(expected: {new_mask})"
                    )
                    
                    # Update cache with ACTUAL value from inverter
                    if is_charge:
                        self._hub.inverter_data["charge_time_enable"] = actual_value
                        _LOGGER.info(f"[PENDING DEBUG] Updated cache: charge_time_enable = {actual_value}")
                    else:
                        self._hub.inverter_data["discharge_time_enable"] = actual_value
                        _LOGGER.info(f"[PENDING DEBUG] Updated cache: discharge_time_enable = {actual_value}")
                    
                    # Force immediate data update to UI
                    self._hub.async_set_updated_data(self._hub.inverter_data)
                    _LOGGER.info(f"[PENDING DEBUG] Forced UI update for {label}")
                    
                    if actual_value != new_mask:
                        _LOGGER.warning(
                            f"[PENDING DEBUG] Inverter returned different value! "
                            f"Wrote {new_mask}, got {actual_value}"
                        )
                        # Update cache with actual value from inverter
                        self._time_enable_cache[cache_key] = actual_value
                else:
                    _LOGGER.info(f"[PENDING DEBUG] Skipping time_enable write for Slot 1 (controlled by master switch)")

        except Exception as e:
            _LOGGER.error(f"Error handling {label} settings: {e}", exc_info=True)

    async def handle_charge_settings_by_index(self, index: int) -> None:
        """Handle charge settings for a specific slot index (1-7)."""
        mode = f"charge{index}"
        await self.handle_settings(mode, mode)

    async def handle_discharge_settings_by_index(self, index: int) -> None:
        """Handle discharge settings for a specific slot index (1-7)."""
        mode = f"discharge{index}"
        await self.handle_settings(mode, mode)

    def _reset_pending_values(self, mode: str) -> None:
        """Reset pending values for a charge or discharge slot."""
        attributes = ["start", "end", "day_mask", "power_percent"]
        if mode.startswith("charge"):
            index = int(mode.replace("charge", "")) - 1
            for attr in attributes:
                self._hub._pending_charges[index][attr] = None
        elif mode.startswith("discharge"):
            index = int(mode.replace("discharge", "")) - 1
            for attr in attributes:
                self._hub._pending_discharges[index][attr] = None

    # ========== HELPER METHODS (Reading/Writing Registers) ==========
    
    async def _write_register_with_backoff(self, address: int, value: int, label: str = "register") -> bool:
        """Write register with exponential backoff retry."""
        for attempt in range(1, MAX_HANDLER_RETRIES + 1):
            try:
                ok = await self._hub._write_register(address, int(value))
                if ok:
                    _LOGGER.info("Successfully wrote %s=%s to 0x%04x (attempt %d/%d)",
                                label, value, address, attempt, MAX_HANDLER_RETRIES)
                    return True
                else:
                    _LOGGER.warning("Failed to write %s (attempt %d/%d)",
                                   label, attempt, MAX_HANDLER_RETRIES)
            except Exception as e:
                _LOGGER.error("Error writing %s (attempt %d/%d): %s",
                             label, attempt, MAX_HANDLER_RETRIES, e)
            
            # Exponential backoff: 1s, 2s, 4s
            if attempt < MAX_HANDLER_RETRIES:
                delay = 2 ** (attempt - 1)
                _LOGGER.debug("Waiting %.1fs before retry (exponential backoff)", delay)
                await asyncio.sleep(delay)
        
        return False

    async def _update_day_mask_and_power(
        self,
        address: int,
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str,
    ) -> None:
        """Updates the day mask and power percentage, reading current values if not provided."""
        _LOGGER.info(
            f"[PENDING DEBUG] _update_day_mask_and_power called for {label}. "
            f"Provided day_mask: {day_mask}, power_percent: {power_percent}"
        )
        try:
            _LOGGER.debug(
                f"Reading current day_mask_power from address {hex(address)} for {label}"
            )
            regs = await self._hub._read_registers(address)
            if not regs:
                _LOGGER.error(
                    f"Failed to read current day_mask_power for {label} at address {hex(address)}. "
                    "No registers returned."
                )
                return

            current_value = regs[0]
            current_day_mask = (current_value >> 8) & 0xFF
            current_power_percent = current_value & 0xFF
            _LOGGER.debug(
                f"Current day_mask_power for {label}: {current_value} "
                f"(day_mask: {current_day_mask}, power_percent: {current_power_percent})"
            )

            # Use current day_mask if not provided
            new_day_mask = current_day_mask if day_mask is None else day_mask
            
            # Handle power_percent:
            # 1. If explicitly provided, use it
            # 2. If register is uninitialized (0/0), use default 10%
            # 3. Otherwise preserve current value
            if power_percent is not None:
                new_power_percent = power_percent
            elif current_value == 0:
                # Register never initialized - use default 10% to make slot active
                new_power_percent = 10
                _LOGGER.info(
                    f"Register for {label} uninitialized, using default power_percent: 10%"
                )
            else:
                # Preserve existing power_percent
                new_power_percent = current_power_percent
                _LOGGER.debug(f"Using current power_percent: {current_power_percent}% for {label}")
            
            _LOGGER.debug(
                f"Calculated new day_mask: {new_day_mask}, "
                f"new_power_percent: {new_power_percent} for {label}"
            )

            combined_value = (new_day_mask << 8) | new_power_percent

            if combined_value == current_value:
                _LOGGER.info(
                    f"No change detected for {label} day_mask_power. "
                    f"Current value: {current_value}. Not writing to Modbus."
                )
                return

            _LOGGER.debug(
                f"Writing combined value {combined_value} to register {hex(address)} for {label}"
            )
            success = await self._write_register_with_backoff(
                address, combined_value, f"{label} day_mask_power"
            )

            if success:
                _LOGGER.info(
                    f"Successfully set {label} day_mask_power to: {combined_value} "
                    f"(day_mask: {new_day_mask}, power_percent: {new_power_percent})"
                )
            else:
                _LOGGER.error(f"Failed to write {label} day_mask_power")
        except Exception as e:
            _LOGGER.error(f"Error updating day mask and power for {label}: {e}")

    def _time_to_register_value(self, time_str: str) -> int:
        """Convert time string HH:MM to register value."""
        parts = time_str.split(":")
        if len(parts) != 2:
            return 0
        
        try:
            hours, minutes = map(int, parts)
            return (hours << 8) | minutes
        except (ValueError, TypeError):
            return 0
    
    def _calculate_day_mask_power_value(self, day_mask: int, power_percent: Optional[int]) -> Optional[int]:
        """Calculate day_mask_power register value."""
        if power_percent is None:
            # Read current value to preserve power_percent
            return None  # Signal to read current value first
        
        return (day_mask << 8) | power_percent

    async def _write_time_register(
        self, address: int, time_str: str, label: str
    ) -> None:
        """Writes a time register in HH:MM format with exponential backoff retry."""
        parts = time_str.split(":")
        if len(parts) != 2:
            _LOGGER.error(f"Invalid time format for {label}: {time_str}")
            return

        try:
            hours, minutes = map(int, parts)
        except ValueError:
            _LOGGER.error(f"Non-integer time parts for {label}: {time_str}")
            return

        value = (hours << 8) | minutes
        success = await self._write_register_with_backoff(address, value, label)
        if success:
            _LOGGER.info(f"Successfully set {label}: {time_str}")
        else:
            _LOGGER.error(f"Failed to write {label}")

    # ========== POWER STATE HANDLER (Charging/Discharging) ==========
    
    async def handle_charging_state(self) -> bool:
        """Handles the pending charging state with optimized time_enable handling."""
        _LOGGER.debug("handle_charging_state called")
        desired = self._hub._pending_charging_state
        if desired is None:
            _LOGGER.debug("No pending charging state to handle")
            return False

        _LOGGER.debug(f"Processing pending charging state: {desired}")
        
        addr = REGISTERS["charging_state"]
        write_value = 1 if desired else 0
        
        _LOGGER.info(
            f"Charging turned {'ON' if desired else 'OFF'}, writing {write_value} to register 0x3604"
        )
        
        ok = await self._write_register_with_backoff(
            addr, write_value, "charging state (0x3604)"
        )
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3604")
            return False
        
        _LOGGER.info(f"Successfully wrote {write_value} to register 0x3604")
        self._hub.inverter_data["charging_enabled"] = write_value
        
        # Update charge_time_enable in cache to reflect new state (same register)
        self._hub.inverter_data["charge_time_enable"] = write_value
        
        # Update time_enable cache to avoid duplicate writes
        self._time_enable_cache["charge_time_enable"] = write_value
        
        # Set locks to prevent overwrites for next 10 seconds
        import time as time_module
        self._hub._charging_state_lock_until = time_module.monotonic() + 10.0
        self._hub._charge_time_enable_lock_until = time_module.monotonic() + 10.0
        _LOGGER.info(f"[PENDING DEBUG] Updated cache after charging state: charge_time_enable = {write_value} (LOCKED for 10s)")
        
        # Clear pending state
        self._hub._pending_charging_state = None
        _LOGGER.debug("Cleared _pending_charging_state after successful write")
        
        # Get current discharging state from cache (not async call)
        dchg_value = self._hub.inverter_data.get("discharging_enabled", 0)
        dchg = bool(dchg_value > 0)
        
        # Update AppMode: 1 if ANY is enabled, 0 if BOTH are disabled
        await self._update_app_mode_from_states(charge_enabled=desired, discharge_enabled=dchg)
        
        # Force immediate data update to UI
        self._hub.async_set_updated_data(self._hub.inverter_data)
        
        return True

    async def handle_discharging_state(self) -> bool:
        """Handles the pending discharging state with optimized time_enable handling."""
        desired = self._hub._pending_discharging_state
        if desired is None:
            return False

        _LOGGER.debug(f"Processing discharging state change: {desired}")
        
        addr = REGISTERS["discharging_state"]
        write_value = 0 if not desired else 1
        
        _LOGGER.info(
            f"Discharging turned {'OFF' if not desired else 'ON'}, "
            f"writing {write_value} to register 0x3605"
        )
        
        ok = await self._write_register_with_backoff(
            addr, write_value, "discharging state (0x3605)"
        )
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3605")
            return False
        
        _LOGGER.info(f"Successfully wrote {write_value} to register 0x3605")
        self._hub.inverter_data["discharging_enabled"] = write_value
        
        # Update discharge_time_enable in cache to reflect new state (same register)
        self._hub.inverter_data["discharge_time_enable"] = write_value
        
        # Update time_enable cache to avoid duplicate writes
        self._time_enable_cache["discharge_time_enable"] = write_value
        
        # Set locks to prevent overwrites for next 10 seconds
        import time as time_module
        self._hub._discharging_state_lock_until = time_module.monotonic() + 10.0
        self._hub._discharge_time_enable_lock_until = time_module.monotonic() + 10.0
        _LOGGER.info(f"[PENDING DEBUG] Updated cache after discharging state: discharge_time_enable = {write_value} (LOCKED for 10s)")
        
        # Clear pending state
        self._hub._pending_discharging_state = None
        _LOGGER.debug("Cleared _pending_discharging_state after successful write")
        
        # Get current charging state from cache (not async call)
        chg_value = self._hub.inverter_data.get("charging_enabled", 0)
        chg = bool(chg_value > 0)
        
        # Update AppMode: 1 if ANY is enabled, 0 if BOTH are disabled
        await self._update_app_mode_from_states(charge_enabled=chg, discharge_enabled=desired)
        
        # Force immediate data update to UI
        self._hub.async_set_updated_data(self._hub.inverter_data)
        
        return True

    async def _update_app_mode_from_states(
        self,
        charge_enabled: bool,
        discharge_enabled: bool,
    ) -> None:
        """Update AppMode (0x3647) based on charging/discharging states."""
        desired_app_mode = 1 if (charge_enabled or discharge_enabled) else 0
        
        current_app_mode = self._hub.inverter_data.get("AppMode")
        
        if current_app_mode == desired_app_mode:
            _LOGGER.info(f"AppMode already at {desired_app_mode}, skipping write")
            return
        
        _LOGGER.info(
            f"Updating AppMode from {current_app_mode} to {desired_app_mode} "
            f"(charge={charge_enabled}, discharge={discharge_enabled})"
        )
        
        ok = await self._write_register_with_backoff(
            REGISTERS["app_mode"], desired_app_mode, "AppMode"
        )
        if ok:
            _LOGGER.info(f"Successfully set AppMode to {desired_app_mode}")
            self._hub.inverter_data["AppMode"] = desired_app_mode
        else:
            _LOGGER.error(f"Failed to write AppMode {desired_app_mode}")