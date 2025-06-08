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


def make_pending_setter(setter_name: str, attr_suffix: str):
    """
    Factory: returns an async method that sets self._pending_<attr_suffix> = value.
    """
    async def setter(self, value: Any) -> None:
        setattr(self, f"_pending_{attr_suffix}", value)
    setter.__name__ = f"set_{setter_name}"
    return setter


class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub

    async def handle_charge_settings(self) -> None:
        """Handles the charge settings"""
        await self._handle_power_settings(
            "charge",
            self._hub._pending_charge_start,
            self._hub._pending_charge_end,
            self._hub._pending_charge_day_mask,
            self._hub._pending_charge_power_percent,
            "charge"
        )

    async def handle_discharge_settings(self) -> None:
        """Handles the discharge settings"""
        await self._handle_power_settings(
            "discharge",
            self._hub._pending_discharge_start,
            self._hub._pending_discharge_end,
            self._hub._pending_discharge_day_mask,
            self._hub._pending_discharge_power_percent,
            "discharge"
        )
        
    async def handle_discharge2_settings(self) -> None:
        """Handles the discharge settings for Discharge 2"""
        await self._handle_power_settings(
            "discharge2",
            self._hub._pending_discharge2_start,
            self._hub._pending_discharge2_end,
            self._hub._pending_discharge2_day_mask,
            self._hub._pending_discharge2_power_percent,
            "discharge2"
        )
        
    async def handle_discharge3_settings(self) -> None:
        """Handles the discharge settings for Discharge 3"""
        await self._handle_power_settings(
            "discharge3",
            self._hub._pending_discharge3_start,
            self._hub._pending_discharge3_end,
            self._hub._pending_discharge3_day_mask,
            self._hub._pending_discharge3_power_percent,
            "discharge3"
        )
        
    async def handle_discharge4_settings(self) -> None:
        """Handles the discharge settings for Discharge 4"""
        await self._handle_power_settings(
            "discharge4",
            self._hub._pending_discharge4_start,
            self._hub._pending_discharge4_end,
            self._hub._pending_discharge4_day_mask,
            self._hub._pending_discharge4_power_percent,
            "discharge4"
        )
        
    async def handle_discharge5_settings(self) -> None:
        """Handles the discharge settings for Discharge 5"""
        await self._handle_power_settings(
            "discharge5",
            self._hub._pending_discharge5_start,
            self._hub._pending_discharge5_end,
            self._hub._pending_discharge5_day_mask,
            self._hub._pending_discharge5_power_percent,
            "discharge5"
        )
        
    async def handle_discharge6_settings(self) -> None:
        """Handles the discharge settings for Discharge 6"""
        await self._handle_power_settings(
            "discharge6",
            self._hub._pending_discharge6_start,
            self._hub._pending_discharge6_end,
            self._hub._pending_discharge6_day_mask,
            self._hub._pending_discharge6_power_percent,
            "discharge6"
        )
        
    async def handle_discharge7_settings(self) -> None:
        """Handles the discharge settings for Discharge 7"""
        await self._handle_power_settings(
            "discharge7",
            self._hub._pending_discharge7_start,
            self._hub._pending_discharge7_end,
            self._hub._pending_discharge7_day_mask,
            self._hub._pending_discharge7_power_percent,
            "discharge7"
        )

    async def _handle_power_settings(
        self, 
        mode: str, 
        start_time: Optional[str], 
        end_time: Optional[str],
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str
    ) -> None:
        """
        Common method for handling charge and discharge settings
        """
        try:
            registers = REGISTERS[mode]
            
            # Set start time
            if start_time is not None:
                await self._write_time_register(
                    registers["start_time"],
                    start_time,
                    f"{label} start time",
                )

            # Set end time
            if end_time is not None:
                await self._write_time_register(
                    registers["end_time"],
                    end_time,
                    f"{label} end time",
                )

            # Set day mask and power percentage
            if day_mask is not None or power_percent is not None:
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    day_mask,
                    power_percent,
                    label
                )
        except Exception as e:
            _LOGGER.error(f"Error writing {label} settings: {e}")
        finally:
            # Reset pending values
            self._reset_pending_values(mode)

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

    def _reset_pending_values(self, mode: str) -> None:
        """Resets the pending values"""
        if mode == "charge":
            self._hub._pending_charge_start = None
            self._hub._pending_charge_end = None
            self._hub._pending_charge_day_mask = None
            self._hub._pending_charge_power_percent = None
        elif mode == "discharge":
            self._hub._pending_discharge_start = None
            self._hub._pending_discharge_end = None
            self._hub._pending_discharge_day_mask = None
            self._hub._pending_discharge_power_percent = None
        elif mode == "discharge2":
            self._hub._pending_discharge2_start = None
            self._hub._pending_discharge2_end = None
            self._hub._pending_discharge2_day_mask = None
            self._hub._pending_discharge2_power_percent = None
        elif mode == "discharge3":
            self._hub._pending_discharge3_start = None
            self._hub._pending_discharge3_end = None
            self._hub._pending_discharge3_day_mask = None
            self._hub._pending_discharge3_power_percent = None
        elif mode == "discharge4":
            self._hub._pending_discharge4_start = None
            self._hub._pending_discharge4_end = None
            self._hub._pending_discharge4_day_mask = None
            self._hub._pending_discharge4_power_percent = None
        elif mode == "discharge5":
            self._hub._pending_discharge5_start = None
            self._hub._pending_discharge5_end = None
            self._hub._pending_discharge5_day_mask = None
            self._hub._pending_discharge5_power_percent = None
        elif mode == "discharge6":
            self._hub._pending_discharge6_start = None
            self._hub._pending_discharge6_end = None
            self._hub._pending_discharge6_day_mask = None
            self._hub._pending_discharge6_power_percent = None
        elif mode == "discharge7":
            self._hub._pending_discharge7_start = None
            self._hub._pending_discharge7_end = None
            self._hub._pending_discharge7_day_mask = None
            self._hub._pending_discharge7_power_percent = None

    async def handle_export_limit(self) -> None:
        """Handles the export limit"""
        await self._handle_simple_register(
            self._hub._pending_export_limit,
            REGISTERS["export_limit"],
            "export limit",
            lambda: setattr(self._hub, "_pending_export_limit", None)
        )
                
    async def handle_app_mode(self) -> None:
        """Handles the app mode"""
        await self._handle_simple_register(
            self._hub._pending_app_mode,
            REGISTERS["app_mode"],
            "app mode",
            lambda: setattr(self._hub, "_pending_app_mode", None)
        )
        
    async def handle_discharge_time_enable(self) -> None:
        """Handles the Discharge Time Enable value"""
        await self._handle_simple_register(
            self._hub._pending_discharge_time_enable,
            REGISTERS["discharging_state"],
            "discharge time enable",
            lambda: setattr(self._hub, "_pending_discharge_time_enable", None)
        )

    async def handle_battery_on_grid_discharge_depth(self) -> None:
        """Handles the Battery On Grid Discharge Depth value"""
        await self._handle_simple_register(
            self._hub._pending_battery_on_grid_discharge_depth,
            REGISTERS["battery_on_grid_discharge_depth"],
            "battery on grid discharge depth",
            lambda: setattr(self._hub, "_pending_battery_on_grid_discharge_depth", None)
        )

    async def handle_battery_off_grid_discharge_depth(self) -> None:
        """Handles the Battery Off Grid Discharge Depth value"""
        await self._handle_simple_register(
            self._hub._pending_battery_off_grid_discharge_depth,
            REGISTERS["battery_off_grid_discharge_depth"],
            "battery off grid discharge depth",
            lambda: setattr(self._hub, "_pending_battery_off_grid_discharge_depth", None)
        )

    async def handle_battery_capacity_charge_upper_limit(self) -> None:
        """Handles the Battery Capacity Charge Upper Limit value"""
        await self._handle_simple_register(
            self._hub._pending_battery_capacity_charge_upper_limit,
            REGISTERS["battery_capacity_charge_upper_limit"],
            "battery capacity charge upper limit",
            lambda: setattr(self._hub, "_pending_battery_capacity_charge_upper_limit", None)
        )

    async def handle_battery_charge_power_limit(self) -> None:
        """Handles the Battery Charge Power Limit value"""
        await self._handle_simple_register(
            self._hub._pending_battery_charge_power_limit,
            REGISTERS["battery_charge_power_limit"],
            "battery charge power limit",
            lambda: setattr(self._hub, "_pending_battery_charge_power_limit", None)
        )

    async def handle_battery_discharge_power_limit(self) -> None:
        """Handles the Battery Discharge Power Limit value"""
        await self._handle_simple_register(
            self._hub._pending_battery_discharge_power_limit,
            REGISTERS["battery_discharge_power_limit"],
            "battery discharge power limit",
            lambda: setattr(self._hub, "_pending_battery_discharge_power_limit", None)
        )

    async def handle_grid_max_charge_power(self) -> None:
        """Handles the Grid Max Charge Power value"""
        await self._handle_simple_register(
            self._hub._pending_grid_max_charge_power,
            REGISTERS["grid_max_charge_power"],
            "grid max charge power",
            lambda: setattr(self._hub, "_pending_grid_max_charge_power", None)
        )

    async def handle_grid_max_discharge_power(self) -> None:
        """Handles the Grid Max Discharge Power value"""
        await self._handle_simple_register(
            self._hub._pending_grid_max_discharge_power,
            REGISTERS["grid_max_discharge_power"],
            "grid max discharge power",
            lambda: setattr(self._hub, "_pending_grid_max_discharge_power", None)
        )

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
                # App-Modus-Register setzen (0x3647)
                app_mode_value = 1 if state or other_state else 0
                success_app_mode = await self._hub._write_register(REGISTERS["app_mode"], app_mode_value)
                if success_app_mode:
                    _LOGGER.info(f"Successfully set {label} (0x3647) to: {app_mode_value}")
                else:
                    _LOGGER.error(f"Failed to set {label} state (0x3647)")

                # Zustandsregister setzen
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
