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
        realtime_data = {}
        additional_data = {}
        additional_data_2 = {}
        additional_data_3 = {}

        def execute_modbus_task(task_function):
            """Wrapper function to execute Modbus tasks with logging and connection checks."""
            if not self._client.connect():
                _LOGGER.error("Failed to connect to the inverter.")
                raise ConnectionException("Failed to connect to the inverter.")
            result = task_function()
            return result

        try:
            # Fetch inverter data if not already fetched
            if not self.inverter_data:
                self.inverter_data = await self.hass.async_add_executor_job(
                    lambda: execute_modbus_task(self.read_modbus_inverter_data)
                )
                await asyncio.sleep(2)  # Pause to reduce load

            # Fetch realtime data
            realtime_data = await self.hass.async_add_executor_job(
                lambda: execute_modbus_task(self.read_modbus_realtime_data)
            )
            await asyncio.sleep(2)

            # Fetch additional data
            additional_data = await self.hass.async_add_executor_job(
                lambda: execute_modbus_task(self.read_additional_modbus_data)
            )
            await asyncio.sleep(2)

            # Fetch additional data 2
            additional_data_2 = await self.hass.async_add_executor_job(
                lambda: execute_modbus_task(self.read_additional_modbus_data_2)
            )
            await asyncio.sleep(2)

            # Fetch additional data 3
            additional_data_3 = await self.hass.async_add_executor_job(
                lambda: execute_modbus_task(self.read_additional_modbus_data_3)
            )

        except ConnectionException as e:
            _LOGGER.error("Reading realtime data failed! Inverter is unreachable. Error: %s", e)
            realtime_data["mpvmode"] = 0
            realtime_data["mpvstatus"] = DEVICE_STATUSSES[0]
            realtime_data["power"] = 0

        finally:
            self.close()

        return {**self.inverter_data, **realtime_data, **additional_data, **additional_data_2, **additional_data_3}



    def read_modbus_inverter_data(self) -> dict:
        try:
            inverter_data = self._read_holding_registers(unit=1, address=0x8F00, count=29)
            if not isinstance(inverter_data, ReadHoldingRegistersResponse) or inverter_data.isError():
                self.log_error("Error when reading the inverter Modbus data")
                return {}
        except ModbusIOException as e:
            self.log_error(f"Modbus IO exception when reading the inverter data: {e}")
            return {}

        if len(inverter_data.registers) < 29:  
            _LOGGER.error(f"Incomplete data when reading the inverter data: Expected 29, received {len(inverter_data.registers) if not inverter_data.isError() else 'Fehler'}")
            return {}

    
        decoder = BinaryPayloadDecoder.fromRegisters(inverter_data.registers, byteorder=Endian.BIG)
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
        try:
            realtime_data = self._read_holding_registers(unit=1, address=0x4004, count=19)
            if not isinstance(realtime_data, ReadHoldingRegistersResponse) or realtime_data.isError():
                self.log_error("Error when reading the additional Modbus data")
                return {}
        except ModbusIOException as e:
            self.log_error(f"Modbus IO exception when reading the realtime data: {e}")
            return {}
            
        if len(realtime_data.registers) < 19:  
            _LOGGER.error(f"Incomplete data when reading Modbus data: Expected 19, received {len(realtime_data.registers)}")

            return {}


        data = {}
        decoder = BinaryPayloadDecoder.fromRegisters(realtime_data.registers, byteorder=Endian.BIG)
        
        mpvmode = decoder.decode_16bit_uint()
        data["mpvmode"] = mpvmode

        if mpvmode in DEVICE_STATUSSES:
            data["mpvstatus"] = DEVICE_STATUSSES[mpvmode]
        else:
            data["mpvstatus"] = "Unknown"

        faultMsg0 = decoder.decode_32bit_uint()
        faultMsg1 = decoder.decode_32bit_uint()
        faultMsg2 = decoder.decode_32bit_uint()
        
        faultMsg = []
        faultMsg.extend(
            self.translate_fault_code_to_messages(faultMsg0, FAULT_MESSAGES[0].items())
        )
        faultMsg.extend(
            self.translate_fault_code_to_messages(faultMsg1, FAULT_MESSAGES[1].items())
        )
        faultMsg.extend(
            self.translate_fault_code_to_messages(faultMsg2, FAULT_MESSAGES[2].items())
        )

        # status value can hold max 255 chars in HA
        data["faultmsg"] = ", ".join(faultMsg).strip()[0:254]
        if faultMsg:
            _LOGGER.error("Fault message: " + ", ".join(faultMsg).strip())
            
        decoder.skip_bytes(8)  
        
        
        errorcount = decoder.decode_16bit_uint()
        data["errorcount"] = errorcount

        
        SinkTemp = decoder.decode_16bit_int()
        data["SinkTemp"] = round(SinkTemp * 0.1, 1)  
        AmbTemp = decoder.decode_16bit_int()
        data["AmbTemp"] = round(AmbTemp * 0.1, 1)
        
        gfci = decoder.decode_16bit_int()
        data["gfci"] = gfci
        
        iso1 = decoder.decode_16bit_uint()
        iso2 = decoder.decode_16bit_uint()
        iso3 = decoder.decode_16bit_uint()
        iso4 = decoder.decode_16bit_uint()
        data["iso1"] = iso1
        data["iso2"] = iso2
        data["iso3"] = iso3
        data["iso4"] = iso4
        
      

        return data

    def read_additional_modbus_data(self) -> dict:
        def try_read_registers(unit, address, count):
            try:
                response = self._read_holding_registers(unit=unit, address=address, count=count)
                if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) < count:
                    self.log_error(f"Error when reading the additional Modbus data from unit {unit} and address {address}")
                    return None
                return response.registers
            except ModbusIOException as e:
                self.log_error(f"Modbus IO exception when reading the additional data: {e}")
                return None

        additional_data_regs = try_read_registers(1, 16494, 64)

        if additional_data_regs is None:
            return self.last_valid_data.get('additional_data', {})

        decoder = BinaryPayloadDecoder.fromRegisters(additional_data_regs, byteorder=Endian.BIG)
        data = {}

        data["BatTemp"] = round(decoder.decode_16bit_uint() * 0.1, 1)
        data["batEnergyPercent"] = round(decoder.decode_16bit_uint() / 100.0, 2)

        decoder.skip_bytes(96)

        data["TotalLoadPower"] = decoder.decode_16bit_int()

        decoder.skip_bytes(8)

        data["pvPower"] = decoder.decode_16bit_int()
        data["batteryPower"] = decoder.decode_16bit_int()

        decoder.skip_bytes(12)

        data["gridPower"] = decoder.decode_16bit_int()

        self.last_valid_data['additional_data'] = data
        return data

    def log_error(self, message: str):
        _LOGGER.error(message)


    def read_additional_modbus_data_2(self) -> dict:
        def try_read_registers(unit, address, count):
            
            try:
                response = self._read_holding_registers(unit=unit, address=address, count=count)
                if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) < count:
                    self.log_error(f"Error when reading the Modbus data from unit {unit} and address {address}")
                    return None, False
                return response.registers, True
            except ModbusIOException as e:
                self.log_error(f"Modbus IO exception when reading the data: {e}")
                return None, False

        additional_data2_regs, additional_data2_success = try_read_registers(1, 16575, 64)
        
        
        if not additional_data2_success:
            return self.last_valid_data.get('additional_data_2', {})
            
            
        def decode_and_round(value):
            
            return round(value * 0.01, 2)  

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
            data[key] = decode_and_round(decoded_value)

        self.last_valid_data['additional_data_2'] = data
        return data
        
        
    def read_additional_modbus_data_3(self) -> dict:
        def try_read_registers(unit, address, count):
            
            try:
                response = self._read_holding_registers(unit=unit, address=address, count=count)
                if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) < count:
                    self.log_error(f"Error when reading the Modbus data from unit {unit} and address {address}")
                    return None, False
                return response.registers, True
            except ModbusIOException as e:
                self.log_error(f"Modbus IO Exception exception when reading the data: {e}")
                return None, False

        
        additional_data3_regs, additional_data3_success = try_read_registers(1, 16711, 48)

        if not additional_data3_success:
            return self.last_valid_data.get('additional_data_3', {})
            
        def decode_and_round(value):
            
            return round(value * 0.01, 2)  

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
            data[key] = decode_and_round(decoded_value)

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
