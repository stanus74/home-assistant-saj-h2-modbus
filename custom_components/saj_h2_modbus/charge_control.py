import logging
from typing import Optional, Any, List, Dict, Tuple, Callable, Awaitable
from .modbus_utils import try_read_registers, try_write_registers

_LOGGER = logging.getLogger(__name__)

# --- Definitions for Pending Setter ---
PENDING_FIELDS: List[tuple[str, str]] = [
    ("charge_start", "charge_start"),
    ("charge_end", "charge_end"),
    ("charge_day_mask", "charge_day_mask"),
    ("charge_power_percent", "charge_power_percent"),
    ("discharge_start", "discharge_start"),
    ("discharge_end", "discharge_end"),
    ("discharge_day_mask", "discharge_day_mask"),
    ("discharge_power_percent", "discharge_power_percent"),
    ("discharge2_start", "discharge2_start"),
    ("discharge2_end", "discharge2_end"),
    ("discharge2_day_mask", "discharge2_day_mask"),
    ("discharge2_power_percent", "discharge2_power_percent"),
    ("discharge3_start", "discharge3_start"),
    ("discharge3_end", "discharge3_end"),
    ("discharge3_day_mask", "discharge3_day_mask"),
    ("discharge3_power_percent", "discharge3_power_percent"),
    ("discharge4_start", "discharge4_start"),
    ("discharge4_end", "discharge4_end"),
    ("discharge4_day_mask", "discharge4_day_mask"),
    ("discharge4_power_percent", "discharge4_power_percent"),
    ("discharge5_start", "discharge5_start"),
    ("discharge5_end", "discharge5_end"),
    ("discharge5_day_mask", "discharge5_day_mask"),
    ("discharge5_power_percent", "discharge5_power_percent"),
    ("discharge6_start", "discharge6_start"),
    ("discharge6_end", "discharge6_end"),
    ("discharge6_day_mask", "discharge6_day_mask"),
    ("discharge6_power_percent", "discharge6_power_percent"),
    ("discharge7_start", "discharge7_start"),
    ("discharge7_end", "discharge7_end"),
    ("discharge7_day_mask", "discharge7_day_mask"),
    ("discharge7_power_percent", "discharge7_power_percent"),
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
    "discharge": {
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


class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub

    async def handle_power_settings(self, mode: str) -> None:
        """Handles the power settings for a given mode (charge or discharge)."""
        pending_settings = self._hub.get_pending_settings(mode)
        if not pending_settings:
            return

        await self._handle_power_settings_internal(mode, pending_settings)

    async def _handle_power_settings_internal(self, mode: str, settings: Dict[str, Any]) -> None:
        """Internal handler for power settings."""
        try:
            registers = REGISTERS[mode]
            
            # Set start time
            if "start" in settings:
                await self._write_time_register(
                    registers["start_time"],
                    settings["start"],
                    f"{mode} start time",
                )

            # Set end time
            if "end" in settings:
                await self._write_time_register(
                    registers["end_time"],
                    settings["end"],
                    f"{mode} end time",
                )

            # Set day mask and power percentage
            if "day_mask" in settings or "power_percent" in settings:
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    settings.get("day_mask"),
                    settings.get("power_percent"),
                    mode,
                )
        except Exception as e:
            _LOGGER.error(f"Error writing {mode} settings: {e}")
        finally:
            # Reset pending values
            self._hub.reset_pending_settings(mode)

    async def _update_day_mask_and_power(
        self, 
        address: int, 
        day_mask: Optional[int], 
        power_percent: Optional[int],
        label: str
    ) -> None:
        """Updates the day mask and power percentage"""
        regs = await self._hub._read_registers(address)
        current_value = regs[0]
        current_day_mask = (current_value >> 8) & 0xFF
        current_power_percent = current_value & 0xFF

        new_day_mask = day_mask if day_mask is not None else current_day_mask
        new_power_percent = power_percent if power_percent is not None else current_power_percent

        value = (new_day_mask << 8) | new_power_percent
        success = await self._hub._write_register(address, value)
        
        if success:
            _LOGGER.info(
                f"Successfully set {label} power time: day_mask={new_day_mask}, power_percent={new_power_percent}"
            )
        else:
            _LOGGER.error(f"Failed to write {label} power time")

    async def handle_simple_register(self, setting_key: str) -> None:
        """Handles a simple register setting."""
        value = self._hub.get_pending_setting(setting_key)
        if value is not None:
            await self._handle_simple_register_internal(
                value,
                REGISTERS[setting_key],
                setting_key.replace("_", " "),
                lambda: self._hub.reset_pending_setting(setting_key),
            )

    async def _handle_simple_register_internal(
        self,
        value: Any,
        address: int,
        label: str,
        reset_callback: Callable[[], None],
    ) -> None:
        """Internal handler for simple register write operations."""
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

    async def handle_power_state_settings(self) -> None:
        """Handles the power state settings for charging and discharging."""
        pending_charging = self._hub.get_pending_setting("charging_state")
        pending_discharging = self._hub.get_pending_setting("discharging_state")

        if pending_charging is not None:
            await self._handle_power_state(
                pending_charging,
                self._hub.get_discharging_state,
                REGISTERS["charging_state"],
                "charging",
                lambda: self._hub.reset_pending_setting("charging_state"),
            )
        
        if pending_discharging is not None:
            await self._handle_power_state(
                pending_discharging,
                self._hub.get_charging_state,
                REGISTERS["discharging_state"],
                "discharging",
                lambda: self._hub.reset_pending_setting("discharging_state"),
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

    async def handle_discharge_time_enable(self) -> None:
        """Handles the discharge time enable setting."""
        value = self._hub.get_pending_setting("discharge_time_enable")
        if value is not None:
            await self._handle_simple_register_internal(
                value,
                REGISTERS["discharge_time_enable"],
                "discharge time enable",
                lambda: self._hub.reset_pending_setting("discharge_time_enable"),
            )

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
