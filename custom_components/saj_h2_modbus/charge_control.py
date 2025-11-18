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
# NOTE: discharge_time_enable shares register 0x3605 with discharging_state (bitmask)
# NOTE: charge_time_enable shares register 0x3604 with charging_state
# Both handlers need to coordinate writes to avoid conflicts
SIMPLE_REGISTER_MAP: Dict[str, Tuple[int, str]] = {
    "export_limit": (REGISTERS["export_limit"], "export limit"),
    "app_mode": (REGISTERS["app_mode"], "app mode"),
    "charge_time_enable": (
        REGISTERS["charge_time_enable"],
        "charge time enable",
    ),
    "discharge_time_enable": (
        REGISTERS["discharge_time_enable"],
        "discharge time enable (bitmask)",
    ),
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
    """Factory for simple register handlers with retry logic.
    
    Attempts to write the pending value up to MAX_HANDLER_RETRIES times
    with HANDLER_RETRY_DELAY between attempts.
    """

    async def handler(self) -> bool:
        # Get pending value from hub
        value = getattr(self._hub, f"_pending_{pending_attr}", None)
        if value is None:
            _LOGGER.debug("Skip %s: no pending value", pending_attr)
            return False

        if address is None:
            _LOGGER.warning("%s register not configured; skip write", pending_attr)
            return False

        # Retry loop
        for attempt in range(1, MAX_HANDLER_RETRIES + 1):
            try:
                ok = await self._hub._write_register(address, int(value))
                if ok:
                    _LOGGER.info("Successfully set %s to: %s (attempt %d/%d)",
                                label, value, attempt, MAX_HANDLER_RETRIES)
                    try:
                        setattr(self._hub, f"_pending_{pending_attr}", None)
                    except Exception:
                        pass
                    return True
                else:
                    _LOGGER.warning("Failed to write %s (attempt %d/%d)",
                                   label, attempt, MAX_HANDLER_RETRIES)
            except Exception as e:
                _LOGGER.error("Error writing %s (attempt %d/%d): %s",
                             label, attempt, MAX_HANDLER_RETRIES, e)
            
            # Wait before retry (except on last attempt)
            if attempt < MAX_HANDLER_RETRIES:
                await asyncio.sleep(HANDLER_RETRY_DELAY)
        
        _LOGGER.error("Failed to write %s after %d attempts", label, MAX_HANDLER_RETRIES)
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
    """Handler für alle Charge/Discharge-Settings mit Decorator-Pattern."""
    
    def __init__(self, hub):
        self._hub = hub
        self._handlers: Dict[str, Callable] = {}
        self._register_handlers()
    
    def _register_handler(self, pending_attr: str) -> Callable:
        """Decorator zum Registrieren von Handler-Funktionen.
        
        Args:
            pending_attr: Name des Pending-Attributs (z.B. "_pending_charging_state")
        
        Returns:
            Decorator-Funktion
        """
        def decorator(func: Callable) -> Callable:
            self._handlers[pending_attr] = func
            _LOGGER.debug(f"Registered handler for '{pending_attr}': {func.__name__}")
            return func
        return decorator
    
    def get_handlers(self) -> Dict[str, Callable]:
        """Gibt alle registrierten Handler zurück."""
        return self._handlers.copy()
    
    def _register_handlers(self) -> None:
        """Registriere alle Handler: dynamisch aus SIMPLE_REGISTER_MAP + Spezialfälle."""
        # 1. Dynamische Handler aus SIMPLE_REGISTER_MAP
        for attr_name in SIMPLE_REGISTER_MAP:
            addr, label = SIMPLE_REGISTER_MAP[attr_name]
            pending_attr = f"_pending_{attr_name}"
            # _make_simple_handler gibt eine ungebundene Funktion zurück
            # Wir müssen sie als Methode an self binden
            unbound_handler = _make_simple_handler(attr_name, addr, label)
            bound_handler = unbound_handler.__get__(self, self.__class__)
            self._handlers[pending_attr] = bound_handler
            _LOGGER.debug(f"Registered dynamic handler for '{pending_attr}'")
        
        # 2. Spezialfälle: Power State Handler
        self._handlers["_pending_charging_state"] = self.handle_charging_state
        _LOGGER.debug("Registered special handler for '_pending_charging_state'")
        
        self._handlers["_pending_discharging_state"] = self.handle_discharging_state
        _LOGGER.debug("Registered special handler for '_pending_discharging_state'")
    
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

    # ========== STATISCHE HANDLER (Charge-Einstellungen) - REMOVED ==========
    # _handle_charge_group is no longer needed - replaced by handle_charge_settings_by_index

    async def handle_settings(self, mode: str, label: str) -> None:
        """Handles settings dynamically based on mode (charge1-7 or discharge1-7)."""
        _LOGGER.info(f"[PENDING DEBUG] handle_settings called for mode={mode}, label={label}")
        
        try:
            registers = REGISTERS[mode]
            _LOGGER.info(f"[PENDING DEBUG] Registers for {mode}: {registers}")

            # Determine if this is a charge or discharge slot
            if mode.startswith("charge"):
                index = int(mode.replace("charge", "")) - 1
                slot_pending = self._hub._pending_charges[index]
            else:  # discharge
                index = int(mode.replace("discharge", "")) - 1
                slot_pending = self._hub._pending_discharges[index]

            start_value = slot_pending.get("start")
            end_value = slot_pending.get("end")
            day_mask_value = slot_pending.get("day_mask")
            power_percent_value = slot_pending.get("power_percent")

            # Only write if there are pending values for this slot
            if not any(v is not None for v in [start_value, end_value, day_mask_value, power_percent_value]):
                _LOGGER.debug(f"No pending values for {mode}, skipping write.")
                return

            # Write start and end times if available
            if start_value is not None:
                if not self._is_valid_time_format(start_value):
                    _LOGGER.error(f"Ungültiges Zeitformat für Start ({start_value}) von {label}.")
                else:
                    _LOGGER.info(f"[PENDING DEBUG] Writing start time: {start_value}")
                    await self._write_time_register(registers["start_time"], start_value, f"{label} start")
            
            if end_value is not None:
                if not self._is_valid_time_format(end_value):
                    _LOGGER.error(f"Ungültiges Zeitformat für Ende ({end_value}) von {label}.")
                else:
                    _LOGGER.info(f"[PENDING DEBUG] Writing end time: {end_value}")
                    await self._write_time_register(registers["end_time"], end_value, f"{label} end")

            # Handle day mask and power percent
            if "day_mask_power" in registers:
                # If day_mask is not explicitly set, use 127 (all days)
                effective_day_mask = day_mask_value if day_mask_value is not None else 127
                
                # Validate power_percent
                if power_percent_value is not None and not (0 <= power_percent_value <= 100):
                    _LOGGER.error(f"Ungültiger Leistungsbereich für {label}: {power_percent_value}%. Erwartet 0-100.")
                    power_percent_value = None

                _LOGGER.info(f"[PENDING DEBUG] Calling _update_day_mask_and_power for {label}")
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    effective_day_mask,
                    power_percent_value,
                    label,
                )
            else:
                _LOGGER.warning(f"[PENDING DEBUG] No day_mask_power register found for {mode}")

        except Exception as e:
            _LOGGER.error(f"Error handling {label} settings: {e}", exc_info=True)
            return

        # Reset pending values for this specific slot
        _LOGGER.info(f"[PENDING DEBUG] Resetting pending values for {mode}")
        self._reset_pending_values(mode)

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
    
    async def _update_day_mask_and_power(
        self,
        address: int,
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str,
    ) -> None:
        """Updates the day mask and power percentage, reading current values if not provided.
        
        If power_percent is None and the register has never been set (both day_mask and power are 0),
        uses a default of 10% to ensure the time slot is actually active.
        """
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
            success = await self._hub._write_register(address, combined_value)

            if success:
                _LOGGER.info(
                    f"Successfully set {label} day_mask_power to: {combined_value} "
                    f"(day_mask: {new_day_mask}, power_percent: {new_power_percent})"
                )
            else:
                _LOGGER.error(f"Failed to write {label} day_mask_power")
        except Exception as e:
            _LOGGER.error(f"Error updating day mask and power for {label}: {e}")

    async def _write_time_register(
        self, address: int, time_str: str, label: str
    ) -> None:
        """Writes a time register in HH:MM format"""
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
        success = await self._hub._write_register(address, value)
        if success:
            _LOGGER.info(f"Successfully set {label}: {time_str}")
        else:
            _LOGGER.error(f"Failed to write {label}")

    # ========== POWER STATE HANDLER (Charging/Discharging) ==========
    
    async def handle_charging_state(self) -> None:
        """Handles the pending charging state.
        
        Writes to register 0x3604:
        - OFF: writes 0 to disable
        - ON: writes 1 to enable (charging control)
        """
        _LOGGER.debug("handle_charging_state called")
        desired = self._hub._pending_charging_state
        if desired is None:
            _LOGGER.debug("No pending charging state to handle")
            return

        _LOGGER.debug(f"Processing pending charging state: {desired}")
        
        addr = REGISTERS["charging_state"]
        write_value = 1 if desired else 0
        
        _LOGGER.info(
            f"Charging turned {'ON' if desired else 'OFF'}, writing {write_value} to register 0x3604"
        )
        
        ok = await self._hub._write_register(addr, write_value)
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3604")
        else:
            _LOGGER.info(f"Successfully wrote {write_value} to register 0x3604")
            self._hub.inverter_data["charging_enabled"] = write_value
            # Clear immediately after successful write
            self._hub._pending_charging_state = None
            _LOGGER.debug("Cleared _pending_charging_state after successful write")
        
        # Get current discharging state
        dchg = await self._hub.get_discharging_state()
        
        # Update AppMode based on both charging and discharging states
        await self._handle_power_state(charge_state=desired, discharge_state=dchg)

    async def handle_discharging_state(self) -> None:
        """Handles the pending discharging state.
        
        Writes to register 0x3605 (Bitmask):
        - OFF: writes 0 to disable all slots
        - ON: writes 1 (0b0000001) to enable first slot only
        
        Card can later modify this bitmask to enable multiple slots.
        """
        desired = self._hub._pending_discharging_state
        if desired is None:
            return

        _LOGGER.debug(f"Processing discharging state change: {desired}")
        
        addr = REGISTERS["discharging_state"]
        
        # Write to register 0x3605 based on desired state
        if not desired:
            # Discharging OFF: write 0 to disable all slots
            _LOGGER.info("Discharging turned OFF, writing 0 to register 0x3605 to disable all slots")
            write_value = 0
        else:
            # Discharging ON: write 1 (enable first slot only)
            # Card can later enable additional slots by modifying the bitmask
            _LOGGER.info("Discharging turned ON, writing 1 to register 0x3605 to enable first slot")
            write_value = 1
        
        ok = await self._hub._write_register(addr, write_value)
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3605")
        else:
            _LOGGER.info(f"Successfully wrote {write_value} to register 0x3605")
            self._hub.inverter_data["discharging_enabled"] = write_value
            # Clear immediately after successful write
            self._hub._pending_discharging_state = None
            _LOGGER.debug(f"Cleared _pending_discharging_state after successful write ({'ON' if desired else 'OFF'})")
        
        # Get current charging state
        chg = await self._hub.get_charging_state()
        
        # Update AppMode based on both charging and discharging states
        await self._handle_power_state(charge_state=chg, discharge_state=desired)

    async def _handle_power_state(
        self,
        charge_state: Optional[bool] = None,
        discharge_state: Optional[bool] = None,
    ) -> None:
        """Update AppMode based on charging/discharging states."""
        chg, dchg = await asyncio.gather(
            (
                self._hub.get_charging_state()
                if charge_state is None
                else asyncio.sleep(0, result=charge_state)
            ),
            (
                self._hub.get_discharging_state()
                if discharge_state is None
                else asyncio.sleep(0, result=discharge_state)
            ),
        )
        if chg is None or dchg is None:
            _LOGGER.debug(
                "Skip power-state handling: state not ready (chg=%s, dchg=%s)",
                chg,
                dchg,
            )
            return

        app_mode = self._hub.inverter_data.get("AppMode")
        if app_mode is None:
            _LOGGER.debug("Skip power-state handling: AppMode not ready")
            return

        desired_mode = 1 if (chg or dchg) else 0
        if app_mode != desired_mode:
            _LOGGER.info("Updating AppMode from %s to %s", app_mode, desired_mode)
            await self._hub._write_register(REGISTERS["app_mode"], desired_mode)