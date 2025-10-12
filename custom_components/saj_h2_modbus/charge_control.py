import asyncio
import logging
from typing import Optional, Any, List, Dict, Tuple

_LOGGER = logging.getLogger(__name__)

# --- Definitions for Pending Setter ---
PENDING_FIELDS: List[tuple[str, str]] = (
    [
        (f"charge_{suffix}", f"charge_{suffix}")
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
DISCHARGE_BLOCK_START_ADDRESSES = [0x361B + i * 3 for i in range(7)]

# --- Register Definitions ---
REGISTERS = {
    "charge": {
        "start_time": 0x3606,
        "end_time": 0x3607,
        "day_mask_power": 0x3608,
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
    "discharging_state": 0x3605,
    "battery_on_grid_discharge_depth": 0x3644,
    "battery_off_grid_discharge_depth": 0x3645,
    "battery_capacity_charge_upper_limit": 0x3646,
    "battery_charge_power_limit": 0x364D,
    "battery_discharge_power_limit": 0x364E,
    "grid_max_charge_power": 0x364F,
    "grid_max_discharge_power": 0x3650,
    "discharge_time_enable": 0x3605,
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
    "discharge_time_enable": (
        REGISTERS["discharge_time_enable"],
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
    """Factory for simple register handlers that read the pending value, write on success, and reset the pending field."""

    async def handler(self) -> bool:
        # Get pending value from hub
        value = getattr(self._hub, f"_pending_{pending_attr}", None)
        if value is None:
            _LOGGER.debug("Skip %s: no pending value", pending_attr)
            return False

        try:
            if address is None:
                _LOGGER.warning("%s register not configured; skip write", pending_attr)
                return False
            ok = await self._hub._write_register(address, int(value))
            if ok:
                _LOGGER.info("Successfully set %s to: %s", label, value)
                # Only reset pending value on successful write
                try:
                    setattr(self._hub, f"_pending_{pending_attr}", None)
                except Exception:
                    pass
            else:
                _LOGGER.error("Failed to write %s", label)
                # Keep pending value so it can be retried later
            return ok
        except Exception as e:
            _LOGGER.error("Error writing %s: %s", label, e)
            # Keep pending value so it can be retried later
            return False

    return handler


def make_pending_setter(attr_path: str):
    """Factory: returns an async method that sets a nested attribute on the hub."""

    async def setter(self, value: Any) -> None:
        """Sets a pending value on the hub."""
        try:
            # This logic handles both simple attributes and nested dictionary attributes
            if "[" in attr_path:
                # Handle nested dictionary access like "discharges[0][start]"
                parts = attr_path.replace("]", "").split("[")
                obj = getattr(self, f"_pending_{parts[0]}")
                for i, key in enumerate(parts[1:]):
                    if i == len(parts) - 2:
                        obj[int(key) if key.isdigit() else key] = value
                        break
                    obj = obj[int(key) if key.isdigit() else key]
            else:
                # Handle simple attribute access like "charge_start"
                # Write directly to dedicated _pending_<field> attribute on the hub
                setattr(self, f"_pending_{attr_path}", value)
        except Exception as e:
            _LOGGER.error(
                f"Error setting pending attribute '{attr_path}': {e}", exc_info=True
            )

    return setter


class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub

    async def handle_settings(self, mode: str, label: str) -> None:
        """Handles settings dynamically based on mode."""
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
                    await self._write_time_register(
                        registers[reg_key], value, f"{label} {attr}"
                    )

            # Handle day_mask and power_percent as a combined register
            day_mask_value = None
            power_percent_value = None
            # Initialize day_mask and power_percent with default values if not provided
            if mode.startswith("discharge"):
                index = int(mode.replace("discharge", "")) - 1
                day_mask_value = self._hub._pending_discharges[index].get("day_mask")
                power_percent_value = self._hub._pending_discharges[index].get("power_percent")
            else:
                day_mask_value = getattr(self._hub, f"_pending_{mode}_day_mask")
                power_percent_value = getattr(self._hub, f"_pending_{mode}_power_percent")

            # Always call _update_day_mask_and_power for modes that have it
            # The _update_day_mask_and_power method handles reading current values and applying defaults
            if "day_mask_power" in registers:
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    day_mask_value,
                    power_percent_value,
                    label,
                )

        except Exception as e:
            _LOGGER.error(f"Error handling {label} settings: {e}")
        finally:
            self._reset_pending_values(mode)

    async def handle_charge_settings(self) -> None:
        await self.handle_settings("charge", "charge")

    async def handle_discharge_settings_by_index(self, index: int) -> None:
        mode = f"discharge{index}"
        await self.handle_settings(mode, mode)

    def _reset_pending_values(self, mode: str) -> None:
        attributes = ["start", "end", "day_mask", "power_percent"]
        if mode.startswith("discharge"):
            index = int(mode.replace("discharge", "")) - 1
            for attr in attributes:
                self._hub._pending_discharges[index][attr] = None
        else:
            for attr in attributes:
                pending_attr = f"_pending_{mode}_{attr}"
                if hasattr(self._hub, pending_attr):
                    setattr(self._hub, pending_attr, None)

    async def _update_day_mask_and_power(
        self,
        address: int,
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str,
    ) -> None:
        """Updates the day mask and power percentage, reading current values if not provided."""
        _LOGGER.debug(
            f"Attempting to update day_mask_power for {label}. "
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

            new_day_mask = current_day_mask if day_mask is None else day_mask
            new_power_percent = current_power_percent if power_percent is None else power_percent
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

    async def handle_charging_state(self) -> None:
        """Handles the pending charging state (robust, without default writes)."""
        _LOGGER.debug("handle_charging_state called")
        desired = self._hub._pending_charging_state
        if desired is None:
            _LOGGER.debug("No pending charging state to handle")
            return

        _LOGGER.debug(f"Processing pending charging state: {desired}")
        chg, dchg = await asyncio.gather(
            self._hub.get_charging_state(),  # Optional[bool]
            self._hub.get_discharging_state(),  # Optional[bool]
        )
        app_mode = self._hub.inverter_data.get("AppMode")
        if chg is None or dchg is None or app_mode is None:
            _LOGGER.debug("Deferring pending charging_state: prerequisites not ready")
            return

        # Write if register exists
        addr = REGISTERS["charging_state"]
        write_value = 1 if desired else 0
        _LOGGER.info(
            "Attempting to write value %s to register %s for charging_state",
            write_value,
            hex(addr),
        )
        _LOGGER.debug("Calling _hub._write_register for charging_state...")
        ok = False  # Initialize ok to False
        try:
            _LOGGER.debug("Executing await self._hub._write_register...")
            ok = await self._hub._write_register(addr, write_value)
            _LOGGER.info(
                "await self._hub._write_register completed. Result: %s", ok
            )
            if ok:
                self._hub.inverter_data["is_charging"] = bool(desired)
                _LOGGER.info(f"Successfully wrote charging state: {desired}")
                # Only reset pending value on successful write
                self._hub._pending_charging_state = None
        except Exception as e:
            _LOGGER.error(
                "Error writing charging_state to register %s: %s", hex(addr), e
            )
            ok = False  # Ensure ok is False if an exception occurs
            # Keep pending value so it can be retried later
        
        # Only handle power state if the write was successful
        if ok:
            await self._handle_power_state(charge_state=desired)
        
        _LOGGER.debug("handle_charging_state completed")

    async def handle_discharging_state(self) -> None:
        """Handles the pending discharging state (robust, without default writes)."""
        desired = self._hub._pending_discharging_state
        if desired is None:
            return

        chg, dchg = await asyncio.gather(
            self._hub.get_charging_state(),  # Optional[bool]
            self._hub.get_discharging_state(),  # Optional[bool]
        )
        app_mode = self._hub.inverter_data.get("AppMode")
        if chg is None or dchg is None or app_mode is None:
            _LOGGER.debug(
                "Deferring pending discharging_state: prerequisites not ready"
            )
            return

        addr = REGISTERS["discharging_state"]
        ok = False  # Initialize ok to False
        try:
            ok = await self._hub._write_register(addr, 1 if desired else 0)
            if ok:
                self._hub.inverter_data["is_discharging"] = bool(desired)
                # Only reset pending value on successful write
                self._hub._pending_discharging_state = None
        except Exception as e:
            _LOGGER.error(
                "Error writing discharging_state to register %s: %s", hex(addr), e
            )
            ok = False  # Ensure ok is False if an exception occurs
            # Keep pending value so it can be retried later
        
        # Only handle power state if the write was successful
        if ok:
            await self._handle_power_state(discharge_state=desired)

    async def _handle_power_state(
        self,
        charge_state: Optional[bool] = None,
        discharge_state: Optional[bool] = None,
    ) -> None:
        # Get charge/discharge flags from hub, if not passed
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
        # If states not ready yet: skip and try again in next cycle
        if chg is None or dchg is None:
            _LOGGER.debug(
                "Skip power-state handling: state not ready (chg=%s, dchg=%s)",
                chg,
                dchg,
            )
            return

        # AppMode must also be present – no more default writes!
        app_mode = self._hub.inverter_data.get("AppMode")
        if app_mode is None:
            _LOGGER.debug("Skip power-state handling: AppMode not ready")
            return

        # Example: if one of the modes is active, ensure AppMode
        desired_mode = 1 if (chg or dchg) else 0
        if app_mode != desired_mode:
            _LOGGER.info("Updating AppMode from %s to %s", app_mode, desired_mode)
            await self._hub._write_register(REGISTERS["app_mode"], desired_mode)

        # Further, safely execute writes based on chg/dchg here ...
        # (e.g. set limits when (dis-)charging is active)

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
