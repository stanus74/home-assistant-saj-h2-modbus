import logging
from typing import Optional, Any, List, Dict, Tuple, Callable, Awaitable

_LOGGER = logging.getLogger(__name__)

# --- Definitions for Pending Setter ---
PENDING_FIELDS: List[tuple[str, str]] = [
    (f"charge_{suffix}", f"charge_{suffix}") for suffix in ["start", "end", "day_mask", "power_percent"]
] + [
    (f"discharge{i}_{suffix}", f"discharges[{i-1}][{suffix}]") for i in range(1, 8) for suffix in ["start", "end", "day_mask", "power_percent"]
] + [
    ("export_limit", "export_limit"),
    ("charging", "charging_state"),
    ("discharging", "discharging_state"),
    ("app_mode", "app_mode"),
    ("discharge_time_enable", "discharge_time_enable"),
    ("battery_on_grid_discharge_depth", "battery_on_grid_discharge_depth"),
    ("battery_off_grid_discharge_depth", "battery_off_grid_discharge_depth"),
    ("battery_capacity_charge_upper_limit", "battery_capacity_charge_upper_limit"),
    ("battery_charge_power_limit", "battery_charge_power_limit"),
    ("battery_discharge_power_limit", "battery_discharge_power_limit"),
    ("grid_max_charge_power", "grid_max_charge_power"),
    ("grid_max_discharge_power", "grid_max_discharge_power"),
]

# --- Register Definitions ---
REGISTERS = {
    "charge": {
        "start_time": 0x3606,
        "end_time": 0x3607,
        "day_mask_power": 0x3608,
    },
    "discharge1": {
        "start_time": 0x361B,
        "end_time": 0x361C,
        "day_mask_power": 0x361D,
    },
    "discharge2": {
        "start_time": 0x361E,
        "end_time": 0x361F,
        "day_mask_power": 0x3620,
    },
    "discharge3": {
        "start_time": 0x3621,
        "end_time": 0x3622,
        "day_mask_power": 0x3623,
    },
    "discharge4": {
        "start_time": 0x3624,
        "end_time": 0x3625,
        "day_mask_power": 0x3626,
    },
    "discharge5": {
        "start_time": 0x3627,
        "end_time": 0x3628,
        "day_mask_power": 0x3629,
    },
    "discharge6": {
        "start_time": 0x362A,
        "end_time": 0x362B,
        "day_mask_power": 0x362C,
    },
    "discharge7": {
        "start_time": 0x362D,
        "end_time": 0x362E,
        "day_mask_power": 0x362F,
    },
    "export_limit": 0x365A,
    "app_mode": 0x3647,
    "charging_state": 0x3604,
    "discharging_state": 0x3605,
    "battery_on_grid_discharge_depth": 0x3644,
    "battery_off_grid_discharge_depth": 0x3645,
    "battery_capacity_charge_upper_limit": 0x3646,
    "battery_charge_power_limit": 0x364D,
    "battery_discharge_power_limit": 0x364E,
    "grid_max_charge_power": 0x364F,
    "grid_max_discharge_power": 0x3650,
}

# Mapping of simple pending attributes to their register addresses and labels
SIMPLE_REGISTER_MAP: Dict[str, Tuple[int, str]] = {
    "export_limit": (REGISTERS["export_limit"], "export limit"),
    "app_mode": (REGISTERS["app_mode"], "app mode"),
    "discharge_time_enable": (
        REGISTERS["discharging_state"],
        "discharge time enable",
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
}


def _make_simple_handler(pending_attr: str, address: int, label: str):
    """Factory for simple register handlers."""

    async def handler(self) -> None:
        await self._handle_simple_register(
            getattr(self._hub, f"_pending_{pending_attr}"),
            address,
            label,
            lambda: setattr(self._hub, f"_pending_{pending_attr}", None),
        )

    return handler


def make_pending_setter(attr_path: str):
    """
    Factory: returns an async method that sets a nested attribute on the hub.
    The returned function is a proper async method that will be bound to the hub instance.
    """
    async def setter(self, value: Any) -> None:
        """Sets a pending value on the hub."""
        try:
            # This logic handles both simple attributes and nested dictionary attributes
            if '[' in attr_path:
                # Handle nested dictionary access like "discharges[0][start]"
                parts = attr_path.replace(']', '').split('[')
                obj = getattr(self, f"_pending_{parts[0]}")
                for i, key in enumerate(parts[1:]):
                    if i == len(parts) - 2:
                        obj[int(key) if key.isdigit() else key] = value
                        break
                    obj = obj[int(key) if key.isdigit() else key]
            else:
                # Handle simple attribute access like "charge_start"
                setattr(self, f"_pending_{attr_path}", value)
        except Exception as e:
            _LOGGER.error(f"Error setting pending attribute '{attr_path}': {e}", exc_info=True)

    return setter

class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub

    async def handle_settings(self, mode: str, pending_attrs: List[str], label: str) -> None:
        """Handles settings dynamically based on mode and pending attributes."""
        try:
            registers = REGISTERS[mode]
            
            # Handle start_time and end_time
            for attr in ["start", "end"]:
                if mode.startswith("discharge"):
                    index = int(mode.replace("discharge", "")) - 1
                    value = self._hub._pending_discharges[index][attr]
                else:
                    value = getattr(self._hub, f"_pending_{mode}_{attr}", None)

                if value is not None:
                    reg_key = f"{attr}_time"
                    await self._write_time_register(registers[reg_key], value, f"{label} {attr}")

            # Handle day_mask and power_percent as a combined register
            # Handle day_mask and power_percent as a combined register
            day_mask_value = None
            power_percent_value = None

            if mode.startswith("discharge"):
                index = int(mode.replace("discharge", "")) - 1
                day_mask_value = self._hub._pending_discharges[index]["day_mask"]
                power_percent_value = self._hub._pending_discharges[index]["power_percent"]
            else:
                day_mask_value = getattr(self._hub, f"_pending_{mode}_day_mask", None)
                power_percent_value = getattr(self._hub, f"_pending_{mode}_power_percent", None)

            # Always call _update_day_mask_and_power for modes that have it
            # The _update_day_mask_and_power method handles reading current values and applying defaults
            if "day_mask_power" in registers:
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    day_mask_value,
                    power_percent_value,
                    label
                )

        except Exception as e:
            _LOGGER.error(f"Error handling {label} settings: {e}")
        finally:
            self._reset_pending_values(mode)

    async def handle_charge_settings(self) -> None:
        await self.handle_settings("charge", ["start", "end", "day_mask", "power_percent"], "charge")

    async def handle_discharge_settings_by_index(self, index: int) -> None:
        mode = f"discharge{index}"
        await self.handle_settings(mode, ["start", "end", "day_mask", "power_percent"], mode)

    def _reset_pending_values(self, mode: str) -> None:
        if mode.startswith("discharge"):
            index = int(mode.replace("discharge", "")) - 1
            for attr in ["start", "end", "day_mask", "power_percent"]:
                self._hub._pending_discharges[index][attr] = None
        else:
            attributes = ["start", "end", "day_mask", "power_percent"]
            for attr in attributes:
                pending_attr = f"_pending_{mode}_{attr}"
                if hasattr(self._hub, pending_attr):
                    setattr(self._hub, pending_attr, None)

    async def _update_day_mask_and_power(
        self,
        address: int,
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str
    ) -> None:
        """Updates the day mask and power percentage, reading current values if not provided."""
        _LOGGER.debug(f"Attempting to update day_mask_power for {label}. Provided day_mask: {day_mask}, power_percent: {power_percent}")
        try:
            _LOGGER.debug(f"Reading current day_mask_power from address {hex(address)} for {label}")
            regs = await self._hub._read_registers(address)
            if not regs:
                _LOGGER.error(f"Failed to read current day_mask_power for {label} at address {hex(address)}. No registers returned.")
                return

            current_value = regs[0]
            current_day_mask = (current_value >> 8) & 0xFF
            current_power_percent = current_value & 0xFF
            _LOGGER.debug(f"Current day_mask_power for {label}: {current_value} (day_mask: {current_day_mask}, power_percent: {current_power_percent})")

            new_day_mask = day_mask if day_mask is not None else 127 # Default to 127 if no day_mask is provided
            new_power_percent = power_percent if power_percent is not None else 5 # Default to 5 if no power_percent is provided
            _LOGGER.debug(f"Calculated new day_mask: {new_day_mask}, new_power_percent: {new_power_percent} for {label}")

            combined_value = (new_day_mask << 8) | new_power_percent

            if combined_value == current_value:
                _LOGGER.info(f"No change detected for {label} day_mask_power. Current value: {current_value}. Not writing to Modbus.")
                return

            _LOGGER.debug(f"Writing combined value {combined_value} to register {hex(address)} for {label}")
            success = await self._hub._write_register(address, combined_value)

            if success:
                _LOGGER.info(
                    f"Successfully set {label} day_mask_power to: {combined_value} (day_mask: {new_day_mask}, power_percent: {new_power_percent})"
                )
            else:
                _LOGGER.error(f"Failed to write {label} day_mask_power")
        except Exception as e:
            _LOGGER.error(f"Error updating day mask and power for {label}: {e}")


    async def _handle_simple_register(
        self, 
        value: Optional[Any], 
        address: int, 
        label: str,
        reset_callback: Callable[[], None]
    ) -> None:
        """Handles simple register write operations"""
        if value is not None:
            try:
                success = await self._hub._write_register(address, value)
                if success:
                    _LOGGER.info(f"Successfully set {label} to: {value}")
                else:
                    _LOGGER.error(f"Failed to write {label}")
            except Exception as e:
                _LOGGER.error(f"Error writing {label}: {e}")
            finally:
                reset_callback()

    async def handle_pending_charging_state(self) -> None:
        """Handles the pending charging state"""
        await self._handle_power_state(
            self._hub._pending_charging_state,
            self._hub.get_discharging_state,
            REGISTERS["charging_state"],
            "charging",
            lambda: setattr(self._hub, "_pending_charging_state", None)
        )

    async def handle_pending_discharging_state(self) -> None:
        """Handles the pending discharging state"""
        await self._handle_power_state(
            self._hub._pending_discharging_state,
            self._hub.get_charging_state,
            REGISTERS["discharging_state"],
            "discharging",
            lambda: setattr(self._hub, "_pending_discharging_state", None)
        )

    async def _handle_power_state(
        self, 
        state: Optional[bool], 
        get_other_state: Callable[[], Awaitable[bool]],
        state_register: int,
        label: str,
        reset_callback: Callable[[], None]
    ) -> None:
        """Common method for handling charging and discharging states"""
        if state is not None:
            other_state = await get_other_state()
            try:
                # Set app mode register (0x3647)
                app_mode_value = 1 if state or other_state else 0
                success_app_mode = await self._hub._write_register(REGISTERS["app_mode"], app_mode_value)
                if success_app_mode:
                    _LOGGER.info(f"Successfully set {label} (0x3647) to: {app_mode_value}")
                else:
                    _LOGGER.error(f"Failed to set {label} state (0x3647)")

                # Set state register
                reg_value = 1 if state else 0
                success_state = await self._hub._write_register(state_register, reg_value)
                if success_state:
                    _LOGGER.info(f"Successfully set register {hex(state_register)} to {reg_value}")
                else:
                    _LOGGER.error(f"Failed to set register {hex(state_register)}")
            except Exception as e:
                _LOGGER.error(f"Error handling pending {label} state: {e}")
            finally:
                reset_callback()

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

# Dynamically add simple register handlers to ChargeSettingHandler
for _attr, (_addr, _label) in SIMPLE_REGISTER_MAP.items():
    setattr(
        ChargeSettingHandler,
        f"handle_{_attr}",
        _make_simple_handler(_attr, _addr, _label),
    )
