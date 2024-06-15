"""SAJ Modbus Hub"""
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from voluptuous.validators import Number
from homeassistant.core import HomeAssistant  

import logging
import threading
import asyncio
import time

from datetime import timedelta
from homeassistant.core import CALLBACK_TYPE, callback
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.payload import BinaryPayloadDecoder

from .const import (
    DEVICE_STATUSSES,
    FAULT_MESSAGES,
)

_LOGGER = logging.getLogger(__name__)


class SAJModbusHub(DataUpdateCoordinator[dict]):
    """Thread-safe wrapper class for pymodbus."""

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: Number, scan_interval: Number):
        """Initialize the Modbus hub."""
        super().__init__(hass, _LOGGER, name=name, update_interval=timedelta(seconds=scan_interval))
        self._client = ModbusTcpClient(host=host, port=port, timeout=7)
        self._lock = threading.Lock()
        self.inverter_data: dict = {}
        self.data: dict = {}
        self.last_valid_data = {}

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update listener."""
        super().async_remove_listener(update_callback)
        if not self._listeners:
            self.close()

    def close(self) -> None:
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def _read_holding_registers(self, unit, address, count) -> ReadHoldingRegistersResponse:
        """Read holding registers with retry logic."""
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            self._client = ModbusTcpClient(host=self._client.host, port=self._client.port, timeout=7)
            self._client.connect()
        with self._lock:
            return self._client.read_holding_registers(address=address, count=count, slave=unit)

    async def _async_update_data(self) -> dict:
	    """Fetch all required data with pauses and better connection handling."""
	    data_tasks = [
	        ("inverter_data", self.read_modbus_inverter_data, 2),
	        ("realtime_data", self.read_modbus_realtime_data, 2),
	        ("additional_data", self.read_additional_modbus_data, 2),
	        ("additional_data_2", self.read_additional_modbus_data_2, 2),
	        ("additional_data_3", self.read_additional_modbus_data_3, 2)
	    ]
	    
	    results = {}

	    def execute_modbus_task(task_function):
	        """Wrapper function to execute Modbus tasks with logging and connection checks."""
	        if not self._client.connect():
	            _LOGGER.error("Failed to connect to the inverter.")
	            raise ConnectionException("Failed to connect to the inverter.")
	        return task_function()

	    try:
	        for key, task_function, sleep_time in data_tasks:
	            if key not in self.inverter_data or key == "realtime_data":
	                results[key] = await self.hass.async_add_executor_job(lambda: execute_modbus_task(task_function))
	                await asyncio.sleep(sleep_time)
	                
	        self.inverter_data.update(results.get("inverter_data", {}))

	    except ConnectionException as e:
	        _LOGGER.error("Reading realtime data failed! Inverter is unreachable. Error: %s", e)
	        results["realtime_data"] = {"mpvmode": 0, "mpvstatus": DEVICE_STATUSSES[0], "power": 0}

	    finally:
	        self.close()

	    return {**self.inverter_data, **results.get("realtime_data", {}), **results.get("additional_data", {}), 
	            **results.get("additional_data_2", {}), **results.get("additional_data_3", {})}


    def try_read_registers(self, unit, address, count):
            """General function to read Modbus registers."""
            try:
              response = self._read_holding_registers(unit=unit, address=address, count=count)
              if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) < count:
                self.log_error(f"Error when reading the Modbus data from unit {unit} and address {address}")
                return None, False
              return response.registers, True
            except ModbusIOException as e:
             self.log_error(f"Modbus IO Exception when reading the data: {e}")
             return None, False



    def read_modbus_inverter_data(self) -> dict:
        inverter_data_regs, inverter_data_success = self.try_read_registers(1, 0x8F00, 29)
        if not inverter_data_success:
            return {}

        if len(inverter_data_regs) < 29:
            _LOGGER.error(f"Incomplete data when reading the inverter data: Expected 29, received {len(inverter_data_regs)}")
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

    def read_modbus_realtime_data(self) -> dict:
        realtime_data_regs, realtime_data_success = self.try_read_registers(1, 16388, 19)
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
        # status value can hold max 255 chars in HA
        data["faultmsg"] = ", ".join(faultMsg).strip()[0:254]
        if faultMsg:
            _LOGGER.error("Fault message: " + ", ".join(faultMsg).strip())
        return data    
   

    def read_additional_modbus_data(self) -> dict:
        additional_data_regs, additional_data_success = self.try_read_registers(1, 16494, 64)
        if not additional_data_success:
            return self.last_valid_data.get('additional_data', {})

        decoder = BinaryPayloadDecoder.fromRegisters(additional_data_regs, byteorder=Endian.BIG)
        data = {}

        
        decode_instructions = [
        ("BatTemp", 0.1), ("batEnergyPercent", 0.01), ("skip", 2),
        ("pv1Voltage", 0.1), ("pv1TotalCurrent", 0.01), ("pv1Power", 1),
        ("pv2Voltage", 0.1), ("pv2TotalCurrent", 0.01), ("pv2Power", 1),
        ("pv3Voltage", 0.1), ("pv3TotalCurrent", 0.01), ("pv3Power", 1),
        ("pv4Voltage", 0.1), ("pv4TotalCurrent", 0.01), ("pv4Power", 1),
        ("skip", 48), ("directionPV", 1), ("directionBattery", 1),
        ("directionGrid", 1), ("directionOutput", 1), ("skip", 14),
        ("TotalLoadPower", 1), ("skip", 8), ("pvPower", 1),
        ("batteryPower", 1), ("totalgridPower", 1), ("skip", 2),
        ("inverterPower", 1), ("skip", 6), ("gridPower", 1)
        ]

        for key, factor in decode_instructions:
            if key == "skip":
                decoder.skip_bytes(factor)
            else:
                data[key] = round(decoder.decode_16bit_int() * factor, 2)

        self.last_valid_data['additional_data'] = data
        return data

    
    
    def read_additional_modbus_data_2(self) -> dict:
        additional_data2_regs, additional_data2_success = self.try_read_registers(1, 16575, 64)
        
        if not additional_data2_success:
            return self.last_valid_data.get('additional_data_2', {})
        
        decoder = BinaryPayloadDecoder.fromRegisters(additional_data2_regs, byteorder=Endian.BIG)
        data = {}    
        
        
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
    
        
        for key in data_keys:
            decoded_value = decoder.decode_32bit_uint()
            data[key] = round(decoded_value * 0.01, 2)

        self.last_valid_data['additional_data_2'] = data
        return data
        
        
    def read_additional_modbus_data_3(self) -> dict:
        additional_data3_regs, additional_data3_success = self.try_read_registers(1, 16711, 48)
        
        if not additional_data3_success:
            return self.last_valid_data.get('additional_data_3', {})
        
        decoder = BinaryPayloadDecoder.fromRegisters(additional_data3_regs, byteorder=Endian.BIG)
        data = {}


        data_keys = [
            
            "sell_today_energy_2", "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
            "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3", "sell_total_energy_3",
            "feedin_today_energy_2", "feedin_month_energy_2", "feedin_year_energy_2", "feedin_total_energy_2",
            "feedin_today_energy_3", "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
            "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year", "sum_feed_in_total",
            "sum_sell_today", "sum_sell_month", "sum_sell_year", "sum_sell_total"
        ]
    
        
        for key in data_keys:
            decoded_value = decoder.decode_32bit_uint()
            data[key] = round(decoded_value * 0.01, 2)

        self.last_valid_data['additional_data_3'] = data
        return data
        



    def log_error(self, message: str):
        _LOGGER.error(message)


    def translate_fault_code_to_messages(
        self, fault_code: int, fault_messages: list
    ) -> list:
        messages = []
        if not fault_code:
            return messages

        for code, mesg in fault_messages:
            if fault_code & code:
                messages.append(mesg)

        return messages