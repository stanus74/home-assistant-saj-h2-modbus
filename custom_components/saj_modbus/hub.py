"""SAJ Modbus Hub"""
import asyncio
import logging
import random
from datetime import timedelta
from typing import List

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.register_read_message import ReadHoldingRegistersResponse

from .const import DEVICE_STATUSSES, FAULT_MESSAGES

_LOGGER = logging.getLogger(__name__)


class SAJModbusHub(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int):
        super().__init__(hass, _LOGGER, name=name, update_interval=timedelta(seconds=scan_interval))
        self._host = host
        self._port = port
        self.update_interval = timedelta(seconds=scan_interval)
        self._client = ModbusTcpClient(host=self._host, port=self._port, timeout=7)
        self._lock = asyncio.Lock()
        self.inverter_data: dict = {}
        self.data: dict = {}
        self.last_valid_data = {}

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Update connection settings and reinitialize the Modbus client."""
        self._host = host
        self._port = port
        self.update_interval = timedelta(seconds=scan_interval)

        # Close the current client, if connected
        await self.close()

        # Create a new Modbus client with the new settings
        self._client = ModbusTcpClient(host=self._host, port=self._port, timeout=7)
        _LOGGER.info(f"Updated connection settings: Host: {host}, Port: {port}, Scan Interval: {scan_interval}")

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update listener."""
        super().async_remove_listener(update_callback)
        if not self._listeners:
            asyncio.create_task(self.close())

    async def close(self) -> None:
        """Disconnect client."""
        async with self._lock:
            if self._client.is_socket_open():
                _LOGGER.info("Closing Modbus connection...")
                await self.hass.async_add_executor_job(self._client.close)
            else:
                _LOGGER.debug("Modbus socket was already closed.")

    def _connect(self) -> bool:
        """Ensure the Modbus client is connected."""
        try:
            if not self._client.connect():
                _LOGGER.error("Failed to connect to the inverter. Attempting to reconnect...")
                self._client.close()
                # Re-instantiate the client
                self._client = ModbusTcpClient(host=self._host, port=self._port, timeout=7)
                return self._client.connect()
            return True
        except Exception as e:
            _LOGGER.error(f"Unexpected error during connection attempt: {e}")
            return False

    async def _async_update_data(self) -> dict:
        """Fetch all required data sequentially without unnecessary connection closures."""
        data_tasks = [
            ("inverter_data", self.read_modbus_inverter_data),
            ("realtime_data", self.read_modbus_realtime_data),
            ("additional_data", self.read_additional_modbus_data_1),
            ("additional_data_2", self.read_additional_modbus_data_2),
            ("additional_data_3", self.read_additional_modbus_data_3),
        ]

        results = {}

        # Ensure the connection is established once
        if not await self.hass.async_add_executor_job(self._connect):
            _LOGGER.error("Failed to connect to the inverter.")
            return {}

        try:
            for key, task_function in data_tasks:
                try:
                    _LOGGER.debug(f"Fetching {key} data...")
                    results[key] = await task_function()
                    _LOGGER.debug(f"Successfully fetched {key} data.")
                except Exception as e:
                    _LOGGER.error(f"Error during {key} data fetch: {e}")
                    results[key] = self.last_valid_data.get(key, {})
        finally:
            # Close the connection after all data is fetched
            await self.close()

        # Update the inverter data
        self.inverter_data.update(results.get("inverter_data", {}))

        return {
            **self.inverter_data,
            **results.get("realtime_data", {}),
            **results.get("additional_data", {}),
            **results.get("additional_data_2", {}),
            **results.get("additional_data_3", {}),
        }

    async def try_read_registers(
        self,
        unit: int,
        address: int,
        count: int,
        max_retries: int = 5,
        base_delay: float = 2,
        max_delay: float = 30,
    ) -> List[int]:
        for attempt in range(max_retries):
            try:
                # Ensure the connection is established
                if not await self.hass.async_add_executor_job(self._connect):
                    _LOGGER.error(f"Failed to connect during attempt {attempt + 1}/{max_retries}")
                    raise ConnectionException("Failed to reconnect")

                # Check if the socket is open
                if not self._client.is_socket_open():
                    _LOGGER.warning(f"Socket is not open after attempting to connect. (Attempt {attempt + 1}/{max_retries})")
                    raise ConnectionException("Socket is still closed after connection attempt")

                async with self._lock:
                    # Read registers
                    response = await self.hass.async_add_executor_job(
                        self._client.read_holding_registers,
                        address,
                        count,
                        unit,
                    )

                # Validate response
                if response.isError() or not isinstance(response, ReadHoldingRegistersResponse):
                    raise ValueError("Modbus response error")
                if len(response.registers) < count:
                    raise ValueError(f"Incomplete response: expected {count} registers, but got {len(response.registers)}")

                # Successful return of data
                return response.registers

            except (ModbusIOException, ConnectionException, TypeError, ValueError) as e:
                _LOGGER.error(f"Error during register read (Attempt {attempt + 1}/{max_retries}): {e}")

                # Close connection on error
                await self.close()
                _LOGGER.info("Connection closed after error. Will attempt to reconnect...")

                if attempt < max_retries - 1:
                    # Wait before the next attempt
                    await asyncio.sleep(min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay))

        # Failed after max_retries
        raise ConnectionException(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")

    async def read_modbus_inverter_data(self) -> dict:
        """Read inverter data from Modbus registers and decode the values."""
        inverter_data_regs = await self.try_read_registers(1, 0x8F00, 29)

        decoder = BinaryPayloadDecoder.fromRegisters(inverter_data_regs, byteorder=Endian.BIG)

        keys = [
            "devtype",
            "subtype",
            "commver",
            "sn",
            "pc",
            "dv",
            "mcv",
            "scv",
            "disphwversion",
            "ctrlhwversion",
            "powerhwversion",
        ]
        data = {}

        for key in keys[:3]:
            value = decoder.decode_16bit_uint()
            data[key] = round(value * 0.001, 3) if key == "commver" else value

        for key in keys[3:5]:
            data[key] = decoder.decode_string(20).decode("ascii").strip()

        for key in keys[5:]:
            data[key] = round(decoder.decode_16bit_uint() * 0.001, 3)

        return data

    async def read_additional_modbus_data_1(self) -> dict:
        """Read additional Modbus data set 1."""
        decode_instructions = [
            ("BatTemp", "decode_16bit_int", 0.1),
            ("batEnergyPercent", "decode_16bit_int", 0.01),
            ("skip", "skip_bytes", 2),
            ("pv1Voltage", "decode_16bit_int", 0.1),
            ("pv1TotalCurrent", "decode_16bit_int", 0.01),
            ("pv1Power", "decode_16bit_int", 1),
            ("pv2Voltage", "decode_16bit_int", 0.1),
            ("pv2TotalCurrent", "decode_16bit_int", 0.01),
            ("pv2Power", "decode_16bit_int", 1),
            ("pv3Voltage", "decode_16bit_int", 0.1),
            ("pv3TotalCurrent", "decode_16bit_int", 0.01),
            ("pv3Power", "decode_16bit_int", 1),
            ("pv4Voltage", "decode_16bit_int", 0.1),
            ("pv4TotalCurrent", "decode_16bit_int", 0.01),
            ("pv4Power", "decode_16bit_int", 1),
            ("skip", "skip_bytes", 48),
            ("directionPV", "decode_16bit_int", 1),
            ("directionBattery", "decode_16bit_int", 1),
            ("directionGrid", "decode_16bit_int", 1),
            ("directionOutput", "decode_16bit_int", 1),
            ("skip", "skip_bytes", 14),
            ("TotalLoadPower", "decode_16bit_int", 1),
            ("skip", "skip_bytes", 8),
            ("pvPower", "decode_16bit_int", 1),
            ("batteryPower", "decode_16bit_int", 1),
            ("totalgridPower", "decode_16bit_int", 1),
            ("skip", "skip_bytes", 2),
            ("inverterPower", "decode_16bit_int", 1),
            ("skip", "skip_bytes", 6),
            ("gridPower", "decode_16bit_int", 1),
        ]
        data = await self._read_modbus_data(16494, 64, decode_instructions)
        self.last_valid_data['additional_data'] = data
        return data

    async def read_additional_modbus_data_2(self) -> dict:
        """Read additional Modbus data set 2."""
        data_keys = [
            "todayenergy", "monthenergy", "yearenergy", "totalenergy",
            "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
            "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
            "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
            "total_today_load", "total_month_load", "total_year_load", "total_total_load",
            "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
            "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
            "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
        ]
        decode_instructions = [(key, "decode_32bit_uint", 0.01) for key in data_keys]
        data = await self._read_modbus_data(16575, 64, decode_instructions)
        self.last_valid_data['additional_data_2'] = data
        return data

    async def read_additional_modbus_data_3(self) -> dict:
        """Read additional Modbus data set 3."""
        data_keys = [
            "sell_today_energy_2", "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
            "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3", "sell_total_energy_3",
            "feedin_today_energy_2", "feedin_month_energy_2", "feedin_year_energy_2", "feedin_total_energy_2",
            "feedin_today_energy_3", "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
            "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year", "sum_feed_in_total",
            "sum_sell_today", "sum_sell_month", "sum_sell_year", "sum_sell_total",
        ]
        decode_instructions = [(key, "decode_32bit_uint", 0.01) for key in data_keys]
        data = await self._read_modbus_data(16711, 48, decode_instructions)
        self.last_valid_data['additional_data_3'] = data
        return data

    async def read_modbus_realtime_data(self) -> dict:
        """Read real-time data from Modbus registers."""
        realtime_data_regs = await self.try_read_registers(1, 16388, 19)

        decoder = BinaryPayloadDecoder.fromRegisters(realtime_data_regs, byteorder=Endian.BIG)

        decode_instructions = [
            ("mpvmode", "decode_16bit_uint", 1, False),
            ("faultMsg0", "decode_32bit_uint", 1, False),
            ("faultMsg1", "decode_32bit_uint", 1, False),
            ("faultMsg2", "decode_32bit_uint", 1, False),
            ("skip", "skip_bytes", 8, False),
            ("errorcount", "decode_16bit_uint", 1, False),
            ("SinkTemp", "decode_16bit_int", 0.1, True),
            ("AmbTemp", "decode_16bit_int", 0.1, True),
            ("gfci", "decode_16bit_int", 1, False),
            ("iso1", "decode_16bit_uint", 1, False),
            ("iso2", "decode_16bit_uint", 1, False),
            ("iso3", "decode_16bit_uint", 1, False),
            ("iso4", "decode_16bit_uint", 1, False),
        ]
        data = {}
        fault_messages = []
        for key, method, factor, is_temp in decode_instructions:
            if key == "skip":
                decoder.skip_bytes(factor)
            else:
                decoded_value = getattr(decoder, method)()
                if is_temp:
                    data[key] = round(decoded_value * factor, 1)
                else:
                    data[key] = round(decoded_value * factor, 2) if factor != 1 else decoded_value

                if key in ["faultMsg0", "faultMsg1", "faultMsg2"]:
                    fault_messages.extend(
                        self.translate_fault_code_to_messages(decoded_value, FAULT_MESSAGES[int(key[-1])])
                    )

        mpvmode = data["mpvmode"]
        data["mpvstatus"] = DEVICE_STATUSSES.get(mpvmode, "Unknown")
        data["faultmsg"] = ", ".join(fault_messages).strip()[0:254]
        if fault_messages:
            _LOGGER.error("Fault message: " + data["faultmsg"])

        self.last_valid_data['realtime_data'] = data
        return data

    async def _read_modbus_data(self, start_address: int, count: int, decode_instructions: list) -> dict:
        """Read Modbus data and decode based on instructions."""
        regs = await self.try_read_registers(1, start_address, count)

        data = {}
        decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)

        for instruction in decode_instructions:
            if instruction[0] == "skip":
                decoder.skip_bytes(instruction[2])
            else:
                decoded_value = getattr(decoder, instruction[1])()
                if isinstance(decoded_value, bytes):
                    data[instruction[0]] = decoded_value.decode("ascii").strip()
                else:
                    data[instruction[0]] = round(decoded_value * instruction[2], 2) if instruction[2] != 1 else decoded_value
        return data

    def translate_fault_code_to_messages(self, fault_code: int, fault_messages: dict) -> list:
        """Translate fault code to readable messages."""
        messages = []
        if not fault_code:
            return messages

        for code, mesg in fault_messages.items():
            if fault_code & code:
                messages.append(mesg)

        return messages
