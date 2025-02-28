import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient
#from pymodbus.exceptions import ConnectionException, ModbusIOException

from .modbus_utils import safe_close, close, ensure_connection, try_read_registers
from .modbus_data_readers import (
    read_modbus_inverter_data,
    read_modbus_realtime_data,
    read_additional_modbus_data_1_part_1,
    read_additional_modbus_data_1_part_2,
    read_additional_modbus_data_2_part_1,
    read_additional_modbus_data_2_part_2,
    read_additional_modbus_data_3,
    read_additional_modbus_data_4,
    read_battery_data,
    read_first_charge_data,
)
#from .const import DEVICE_STATUSSES, FAULT_MESSAGES

_LOGGER = logging.getLogger(__name__)

class SAJModbusHub(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
            update_method=self._async_update_data,
        )
        self._host = host
        self._port = port
        self._client: Optional[AsyncModbusTcpClient] = None
        self._read_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()
        self.updating_settings = False
        self.inverter_data: Dict[str, Any] = {}
        self._closing = False
        #self._reconnecting = False
        #self._max_retries = 2
        #self._retry_delay = 1
        self._operation_timeout = 30
        
        # Initialize the pending charging state:
        self._pending_charging_state: Optional[bool] = None
        
        # New pending variables for First Charge:
        self._pending_first_charge_start: Optional[str] = None  # Expected in format "HH:MM"
        self._pending_first_charge_end: Optional[str] = None    # Expected in format "HH:MM"
        self._pending_first_charge_day_mask: Optional[int] = None
        self._pending_first_charge_power_percent: Optional[int] = None

    def _create_client(self) -> AsyncModbusTcpClient:
        """Creates a new optimized instance of the AsyncModbusTcpClient."""
        client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=10,
            
        )
        _LOGGER.debug(f"Created new Modbus client: AsyncModbusTcpClient {self._host}:{self._port}")
        return client

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Updates the connection settings with improved synchronization."""
        async with self._connection_lock:
            self.updating_settings = True
            try:
                connection_changed = (host != self._host) or (port != self._port)
                self._host = host
                self._port = port
                self.update_interval = timedelta(seconds=scan_interval)

                if connection_changed:
                    await safe_close(self._client)
                    self._client = self._create_client()
                    self._client = await ensure_connection(self._client, self._host, self._port)
            finally:
                self.updating_settings = False


    async def _async_update_data(self) -> Dict[str, Any]:
        self._client = await ensure_connection(self._client, self._host, self._port)
        if not self.inverter_data:
            self.inverter_data.update(await read_modbus_inverter_data(self._client, self._read_lock))
        combined_data = {**self.inverter_data}

        # Loop through all methods that provide dictionary data
        for method in [
            read_modbus_realtime_data,
            read_additional_modbus_data_1_part_1,
            read_additional_modbus_data_1_part_2,
            read_additional_modbus_data_2_part_1,
            read_additional_modbus_data_2_part_2,
            read_additional_modbus_data_3,
            read_additional_modbus_data_4,
            read_battery_data,
            read_first_charge_data,
        ]:
            result = await method(self._client, self._read_lock)
            combined_data.update(result)
            await asyncio.sleep(0.2)
        
        # Separate call to query the current charging state
        charging_state = await self.get_charging_state()
        combined_data["charging_enabled"] = charging_state

        # Handle pending charging state
        if self._pending_charging_state is not None:
            if self._pending_charging_state != charging_state:
                await self._handle_pending_charging_state()
                charging_state = await self.get_charging_state()
                combined_data["charging_enabled"] = charging_state
            else:
                _LOGGER.info("Charging state unchanged, no write required.")
                self._pending_charging_state = None

        # Handle pending first charge settings
        if (self._pending_first_charge_start is not None or
            self._pending_first_charge_end is not None or
            self._pending_first_charge_day_mask is not None or
            self._pending_first_charge_power_percent is not None):
            _LOGGER.info(
                "Writing First Charge values: start=%s, end=%s, day_mask=%s, power_percent=%s",
                self._pending_first_charge_start,
                self._pending_first_charge_end,
                self._pending_first_charge_day_mask,
                self._pending_first_charge_power_percent
            )
            await self._handle_pending_first_charge_settings()

        await close(self._client, self._closing, self._connection_lock)
        return combined_data

    async def _handle_pending_first_charge_settings(self) -> None:
        """Writes the pending First-Charge values to registers 0x3606, 0x3607, and 0x3608."""
        async with self._read_lock:
            # Register 0x3606: Start Time (High Byte = Hour, Low Byte = Minute)
            if self._pending_first_charge_start is not None:
                try:
                    hour, minute = map(int, self._pending_first_charge_start.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x3606, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set first charge start time: {self._pending_first_charge_start}")
                    else:
                        _LOGGER.error(f"Failed to write first charge start time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing first charge start time: {e}")
                finally:
                    self._pending_first_charge_start = None

            # Register 0x3607: End Time (High Byte = Hour, Low Byte = Minute)
            if self._pending_first_charge_end is not None:
                try:
                    hour, minute = map(int, self._pending_first_charge_end.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x3607, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set first charge end time: {self._pending_first_charge_end}")
                    else:
                        _LOGGER.error(f"Failed to write first charge end time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing first charge end time: {e}")
                finally:
                    self._pending_first_charge_end = None

            # Register 0x3608: Power Time (High Byte = Day Mask, Low Byte = Power Percent)
            if self._pending_first_charge_day_mask is not None or self._pending_first_charge_power_percent is not None:
                try:
                    # First read the current register value for 0x3608
                    response = await self._client.read_holding_registers(address=0x3608, count=1)
                    if not response or response.isError() or len(response.registers) < 1:
                        current_value = 0
                    else:
                        current_value = response.registers[0]
                    current_day_mask = (current_value >> 8) & 0xFF
                    current_power_percent = current_value & 0xFF

                    # Supplement missing parts with the pending values (if available)
                    day_mask = self._pending_first_charge_day_mask if self._pending_first_charge_day_mask is not None else current_day_mask
                    power_percent = self._pending_first_charge_power_percent if self._pending_first_charge_power_percent is not None else current_power_percent

                    value = (day_mask << 8) | power_percent
                    response = await self._client.write_register(0x3608, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set first charge power time: day_mask={day_mask}, power_percent={power_percent}")
                    else:
                        _LOGGER.error(f"Failed to write first charge power time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing first charge power time: {e}")
                finally:
                    self._pending_first_charge_day_mask = None
                    self._pending_first_charge_power_percent = None

    # Setter methods called by HA when sensors change:
    async def set_first_charge_start(self, time_str: str) -> None:
        """Sets the new start time (format 'HH:MM') for First Charge."""
        self._pending_first_charge_start = time_str

    async def set_first_charge_end(self, time_str: str) -> None:
        """Sets the new end time (format 'HH:MM') for First Charge."""
        self._pending_first_charge_end = time_str

    async def set_first_charge_day_mask(self, day_mask: int) -> None:
        """Sets the new Day Mask value for First Charge."""
        self._pending_first_charge_day_mask = day_mask

    async def set_first_charge_power_percent(self, power_percent: int) -> None:
        """Sets the new Power Percent value for First Charge."""
        self._pending_first_charge_power_percent = power_percent

    async def _handle_pending_charging_state(self) -> dict:
        """Writes the pending charging state to register 0x3647 and returns an empty dictionary."""
        if self._pending_charging_state is not None:
            value = 1 if self._pending_charging_state else 0
            async with self._read_lock:
                response = await self._client.write_register(0x3647, value)
                if response and not response.isError():
                    _LOGGER.info(f"Successfully set charging to: {self._pending_charging_state}")
                else:
                    _LOGGER.error(f"Failed to set charging state: {response}")
            # After the write operation, the pending state is reset.
            self._pending_charging_state = None
        return {}


    async def get_charging_state(self) -> bool:
        """Get the current charging control state."""
        try:
            regs = await try_read_registers(self._client, self._read_lock, 1, 0x3647, 1)
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading charging state: {e}")
            return False


    async def set_charging(self, enable: bool) -> None:
        """Set the charging control state by scheduling it for the next update cycle."""
        self._pending_charging_state = enable
        # The call to async_request_refresh() was removed so that the write operation
        # occurs exclusively in the regular update cycle.


