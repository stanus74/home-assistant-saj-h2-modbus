"""SAJ Modbus Hub"""
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from voluptuous.validators import Number
from homeassistant.helpers.typing import HomeAssistantType

import logging
import threading
import asyncio
import time


from datetime import timedelta
from homeassistant.core import CALLBACK_TYPE, callback
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ModbusIOException


from .const import (
    DEVICE_STATUSSES,
    FAULT_MESSAGES,
)

_LOGGER = logging.getLogger(__name__)


class SAJModbusHub(DataUpdateCoordinator[dict]):
    """Thread safe wrapper class for pymodbus."""

    def __init__(
        self,
        hass: HomeAssistantType,
        name: str,
        host: str,
        port: Number,
        scan_interval: Number,
    ):
        """Initialize the Modbus hub."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )

        self._client = ModbusTcpClient(host=host, port=port, timeout=7)
        self._lock = threading.Lock()

        self.inverter_data: dict = {}
        self.data: dict = {}
        self.last_valid_data = {}  

    @callback
    def async_remove_listener(self, update_callback: CALLBACK_TYPE) -> None:
        """Remove data update listener."""
        super().async_remove_listener(update_callback)

        """No listeners left then close connection"""
        if not self._listeners:
            self.close()

    def close(self) -> None:
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def _read_holding_registers(
        self, unit, address, count
    ) -> ReadHoldingRegistersResponse:
        """Read holding registers."""
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            self._client = ModbusTcpClient(host=self._client.host, port=self._client.port, timeout=7)
            self._client.connect()
        with self._lock:
            return self._client.read_holding_registers(address=address, count=count, slave=unit)

    
    async def _check_and_reconnect(self):
        """Check if the connection is stable and reconnect if necessary."""
        if not self._client.connected:
            _LOGGER.error("Connection to the inverter is not stable, reconnecting...")
            self._client.close()
            await asyncio.sleep(2)  # wait for 2 seconds before attempting to reconnect
            if not self._client.connect():
                _LOGGER.error("Failed to reconnect to the inverter.")
                raise ConnectionException("Failed to reconnect to the inverter.")


    
    
    async def _async_update_data(self) -> dict:
     realtime_data = {}
     additional_data = {}
     additional_data_2 = {}

     try:
        # Connect to the inverter
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            raise ConnectionException("Failed to connect to the inverter.")

        """Inverter info is only fetched once"""
        if not self.inverter_data:
            self.inverter_data = await self.hass.async_add_executor_job(
                self.read_modbus_inverter_data
            )
            #self._client.close()  # Close the connection after fetching inverter data

        # Second query without rebuilding the connection
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            raise ConnectionException("Failed to connect to the inverter.")
        realtime_data = await self.hass.async_add_executor_job(
            self.read_modbus_realtime_data
        )
        self._client.close()  # Close the connection after fetching realtime data

        # Third query without rebuilding the connection
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            raise ConnectionException("Failed to connect to the inverter.")
        additional_data = await self.hass.async_add_executor_job(
            self.read_additional_modbus_data
        )
        self._client.close()  # Close the connection after fetching additional data

        # Fourth query without rebuilding the connection
        if not self._client.connect():
            _LOGGER.error("Failed to connect to the inverter.")
            raise ConnectionException("Failed to connect to the inverter.")
        additional_data_2 = await self.hass.async_add_executor_job(
            self.read_additional_modbus_data_2
        )
        self._client.close()  # Close the connection after fetching additional data 2

     except ConnectionException as e:
        _LOGGER.error("Reading realtime data failed! Inverter is unreachable. Error: %s", e)
        realtime_data["mpvmode"] = 0
        realtime_data["mpvstatus"] = DEVICE_STATUSSES[0]
        realtime_data["power"] = 0

     return {**self.inverter_data, **realtime_data, **additional_data, **additional_data_2}



    def read_modbus_inverter_data(self) -> dict:
        try:
            inverter_data = self._read_holding_registers(unit=1, address=0x8F00, count=29)
            if not isinstance(inverter_data, ReadHoldingRegistersResponse) or inverter_data.isError():
                self.log_error("Error when reading the inverter Modbus data")
                return {}
        except ModbusIOException as e:
            self.log_error(f"Modbus IO exception when reading the inverter data: {e}")
            return {}

        if len(inverter_data.registers) < 29:  # Stellen Sie sicher, dass genügend Register für die gesamte geplante Dekodierung vorliegen
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
        try:
            additional_data = self._read_holding_registers(unit=1, address=16494, count=64)
            if not isinstance(additional_data, ReadHoldingRegistersResponse) or additional_data.isError():
                self.log_error("Error when reading the additional Modbus data")
                
                return self.last_valid_data.get('additional_data', {})  
            
        except ModbusIOException as e:
            self.log_error(f"Modbus IO exception when reading the additional data: {e}")
            
            return self.last_valid_data.get('additional_data', {})  

        if len(additional_data.registers) < 64:  
            self.log_error("Incomplete data when reading the additional Modbus data 2")
            return self.last_valid_data.get('additional_data', {})  


        decoder = BinaryPayloadDecoder.fromRegisters(additional_data.registers, byteorder=Endian.BIG)
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

        
        self.last_valid_data['additional_data_2'] = data

        return data

    def log_error(self, message: str):
        _LOGGER.error(message)
        
  
    def read_additional_modbus_data_2(self) -> dict:
        try:
            additional_data2 = self._read_holding_registers(unit=1, address=16572, count=67)
            if not isinstance(additional_data2, ReadHoldingRegistersResponse) or additional_data2.isError():
                self.log_error("Error when reading the additional Modbus data 2")
                return self.last_valid_data.get('additional_data_2', {})  

        except ModbusIOException as e:
            self.log_error(f"Modbus IO exception when reading the additional data 2: {e}")
            return self.last_valid_data.get('additional_data_2', {})

        if len(additional_data2.registers) < 67:  
            self.log_error("Incomplete data when reading the additional Modbus data 2")
            return self.last_valid_data.get('additional_data_2', {})  


        decoder2 = BinaryPayloadDecoder.fromRegisters(additional_data2.registers, byteorder=Endian.BIG)
        data = {}

        
        data["todayhour"] = round(decoder2.decode_16bit_uint() * 0.1, 1)
        data["totalhour"] = round(decoder2.decode_32bit_uint() * 0.1, 1)

               
        data["todayenergy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["monthenergy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["yearenergy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["totalenergy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        
        
        data["bat_today_charge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_month_charge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_year_charge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_total_charge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

        
        data["bat_today_discharge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_month_discharge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_year_discharge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["bat_total_discharge"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

          
        
        data["inv_today_gen"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["inv_month_gen"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["inv_year_gen"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["inv_total_gen"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

        
        data["total_today_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["total_month_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["total_year_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["total_total_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

        
        data["backup_today_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["backup_month_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["backup_year_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["backup_total_load"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

        
        data["sell_today_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["sell_month_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["sell_year_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["sell_total_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)

        
        data["feedin_today_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["feedin_month_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["feedin_year_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        data["feedin_total_energy"] = round(decoder2.decode_32bit_uint() * 0.01, 2)
        
        

        self.last_valid_data['additional_data_2'] = data

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
