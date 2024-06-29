"""SAJ Modbus Hub"""
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.payload import BinaryPayloadDecoder
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from voluptuous.validators import Number
from homeassistant.core import HomeAssistant, CALLBACK_TYPE, callback
from datetime import timedelta
from typing import Tuple, List, Optional
import logging
import asyncio
import random
from .const import DEVICE_STATUSSES, FAULT_MESSAGES

_LOGGER = logging.getLogger(__name__)

class SAJModbusHub(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: Number, scan_interval: Number):
        super().__init__(hass, _LOGGER, name=name, update_interval=timedelta(seconds=scan_interval))
        self._client = ModbusTcpClient(host=host, port=port, timeout=7)
        self._lock = asyncio.Lock()
        self.inverter_data: dict = {}
        self.data: dict = {}
        self.last_valid_data = {}

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update listener."""
        super().async_remove_listener(update_callback)
        if not self._listeners:
            asyncio.create_task(self.close())

    async def close(self) -> None:
        """Disconnect client."""
        async with self._lock:
            await self.hass.async_add_executor_job(self._client.close)

   
    def _connect(self) -> bool:
        """Ensure the Modbus client is connected."""
        try:
            if not self._client.connect():
                _LOGGER.error("Failed to connect to the inverter. Attempting to reconnect...")
                self._client.close()
                return self._client.connect()
            return True
        except Exception as e:
            _LOGGER.error(f"Unexpected error during connection attempt: {e}")
            return False

    async def _async_update_data(self) -> dict:
        """Fetch all required data sequentially with pauses."""
        data_tasks = [
            ("inverter_data", self.read_modbus_inverter_data),
            ("realtime_data", self.read_modbus_realtime_data),
            ("additional_data", self.read_additional_modbus_data_1),
            ("additional_data_2", self.read_additional_modbus_data_2),
            ("additional_data_3", self.read_additional_modbus_data_3)
        ]

        results = {}

        for key, task_function in data_tasks:
            try:
                results[key] = await task_function()
            except ConnectionException as e:
                _LOGGER.error(f"Connection error during {key} data fetch: {e}")
                if key == "realtime_data":
                    results[key] = {"mpvmode": 0, "mpvstatus": DEVICE_STATUSSES[0], "power": 0}
                else:
                    results[key] = {}
            except Exception as e:
                _LOGGER.error(f"Unexpected error during {key} data fetch: {e}")
                results[key] = {}

            finally:
                # Ensure the connection is closed even in case of errors
                await self.close()

            # Wait 2 seconds before the next query
            await asyncio.sleep(2)

        # Update the inverter data
        self.inverter_data.update(results.get("inverter_data", {}))

        return {**self.inverter_data, **results.get("realtime_data", {}), **results.get("additional_data", {}),
                **results.get("additional_data_2", {}), **results.get("additional_data_3", {})}


    async def try_read_registers(self, unit: int, address: int, count: int, max_retries: int = 5, base_delay: float = 0.5, max_delay: float = 30) -> Tuple[Optional[List[int]], bool]:
        for attempt in range(max_retries):
            try:
                if not self._client.is_socket_open():
                    if not await self.hass.async_add_executor_job(self._connect):
                        raise ConnectionException("Failed to reconnect")
    
                async with self._lock:
                    response = await self.hass.async_add_executor_job(
                        self._client.read_holding_registers,
                        address,
                        count,
                        unit
                    )
    
                if response.isError() or not isinstance(response, ReadHoldingRegistersResponse) or len(response.registers) < count:
                    raise ValueError(f"Incomplete or unexpected response")
                
                return response.registers, True
    
            except (ModbusIOException, ConnectionException, TypeError, ValueError) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay))
    
        _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
        return None, False





    async def read_modbus_inverter_data(self) -> dict:
        inverter_data_regs, inverter_data_success = await self.try_read_registers(1, 0x8F00, 29)
        if not inverter_data_success:
            return {}

       

        decoder = BinaryPayloadDecoder.fromRegisters(inverter_data_regs, byteorder=Endian.BIG)

        keys = ["devtype", "subtype", "commver", "sn", "pc", "dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]
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
            ("gridPower", "decode_16bit_int", 1)
        ]
        return await self._read_modbus_data(16494, 64, decode_instructions)

    async def read_additional_modbus_data_2(self) -> dict:
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
        return await self._read_modbus_data(16575, 64, [(key, "decode_32bit_uint", 0.01) for key in data_keys])

    async def read_additional_modbus_data_3(self) -> dict:
        data_keys = [
            "sell_today_energy_2", "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
            "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3", "sell_total_energy_3",
            "feedin_today_energy_2", "feedin_month_energy_2", "feedin_year_energy_2", "feedin_total_energy_2",
            "feedin_today_energy_3", "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
            "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year", "sum_feed_in_total",
            "sum_sell_today", "sum_sell_month", "sum_sell_year", "sum_sell_total"
        ]
        return await self._read_modbus_data(16711, 48, [(key, "decode_32bit_uint", 0.01) for key in data_keys])

    async def read_modbus_realtime_data(self) -> dict:
        realtime_data_regs, realtime_data_success = await self.try_read_registers(1, 16388, 19)
        if not realtime_data_success:
            return self.last_valid_data.get('realtime_data', {})

        data = {}
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
        faultMsg = []
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
                    faultMsg.extend(
                        self.translate_fault_code_to_messages(decoded_value, FAULT_MESSAGES[int(key[-1])].items())
                    )

        mpvmode = data["mpvmode"]
        data["mpvstatus"] = DEVICE_STATUSSES.get(mpvmode, "Unknown")
        data["faultmsg"] = ", ".join(faultMsg).strip()[0:254]
        if faultMsg:
            _LOGGER.error("Fault message: " + ", ".join(faultMsg).strip())
        return data

    async def _read_modbus_data(self, start_address: int, count: int, decode_instructions: list) -> dict:
        regs, success = await self.try_read_registers(1, start_address, count)
        if not success:
            return self.last_valid_data.get('realtime_data', {})

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

        self.last_valid_data['realtime_data'] = data
        return data

    def log_error(self, message: str):
        _LOGGER.error(message)

    def translate_fault_code_to_messages(self, fault_code: int, fault_messages: list) -> list:
        messages = []
        if not fault_code:
            return messages

        for code, mesg in fault_messages:
            if fault_code & code:
                messages.append(mesg)

        return messages
