import logging
from typing import Optional, Any, List
from .modbus_utils import try_read_registers, try_write_registers

_LOGGER = logging.getLogger(__name__)

# --- neue Definitionen für Pending-Setter ---
PENDING_FIELDS: List[tuple[str, str]] = [
    ("charge_start", "charge_start"),
    ("charge_end", "charge_end"),
    ("charge_day_mask", "charge_day_mask"),
    ("charge_power_percent", "charge_power_percent"),
    ("discharge_start", "discharge_start"),
    ("discharge_end", "discharge_end"),
    ("discharge_day_mask", "discharge_day_mask"),
    ("discharge_power_percent", "discharge_power_percent"),
    ("export_limit", "export_limit"),
    ("charging", "charging_state"),
    ("discharging", "discharging_state"),
    ("app_mode", "app_mode"),
]


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
        try:
            if self._hub._pending_charge_start is not None:
                await self._write_time_register(
                    0x3606,
                    self._hub._pending_charge_start,
                    "charge start time",
                )

            if self._hub._pending_charge_end is not None:
                await self._write_time_register(
                    0x3607,
                    self._hub._pending_charge_end,
                    "charge end time",
                )

            if (
                self._hub._pending_charge_day_mask is not None
                or self._hub._pending_charge_power_percent is not None
            ):
                regs = await self._hub._read_registers(0x3608)
                current_value = regs[0]
                current_day_mask = (current_value >> 8) & 0xFF
                current_power_percent = current_value & 0xFF

                day_mask = (
                    self._hub._pending_charge_day_mask
                    if self._hub._pending_charge_day_mask is not None
                    else current_day_mask
                )
                power_percent = (
                    self._hub._pending_charge_power_percent
                    if self._hub._pending_charge_power_percent is not None
                    else current_power_percent
                )

                value = (day_mask << 8) | power_percent
                success = await self._hub._write_register(0x3608, value)
                if success:
                    _LOGGER.info(
                        f"Successfully set charge power time: day_mask={day_mask}, power_percent={power_percent}"
                    )
                else:
                    _LOGGER.error("Failed to write charge power time")
        except Exception as e:
            _LOGGER.error(f"Error writing charge settings: {e}")
        finally:
            self._hub._pending_charge_start = None
            self._hub._pending_charge_end = None
            self._hub._pending_charge_day_mask = None
            self._hub._pending_charge_power_percent = None

    async def handle_discharge_settings(self) -> None:
        try:
            if self._hub._pending_discharge_start is not None:
                await self._write_time_register(
                    0x361B,
                    self._hub._pending_discharge_start,
                    "discharge start time",
                )

            if self._hub._pending_discharge_end is not None:
                await self._write_time_register(
                    0x361C,
                    self._hub._pending_discharge_end,
                    "discharge end time",
                )

            if (
                self._hub._pending_discharge_day_mask is not None
                or self._hub._pending_discharge_power_percent is not None
            ):
                regs = await self._hub._read_registers(0x361D)
                current_value = regs[0]
                current_day_mask = (current_value >> 8) & 0xFF
                current_power_percent = current_value & 0xFF

                day_mask = (
                    self._hub._pending_discharge_day_mask
                    if self._hub._pending_discharge_day_mask is not None
                    else current_day_mask
                )
                power_percent = (
                    self._hub._pending_discharge_power_percent
                    if self._hub._pending_discharge_power_percent is not None
                    else current_power_percent
                )

                value = (day_mask << 8) | power_percent
                success = await self._hub._write_register(0x361D, value)
                if success:
                    _LOGGER.info(
                        f"Successfully set discharge power time: day_mask={day_mask}, power_percent={power_percent}"
                    )
                else:
                    _LOGGER.error("Failed to write discharge power time")
        except Exception as e:
            _LOGGER.error(f"Error writing discharge settings: {e}")
        finally:
            self._hub._pending_discharge_start = None
            self._hub._pending_discharge_end = None
            self._hub._pending_discharge_day_mask = None
            self._hub._pending_discharge_power_percent = None

    async def handle_export_limit(self) -> None:
        if self._hub._pending_export_limit is not None:
            try:
                success = await self._hub._write_register(
                    0x365A, self._hub._pending_export_limit
                )
                if success:
                    _LOGGER.info(
                        f"Successfully set export limit to: {self._hub._pending_export_limit}"
                    )
                else:
                    _LOGGER.error("Failed to write export limit")
            except Exception as e:
                _LOGGER.error(f"Error writing export limit: {e}")
            finally:
                self._hub._pending_export_limit = None
                
    async def handle_app_mode(self) -> None:
        if self._hub._pending_app_mode is not None:
            try:
                success = await self._hub._write_register(
                    0x3647, self._hub._pending_app_mode
                )
                if success:
                    _LOGGER.info(
                        f"Successfully set app mode to: {self._hub._pending_app_mode}"
                    )
                else:
                    _LOGGER.error("Failed to write app mode")
            except Exception as e:
                _LOGGER.error(f"Error writing app mode: {e}")
            finally:
                self._hub._pending_app_mode = None

    async def handle_pending_charging_state(self) -> None:
        if self._hub._pending_charging_state is not None:
            discharging_state = await self._hub.get_discharging_state()
            try:
                value = (
                    1
                    if self._hub._pending_charging_state or discharging_state
                    else 0
                )
                success_3647 = await self._hub._write_register(0x3647, value)
                if success_3647:
                    _LOGGER.info(f"Successfully set charging (0x3647) to: {value}")
                else:
                    _LOGGER.error("Failed to set charging state (0x3647)")

                reg_value = 1 if self._hub._pending_charging_state else 0
                success_3604 = await self._hub._write_register(0x3604, reg_value)
                if success_3604:
                    _LOGGER.info(f"Successfully set register 0x3604 to {reg_value}")
                else:
                    _LOGGER.error("Failed to set register 0x3604")
            except Exception as e:
                _LOGGER.error(f"Error handling pending charging state: {e}")
            finally:
                self._hub._pending_charging_state = None

    async def handle_pending_discharging_state(self) -> None:
        if self._hub._pending_discharging_state is not None:
            charging_state = await self._hub.get_charging_state()
            try:
                value = (
                    1
                    if self._hub._pending_discharging_state or charging_state
                    else 0
                )
                success_3647 = await self._hub._write_register(0x3647, value)
                if success_3647:
                    _LOGGER.info(f"Successfully set discharging (0x3647) to: {value}")
                else:
                    _LOGGER.error("Failed to set discharging state (0x3647)")

                reg_value = 1 if self._hub._pending_discharging_state else 0
                success_3605 = await self._hub._write_register(0x3605, reg_value)
                if success_3605:
                    _LOGGER.info(f"Successfully set register 0x3605 to {reg_value}")
                else:
                    _LOGGER.error("Failed to set register 0x3605")
            except Exception as e:
                _LOGGER.error(f"Error handling pending discharging state: {e}")
            finally:
                self._hub._pending_discharging_state = None

    async def _write_time_register(
        self, address: int, time_str: str, label: str
    ) -> None:
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
