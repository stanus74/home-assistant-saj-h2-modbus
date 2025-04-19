import logging
from typing import Optional, List
from .modbus_utils import try_read_registers, try_write_registers

_LOGGER = logging.getLogger(__name__)

class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub
        self._client = hub._client
        self._read_lock = hub._read_lock
        self._host = hub._host
        self._port = hub._port

    async def _read_registers(self, address: int, count: int = 1) -> List[int]:
        return await try_read_registers(
            self._client,
            self._read_lock,
            1,
            address,
            count,
            host=self._host,
            port=self._port
        )

    async def _write_register(self, address: int, value: int) -> bool:
        return await try_write_registers(
            self._client,
            self._read_lock,
            1,
            address,
            value,
            host=self._host,
            port=self._port
        )

    async def handle_charge_settings(self) -> None:
        try:
            if self._hub._pending_charge_start is not None:
                await self._write_time_register(
                    0x3606, self._hub._pending_charge_start, "charge start time"
                )

            if self._hub._pending_charge_end is not None:
                await self._write_time_register(
                    0x3607, self._hub._pending_charge_end, "charge end time"
                )

            if (self._hub._pending_charge_day_mask is not None or
                self._hub._pending_charge_power_percent is not None):
                regs = await self._read_registers(0x3608)
                current_value = regs[0]
                current_day_mask = (current_value >> 8) & 0xFF
                current_power_percent = current_value & 0xFF

                day_mask = self._hub._pending_charge_day_mask if self._hub._pending_charge_day_mask is not None else current_day_mask
                power_percent = self._hub._pending_charge_power_percent if self._hub._pending_charge_power_percent is not None else current_power_percent

                value = (day_mask << 8) | power_percent
                success = await self._write_register(0x3608, value)
                if success:
                    _LOGGER.info(f"Successfully set charge power time: day_mask={day_mask}, power_percent={power_percent}")
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
                    0x361B, self._hub._pending_discharge_start, "discharge start time"
                )

            if self._hub._pending_discharge_end is not None:
                await self._write_time_register(
                    0x361C, self._hub._pending_discharge_end, "discharge end time"
                )

            if (self._hub._pending_discharge_day_mask is not None or
                self._hub._pending_discharge_power_percent is not None):
                regs = await self._read_registers(0x361D)
                current_value = regs[0]
                current_day_mask = (current_value >> 8) & 0xFF
                current_power_percent = current_value & 0xFF

                day_mask = self._hub._pending_discharge_day_mask if self._hub._pending_discharge_day_mask is not None else current_day_mask
                power_percent = self._hub._pending_discharge_power_percent if self._hub._pending_discharge_power_percent is not None else current_power_percent

                value = (day_mask << 8) | power_percent
                success = await self._write_register(0x361D, value)
                if success:
                    _LOGGER.info(f"Successfully set discharge power time: day_mask={day_mask}, power_percent={power_percent}")
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
                success = await self._write_register(0x365A, self._hub._pending_export_limit)
                if success:
                    _LOGGER.info(f"Successfully set export limit to: {self._hub._pending_export_limit}")
                else:
                    _LOGGER.error("Failed to write export limit")
            except Exception as e:
                _LOGGER.error(f"Error writing export limit: {e}")
            finally:
                self._hub._pending_export_limit = None

    async def handle_pending_charging_state(self) -> None:
        if self._hub._pending_charging_state is not None:
            discharging_state = await self._hub.get_discharging_state()
            try:
                value = 1 if self._hub._pending_charging_state or discharging_state else 0
                success_3647 = await self._write_register(0x3647, value)
                if success_3647:
                    _LOGGER.info(f"Successfully set charging (0x3647) to: {value}")
                else:
                    _LOGGER.error("Failed to set charging state (0x3647)")

                reg_value = 1 if self._hub._pending_charging_state else 0
                success_3604 = await self._write_register(0x3604, reg_value)
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
                value = 1 if self._hub._pending_discharging_state or charging_state else 0
                success_3647 = await self._write_register(0x3647, value)
                if success_3647:
                    _LOGGER.info(f"Successfully set discharging (0x3647) to: {value}")
                else:
                    _LOGGER.error("Failed to set discharging state (0x3647)")

                reg_value = 1 if self._hub._pending_discharging_state else 0
                success_3605 = await self._write_register(0x3605, reg_value)
                if success_3605:
                    _LOGGER.info(f"Successfully set register 0x3605 to {reg_value}")
                else:
                    _LOGGER.error("Failed to set register 0x3605")
            except Exception as e:
                _LOGGER.error(f"Error handling pending discharging state: {e}")
            finally:
                self._hub._pending_discharging_state = None

    async def _write_time_register(self, address: int, time_str: str, label: str) -> None:
        time_parts = time_str.split(":")
        if len(time_parts) == 2:
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            value = (hours << 8) | minutes
            success = await self._write_register(address, value)
            if success:
                _LOGGER.info(f"Successfully set {label}: {time_str}")
            else:
                _LOGGER.error(f"Failed to write {label}")
        else:
            _LOGGER.error(f"Invalid time format for {label}: {time_str}")
