import asyncio
import logging
import time
from datetime import timedelta
from typing import List, Callable, Any, Dict, Optional, Tuple
import inspect
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.register_read_message import ReadHoldingRegistersResponse

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
        # self.last_valid_data wurde entfernt
        self._closing = False
        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30

    def _create_client(self) -> AsyncModbusTcpClient:
        """Creates a new optimized instance of the AsyncModbusTcpClient."""
        client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=10,
            retries=self._max_retries,
            retry_on_empty=True,
            close_comm_on_error=False,
            strict=False
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


    async def ensure_connection(self) -> bool:
        """Ensure the Modbus connection is established and stable."""
        if self._client and self._client.connected:
                return True

        try:
                self._client = self._client or self._create_client()
                if await asyncio.wait_for(self._client.connect(), timeout=10):
                        _LOGGER.info("Successfully connected to Modbus server.")
                        return True
                _LOGGER.warning("Failed to connect to Modbus server.")
        except Exception as e:
                _LOGGER.warning(f"Error during connection attempt: {e}", exc_info=True)

        return False

    async def try_read_registers(
        self,
        unit: int,
        address: int,
        count: int,
        max_retries: int = 3,
        base_delay: float = 2.0
    ) -> List[int]:
        """Reads Modbus registers with optimized error handling and on-demand connection check."""
        start_time = time.time()

        for attempt in range(max_retries):
                try:
                        # Establish connection only if needed
                        if not self._client or not await self.ensure_connection():
                                raise ConnectionException("Unable to establish connection")

                        # Read attempt with Modbus client
                        async with self._read_lock:
                                response = await self._client.read_holding_registers(address, count, slave=unit)

                        # Check the response and number of registers
                        if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) != count:
                                raise ModbusIOException(f"Invalid response from address {address}")

                        #_LOGGER.info(f"Successfully read registers at address {address}.")
                        return response.registers

                except (ModbusIOException, ConnectionException) as e:
                        _LOGGER.error(f"Read attempt {attempt + 1} failed at address {address}: {e}")

                        # Exponential backoff for retry
                        if attempt < max_retries - 1:
                                await asyncio.sleep(min(base_delay * (2 ** attempt), 10.0))

                                # In case of connection problems, safely close the current connection and rebuild it
                                if not await self._safe_close():
                                        _LOGGER.warning("Failed to safely close the Modbus client.")
                                        
                                # Ensure reconnection
                                if not await self.ensure_connection():
                                        _LOGGER.error("Failed to reconnect Modbus client.")
                                else:
                                        _LOGGER.info("Reconnected Modbus client successfully.")

        # If all attempts failed
        _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
        raise ConnectionException(f"Read operation failed for address {address} after {max_retries} attempts")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Updates all data records."""
        if not self.inverter_data:
                self.inverter_data.update(await self.read_modbus_inverter_data())

        data_read_methods = [
                self.read_modbus_realtime_data,
                self.read_additional_modbus_data_1_part_1,
                self.read_additional_modbus_data_1_part_2,
                self.read_additional_modbus_data_2_part_1,
                self.read_additional_modbus_data_2_part_2,
                self.read_additional_modbus_data_3,
		self.read_charging_modbus_data_1
        ]

        combined_data = {**self.inverter_data}

        for read_method in data_read_methods:
                combined_data.update(await read_method())
                await asyncio.sleep(0.2)  # 200ms pause between read operations

        return combined_data

    async def _read_modbus_data(
        self,
        start_address: int,
        count: int,
        decode_instructions: List[tuple],
        data_key: str,
        default_decoder: str = "decode_16bit_uint",
        default_factor: float = 0.01
    ) -> Dict[str, Any]:
        """
        Reads and decodes Modbus data with optional default decoder and factor.

        Args:
            start_address (int): Starting address for reading registers.
            count (int): Number of registers to read.
            decode_instructions (List[tuple]): Decoding instructions [(key, method, factor)].
            data_key (str): Key for logging or tracking data context.
            default_decoder (str): Default decoding method to use when none is specified.
            default_factor (float): Default factor to apply when none is specified.

        Returns:
            Dict[str, Any]: Decoded data as a dictionary.
        """
        try:
            regs = await self.try_read_registers(1, start_address, count)
            decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)
            new_data: Dict[str, Any] = {}

            for instruction in decode_instructions:
                try:
                    key, method, factor = instruction if len(instruction) == 3 else (*instruction, default_factor)
                    method = method or default_decoder  # Use default decoder if none is specified

                    if method == "skip_bytes":
                        decoder.skip_bytes(factor)
                        continue

                    if not key:
                        continue

                    value = getattr(decoder, method)()
                    if isinstance(value, bytes):
                        value = value.decode("ascii", errors="replace").strip()
                    
                    new_data[key] = round(value * factor, 2) if factor != 1 else value

                except Exception as e:
                    _LOGGER.error(f"Error decoding {key}: {e}")
                    return {}

            return new_data

        except Exception as e:
            _LOGGER.error(f"Error reading modbus data: {e}")
            return {}


    async def read_modbus_inverter_data(self) -> Dict[str, Any]:
        """Reads basic inverter data."""
        try:
            regs = await self.try_read_registers(1, 0x8F00, 29)
            decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)
            data = {}

            # Basic parameters
            for key in ["devtype", "subtype"]:
                data[key] = decoder.decode_16bit_uint()

            # Communication version
            data["commver"] = round(decoder.decode_16bit_uint() * 0.001, 3)

            # Serial number and PC
            for key in ["sn", "pc"]:
                data[key] = decoder.decode_string(20).decode("ascii", errors="replace").strip()

            # Hardware versions
            for key in ["dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]:
                data[key] = round(decoder.decode_16bit_uint() * 0.001, 3)

            
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
        from sensor directionPV to gridPower.
        """
        decode_instructions_part_2 = [
            ("directionPV", None), ("directionBattery", "decode_16bit_int"),
            ("directionGrid", "decode_16bit_int"), ("directionOutput", None),
            (None, "skip_bytes", 14), ("TotalLoadPower", "decode_16bit_int"),
            (None, "skip_bytes", 8), ("pvPower", "decode_16bit_int"),
            ("batteryPower", "decode_16bit_int"), ("totalgridPower", "decode_16bit_int"),
            (None, "skip_bytes", 2), ("inverterPower", "decode_16bit_int"),
            (None, "skip_bytes", 6), ("gridPower", "decode_16bit_int"),
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
        """Reads additional operating data (Set 3)."""
        data_keys = [
            "sell_today_energy_2", "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
            "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3", "sell_total_energy_3",
            "feedin_today_energy_2", "feedin_month_energy_2", "feedin_year_energy_2", "feedin_total_energy_2",
            "feedin_today_energy_3", "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
            "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year", "sum_feed_in_total",
            "sum_sell_today", "sum_sell_month", "sum_sell_year", "sum_sell_total",
        ]
        decode_instructions = [(key, "decode_32bit_uint", 0.01) for key in data_keys]
        return await self._read_modbus_data(16711, 48, decode_instructions, 'additional_data_3')

    async def read_charging_modbus_data_1(self) -> Dict[str, Any]:
        """Reads charging-related data (Set 1)."""

        decode_instructions_charging_part_1 = [
            ("passchargeena", "decode_16bit_uint"),      
            ("passgridchargepow", "decode_16bit_uint", 0.001),               
            ("passgriddischargepow", "decode_16bit_uint", 0.001),               
            ("passbatchargepow", "decode_16bit_uint", 0.001),               
            ("passbatdischargepow", "decode_16bit_uint", 0.001),               
            (None, "skip_bytes", 18),                  
            ("batongriddisdepth", "decode_16bit_uint"),               
            ("batoffgriddisdepth", "decode_16bit_uint"),               
            ("batchargedepth", "decode_16bit_uint"),               
            ("appmode", "decode_16bit_uint"),               
            (None, "skip_bytes", 10),                  
            ("batchargepow", "decode_16bit_uint", 0.001),               
            ("batdischargepow", "decode_16bit_uint", 0.001),               
            ("gridchargepow", "decode_16bit_uint", 0.001),               
            ("griddischargepow", "decode_16bit_uint", 0.001),               
        ]

        return await self._read_modbus_data(
            13878, 27, decode_instructions_charging_part_1, 'charging_data_1',
            default_decoder="decode_16bit_uint", default_factor=1
        )

