import asyncio
import logging
import time
import struct
from datetime import timedelta
from typing import List, Callable, Any, Dict, Optional, Tuple
import inspect
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.client.mixin import ModbusClientMixin


from .const import DEVICE_STATUSSES, FAULT_MESSAGES


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
        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
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
                    await self._safe_close()
                    self._client = self._create_client()
                    await self.ensure_connection()
            finally:
                self.updating_settings = False

    async def _safe_close(self) -> bool:
        """Safely closes the Modbus connection."""
        if not self._client:
                return True

        try:
                if self._client.connected:
                        close = getattr(self._client, "close", None)
                        if close:
                                await close() if inspect.iscoroutinefunction(close) else close()
                        transport = getattr(self._client, "transport", None)
                        if transport:
                                transport.close()
                        await asyncio.sleep(0.2)
                        return not self._client.connected
                return True
        except Exception as e:
                _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)
                return False
        finally:
                self._client = None


    async def close(self) -> None:
        """Closes the Modbus connection with improved resource management."""
        if self._closing:
                return

        self._closing = True
        try:
                async with asyncio.timeout(5.0):
                        async with self._connection_lock:
                                await self._safe_close()
        except (asyncio.TimeoutError, Exception) as e:
                _LOGGER.warning(f"Error during close: {e}", exc_info=True)
        finally:
                self._closing = False


    async def ensure_connection(self) -> None:
            """Ensure the Modbus connection is established and stable."""
            if self._client and self._client.connected:
                return

            self._client = self._client or self._create_client()
            try:
                await asyncio.wait_for(self._client.connect(), timeout=10)
                _LOGGER.info("Successfully connected to Modbus server.")
            except Exception as e:
                _LOGGER.warning(f"Error during connection attempt: {e}", exc_info=True)
                raise ConnectionException("Failed to connect to Modbus server.") from e


    async def try_read_registers(
            self,
            unit: int,
            address: int,
            count: int,
            max_retries: int = 3,
            base_delay: float = 2.0
        ) -> List[int]:
            """Reads Modbus registers with optimized error handling."""
            
            # Ensure a client is available
            #if self._client is None:
            #    await self.ensure_connection()
            
            for attempt in range(max_retries):
                try:
                    async with self._read_lock:
                       
                    
                        response = await self._client.read_holding_registers(address=address, count=count)

                    
                    
                    if (not response) or response.isError() or len(response.registers) != count:
                        raise ModbusIOException(f"Invalid response from address {address}")
                        
                    return response.registers
                    
                except (ModbusIOException, ConnectionException) as e:
                    _LOGGER.error(f"Read attempt {attempt + 1} failed at address {address}: {e}")
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), 10.0)
                        await asyncio.sleep(delay)
                        if not await self._safe_close():
                            _LOGGER.warning("Failed to safely close the Modbus client.")
                        try:
                            await self.ensure_connection()
                        except ConnectionException:
                            _LOGGER.error("Failed to reconnect Modbus client.")
                            continue
                        else:
                            _LOGGER.info("Reconnected Modbus client successfully.")
            _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
            raise ConnectionException(f"Read operation failed for address {address} after {max_retries} attempts")

    
    async def _async_update_data(self) -> Dict[str, Any]:
        await self.ensure_connection()
        if not self.inverter_data:
            self.inverter_data.update(await self.read_modbus_inverter_data())
        combined_data = {**self.inverter_data}

        # Loop through all methods that provide dictionary data
        for method in [
            self.read_modbus_realtime_data,
            self.read_additional_modbus_data_1_part_1,
            self.read_additional_modbus_data_1_part_2,
            self.read_additional_modbus_data_2_part_1,
            self.read_additional_modbus_data_2_part_2,
            self.read_additional_modbus_data_3,
            self.read_additional_modbus_data_4,
            self.read_battery_data,
            self.read_first_charge_data,
            
        ]:
            result = await method()
            # Here we assume that each method returns a dictionary.
            combined_data.update(result)
            await asyncio.sleep(0.2)
        
        # Separate call to query the current charging state.
        charging_state = await self.get_charging_state()
        combined_data["charging_enabled"] = charging_state

        # Only execute write operation when a pending charging state is set
        # and differs from the currently read state.
        if self._pending_charging_state is not None:
            if self._pending_charging_state != charging_state:
                await self._handle_pending_charging_state()
                charging_state = await self.get_charging_state()
                combined_data["charging_enabled"] = charging_state
            else:
                _LOGGER.info("Charging state unchanged, no write required.")
                self._pending_charging_state = None
        
        
        # If new First-Charge values are present, write them
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
            # Directly after writing, it will be read in the next cycle.

        
        
        
        
        await self.close()
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





    # Setter-Methoden, die von HA bei Änderung der Sensoren aufgerufen werden:
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

    
    
    # ende charing time


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
            regs = await self.try_read_registers(1, 0x3647, 1)  # Register for charging control
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading charging state: {e}")
            return False


    async def set_charging(self, enable: bool) -> None:
        """Set the charging control state by scheduling it for the next update cycle."""
        self._pending_charging_state = enable
        # The call to async_request_refresh() was removed so that the write operation
        # occurs exclusively in the regular update cycle.


    async def _read_modbus_data(
        self,
        start_address: int,
        count: int,
        decode_instructions: List[tuple],
        data_key: str,
        default_decoder: str = "decode_16bit_uint",
        default_factor: float = 0.01
    ) -> Dict[str, Any]:
        try:
            regs = await self.try_read_registers(1, start_address, count)
            if not regs:
                _LOGGER.error(f"Error reading modbus data: No response for {data_key}")
                return {}

            new_data = {}
            index = 0

            for instruction in decode_instructions:
                key, method, factor = (instruction + (default_factor,))[:3]
                method = method or default_decoder

                if method == "skip_bytes":
                    index += factor // 2  # Each register is 2 bytes in size
                    continue

                if not key:
                    continue

                try:
                    raw_value = regs[index]

                    # Selection of the correct decoding method
                    if method == "decode_16bit_int":
                        value = self._client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.INT16)
                    elif method == "decode_16bit_uint":
                        value = self._client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.UINT16)
                    elif method == "decode_32bit_uint":
                        if index + 1 < len(regs):
                            value = self._client.convert_from_registers([raw_value, regs[index + 1]], ModbusClientMixin.DATATYPE.UINT32)
                            index += 1  # 32-bit values occupy two registers
                        else:
                            value = 0
                    else:
                        value = raw_value  # Default value if no conversion is necessary

                    new_data[key] = round(value * factor, 2) if factor != 1 else value
                    index += 1

                except Exception as e:
                    _LOGGER.error(f"Error decoding {key}: {e}")
                    return {}

            return new_data

        except Exception as e:
            _LOGGER.error(f"Error reading modbus data: {e}")
            return {}


    async def read_modbus_inverter_data(self) -> Dict[str, Any]:
        """Reads basic inverter data using the pymodbus 3.9 API, without BinaryPayloadDecoder."""
        try:
            # Read 29 registers starting from address 0x8F00
            regs = await self.try_read_registers(1, 0x8F00, 29)
            data = {}
            index = 0

            # Basic parameters: devtype and subtype as 16-bit unsigned values
            for key in ["devtype", "subtype"]:
                value = self._client.convert_from_registers(
                    [regs[index]], ModbusClientMixin.DATATYPE.UINT16
                )
                data[key] = value
                index += 1

            # Communication version: 16-bit unsigned, multiplied by 0.001 and rounded to 3 decimal places
            commver = self._client.convert_from_registers(
                [regs[index]], ModbusClientMixin.DATATYPE.UINT16
            )
            data["commver"] = round(commver * 0.001, 3)
            index += 1

            # Serial number and PC: 20 bytes each (equivalent to 10 registers)
            for key in ["sn", "pc"]:
                # Get the next 10 registers
                reg_slice = regs[index : index + 10]
                # Convert each register (16-bit) to 2 bytes in Big-Endian format
                raw_bytes = b"".join(struct.pack(">H", r) for r in reg_slice)
                data[key] = raw_bytes.decode("ascii", errors="replace").strip()
                index += 10

            # Hardware version numbers: Each as 16-bit unsigned, multiplied by 0.001
            for key in ["dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]:
                value = self._client.convert_from_registers(
                    [regs[index]], ModbusClientMixin.DATATYPE.UINT16
                )
                data[key] = round(value * 0.001, 3)
                index += 1

            return data

        except Exception as e:
            _LOGGER.error(f"Error reading inverter data: {e}")
            return {}


    async def read_modbus_realtime_data(self) -> Dict[str, Any]:
        """Reads real-time operating data."""

        decode_instructions = [
            ("mpvmode", None),                     
            ("faultMsg0", "decode_32bit_uint"),    
            ("faultMsg1", "decode_32bit_uint"),
            ("faultMsg2", "decode_32bit_uint"),
            (None, "skip_bytes", 8),              
            ("errorcount", None),                
            ("SinkTemp", "decode_16bit_int", 0.1),
            ("AmbTemp", "decode_16bit_int", 0.1),
            ("gfci", None),                      
            ("iso1", None),                       
            ("iso2", None),
            ("iso3", None),
            ("iso4", None),
        ]

        
        data = await self._read_modbus_data(
            16388, 19, decode_instructions, 'realtime_data',
            default_decoder="decode_16bit_uint", default_factor=1
        )


        # Process fault messages
        fault_messages = []
        for key in ["faultMsg0", "faultMsg1", "faultMsg2"]:
            fault_code = data.get(key, 0)
            fault_messages.extend([
                msg for code, msg in FAULT_MESSAGES[int(key[-1])].items()
                if fault_code & code
            ])
            data[key] = fault_code

        data["mpvstatus"] = DEVICE_STATUSSES.get(data.get("mpvmode"), "Unknown")
        data["faultmsg"] = ", ".join(fault_messages).strip()[:254]
        
        if fault_messages:
            _LOGGER.error(f"Fault detected: {data['faultmsg']}")
            
        return data


    async def read_additional_modbus_data_1_part_1(self) -> Dict[str, Any]:
        """Reads the first part of additional operating data (Set 1), up to sensor pv4Power."""

        decode_instructions_part_1 = [
            ("BatTemp", "decode_16bit_int", 0.1),      
            ("batEnergyPercent", None),               
            (None, "skip_bytes", 2),                  
            ("pv1Voltage", None, 0.1),                
            ("pv1TotalCurrent", None),                
            ("pv1Power", None,1),                       
            ("pv2Voltage", None, 0.1),                
            ("pv2TotalCurrent", None),                
            ("pv2Power", None,1),                       
            ("pv3Voltage", None, 0.1),
            ("pv3TotalCurrent", None),
            ("pv3Power", None,1),
            ("pv4Voltage", None, 0.1),
            ("pv4TotalCurrent", None),
            ("pv4Power", None,1),
        ]

        return await self._read_modbus_data(
            16494, 15, decode_instructions_part_1, 'additional_data_1_part_1',
            default_decoder="decode_16bit_uint", default_factor=0.01
        )

    async def read_additional_modbus_data_1_part_2(self) -> Dict[str, Any]:
            """
            Reads the second part of additional operating data (Set 1),
            incorporating the provided registers and correct skip_bytes adjustments.
            """
            decode_instructions_part_2 = [
                ("directionPV", None),  
                ("directionBattery", "decode_16bit_int"),  
                ("directionGrid", "decode_16bit_int"),  
                ("directionOutput", None),  
                (None, "skip_bytes", 14),  
                ("TotalLoadPower", "decode_16bit_int"),  
                ("CT_GridPowerWatt", "decode_16bit_int"),  
                ("CT_GridPowerVA", "decode_16bit_int"),  
                ("CT_PVPowerWatt", "decode_16bit_int"),  
                ("CT_PVPowerVA", "decode_16bit_int"),  
                ("pvPower", "decode_16bit_int"),  
                ("batteryPower", "decode_16bit_int"),  
                ("totalgridPower", "decode_16bit_int"),  
                ("totalgridPowerVA", "decode_16bit_int"),  
                ("inverterPower", "decode_16bit_int"),  
                ("TotalInvPowerVA", "decode_16bit_int"),  
                ("BackupTotalLoadPowerWatt", "decode_16bit_uint"),  
                ("BackupTotalLoadPowerVA", "decode_16bit_uint"),  
                ("gridPower", "decode_16bit_int"),  
            ]

            
            return await self._read_modbus_data(
                16533, 25, decode_instructions_part_2, 'additional_data_1_part_2',
                default_decoder="decode_16bit_uint", default_factor=1
            )




    async def read_additional_modbus_data_2_part_1(self) -> Dict[str, Any]:
        """Reads the first part of additional operating data (Set 2)."""

        data_keys_part_1 = [
                "todayenergy", "monthenergy", "yearenergy", "totalenergy",
                "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
                "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
                "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
        ]
        decode_instructions_part_1 = [(key, "decode_32bit_uint", 0.01) for key in data_keys_part_1]

        return await self._read_modbus_data(16575, 32, decode_instructions_part_1, 'additional_data_2_part_1')

    async def read_additional_modbus_data_2_part_2(self) -> Dict[str, Any]:
        """Reads the second part of additional operating data (Set 2)."""

        data_keys_part_2 = [
                "total_today_load", "total_month_load", "total_year_load", "total_total_load",
                "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
                "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
                "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
        ]
        decode_instructions_part_2 = [(key, "decode_32bit_uint", 0.01) for key in data_keys_part_2]

        return await self._read_modbus_data(16607, 32, decode_instructions_part_2, 'additional_data_2_part_2')



    async def read_additional_modbus_data_3(self) -> Dict[str, Any]:
        
       
        data_keys_part_3 = [
            "today_pv_energy2", "month_pv_energy2", "year_pv_energy2",
            "total_pv_energy2", "today_pv_energy3", "month_pv_energy3",
            "year_pv_energy3", "total_pv_energy3", "sell_today_energy_2",
            "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
            "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3",
            "sell_total_energy_3", "feedin_today_energy_2", "feedin_month_energy_2",
            "feedin_year_energy_2", "feedin_total_energy_2", "feedin_today_energy_3",
            "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
            "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year",
            "sum_feed_in_total", "sum_sell_today", "sum_sell_month",
            "sum_sell_year", "sum_sell_total"
        ]
        decode_instructions_part_3 = [(key, "decode_32bit_uint", 0.01) for key in data_keys_part_3]
        
        return await self._read_modbus_data(16695, 64, decode_instructions_part_3, 'additional_data_3')

     
        
    async def read_additional_modbus_data_4(self) -> Dict[str, Any]:
            """
            Reads data for grid parameters (R, S, and T phase).
            """
            decode_instructions = [
                ("RGridVolt", None, 0.1),
                ("RGridCurr", "decode_16bit_int", 0.01),
                ("RGridFreq", None, 0.01),
                ("RGridDCI", "decode_16bit_int", 0.001),
                ("RGridPowerWatt", "decode_16bit_int", 1),
                ("RGridPowerVA", None, 1),
                ("RGridPowerPF", "decode_16bit_int", 0.001),
                ("SGridVolt", None, 0.1),
                ("SGridCurr", "decode_16bit_int", 0.01),
                ("SGridFreq", None, 0.01),
                ("SGridDCI", "decode_16bit_int", 0.001),
                ("SGridPowerWatt", "decode_16bit_int", 1),
                ("SGridPowerVA", None, 1),
                ("SGridPowerPF", "decode_16bit_int", 0.001),
                ("TGridVolt", None, 0.1),
                ("TGridCurr", "decode_16bit_int", 0.01),
                ("TGridFreq", None, 0.01),
                ("TGridDCI", "decode_16bit_int", 0.001),
                ("TGridPowerWatt", "decode_16bit_int", 1),
                ("TGridPowerVA", None, 1),
                ("TGridPowerPF", "decode_16bit_int", 0.001),
                ]


            
            return await self._read_modbus_data(
                16433, 21, decode_instructions, "grid_phase_data",
                default_decoder="decode_16bit_uint", default_factor=1
            )
            
            
    async def read_battery_data(self) -> Dict[str, Any]:
        """
        Reads battery data from registers 40960 to 41015.
        
        Note: There is a gap sector between register 40995 (Bat4CycleNum) and 
        41002 (Bat1DischarCapH), which is skipped using 'skip_bytes'.
        """
        decode_instructions = [
        # Registers 40960 to 40995 (first 36 registers)
        ("BatNum",            "decode_16bit_uint", 1),         # 40960
        ("BatCapcity",        "decode_16bit_uint", 1),         # 40961
        ("Bat1FaultMSG",      "decode_16bit_uint", 1),         # 40962
        ("Bat1WarnMSG",       "decode_16bit_uint", 1),         # 40963
        ("Bat2FaultMSG",      "decode_16bit_uint", 1),         # 40964
        ("Bat2WarnMSG",       "decode_16bit_uint", 1),         # 40965
        ("Bat3FaultMSG",      "decode_16bit_uint", 1),         # 40966
        ("Bat3WarnMSG",       "decode_16bit_uint", 1),         # 40967
        ("Bat4FaultMSG",      "decode_16bit_uint", 1),         # 40968
        ("Bat4WarnMSG",       "decode_16bit_uint", 1),         # 40969
        ("BatUserCap",        "decode_16bit_uint", 1),         # 40970
        ("BatOnline",         "decode_16bit_uint", 1),         # 40971
        ("Bat1SOC",           "decode_16bit_uint", 0.01),      # 40972, Ratio -2 → 0.01
        ("Bat1SOH",           "decode_16bit_uint", 0.01),      # 40973, Ratio -2
        ("Bat1Voltage",       "decode_16bit_uint", 0.1),       # 40974, Ratio -1 → 0.1
        ("Bat1Current",       "decode_16bit_int", 0.01),       # 40975, Int16, Ratio -2
        ("Bat1Temperature",   "decode_16bit_int", 0.1),        # 40976, Int16, Ratio -1
        ("Bat1CycleNum",      "decode_16bit_uint", 1),         # 40977
        ("Bat2SOC",           "decode_16bit_uint", 0.01),      # 40978
        ("Bat2SOH",           "decode_16bit_uint", 0.01),      # 40979
        ("Bat2Voltage",       "decode_16bit_uint", 0.1),       # 40980
        ("Bat2Current",       "decode_16bit_int", 0.01),       # 40981
        ("Bat2Temperature",   "decode_16bit_int", 0.1),        # 40982
        ("Bat2CycleNum",      "decode_16bit_uint", 1),         # 40983
        ("Bat3SOC",           "decode_16bit_uint", 0.01),      # 40984
        ("Bat3SOH",           "decode_16bit_uint", 0.01),      # 40985
        ("Bat3Voltage",       "decode_16bit_uint", 0.1),       # 40986
        ("Bat3Current",       "decode_16bit_int", 0.01),       # 40987
        ("Bat3Temperature",   "decode_16bit_int", 0.1),        # 40988
        ("Bat3CycleNum",      "decode_16bit_uint", 1),         # 40989
        ("Bat4SOC",           "decode_16bit_uint", 0.01),      # 40990
        ("Bat4SOH",           "decode_16bit_uint", 0.01),      # 40991
        ("Bat4Voltage",       "decode_16bit_uint", 0.1),       # 40992
        ("Bat4Current",       "decode_16bit_int", 0.01),       # 40993
        ("Bat4Temperature",   "decode_16bit_int", 0.1),        # 40994
        ("Bat4CycleNum",      "decode_16bit_uint", 1),         # 40995
        
        # --> Insert register jump here (skip registers 40996 to 41001):
        (None, "skip_bytes", 12),  # 6 Register * 2 Bytes = 12 Bytes
        
        # Registers 41002 to 41015 (next 14 registers)
        ("Bat1DischarCapH",   "decode_16bit_uint", 1),         # 41002
        ("Bat1DischarCapL",   "decode_16bit_uint", 1),         # 41003
        ("Bat2DischarCapH",   "decode_16bit_uint", 1),         # 41004
        ("Bat2DischarCapL",   "decode_16bit_uint", 1),         # 41005
        ("Bat3DischarCapH",   "decode_16bit_uint", 1),         # 41006
        ("Bat3DischarCapL",   "decode_16bit_uint", 1),         # 41007
        ("Bat4DischarCapH",   "decode_16bit_uint", 1),         # 41008
        ("Bat4DischarCapL",   "decode_16bit_uint", 1),         # 41009
        ("BatProtHigh",       "decode_16bit_uint", 0.1),       # 41010, Ratio -1 → 0.1
        ("BatProtLow",        "decode_16bit_uint", 0.1),       # 41011, Ratio -1 → 0.1
        ("Bat_Chargevoltage", "decode_16bit_uint", 0.1),       # 41012, Ratio -1 → 0.1
        ("Bat_DisCutOffVolt", "decode_16bit_uint", 0.1),       # 41013, Ratio -1 → 0.1
        ("BatDisCurrLimit",   "decode_16bit_uint", 0.1),       # 41014, Ratio -1 → 0.1
        ("BatChaCurrLimit",   "decode_16bit_uint", 0.1),       # 41015, Ratio -1 → 0.1
        
        ]
       
        
        return await self._read_modbus_data(40960, 56, decode_instructions, 'battery_data')



    async def read_first_charge_data(self) -> Dict[str, Any]:
        """Reads the First Charge registers:
        
        - Register 0x3606: start_time (High Byte: Hour, Low Byte: Minute)
        - Register 0x3607: end_time (High Byte: Hour, Low Byte: Minute)
        - Register 0x3608: power_time (High Byte: Day (as bitmask), Low Byte: Power in %)
        """
        try:
            # Address in hexadecimal (0x3606 corresponds to 13830 decimal)
            regs = await self.try_read_registers(1, 0x3606, 3)
            if not regs or len(regs) < 3:
                _LOGGER.error("Not enough data received for First Charge registers.")
                return {}

            def decode_time(value: int) -> str:
                """Decodes a time value from a register (High Byte: Hour, Low Byte: Minute)"""
                return f"{(value >> 8) & 0xFF:02d}:{value & 0xFF:02d}"

            start_time = decode_time(regs[0])  # Start time from register 0x3606
            end_time = decode_time(regs[1])    # End time from register 0x3607

            # Power Time from register 0x3608
            power_value = regs[2]
            day_mask = (power_value >> 8) & 0xFF  # e.g., 0b0100 corresponds to Wednesday
            power_percent = power_value & 0xFF    # e.g., 1 corresponds to 1% of standard power

            return {
                "first_charge_start_time": start_time,
                "first_charge_end_time": end_time,
                "first_charge_day_mask": day_mask,
                "first_charge_power_percent": power_percent,
            }
        except Exception as e:
            _LOGGER.error(f"Error reading First Charge data: {e}", exc_info=True)
            return {}
