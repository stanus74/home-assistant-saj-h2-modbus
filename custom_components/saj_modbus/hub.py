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
    """Optimized SAJ Modbus Hub Implementation."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str,
        port: int,
        scan_interval: int,
    ) -> None:
        """Initializes the SAJ Modbus Hub with improved error handling."""
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
        self.last_valid_data: Dict[str, Any] = {}
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
        """Safe method to close the connection with feedback."""
        client = self._client
        if not client:
                _LOGGER.debug("No client instance to close.")
                return True  # No active connection, therefore already "successfully closed"

        try:
                # If the connection is active, close it
                if getattr(client, 'connected', False):
                        close = getattr(client, 'close', None)
                        if close:
                                # If close is a coroutine, use await
                                if inspect.iscoroutinefunction(close):
                                        await close()
                                else:
                                        close()

                # Ensure transport connection and close it
                transport = getattr(client, 'transport', None)
                if transport:
                        transport.close()
                        _LOGGER.debug("Transport layer closed successfully.")

                await asyncio.sleep(0.2)

                # Check if the connection is closed
                if not client.connected:
                        _LOGGER.info("Modbus client disconnected successfully.")
                        return True  # Successful closure
                else:
                        _LOGGER.warning("Failed to disconnect Modbus client properly.")
                        return False  # Connection could not be terminated correctly

        except Exception as e:
                _LOGGER.error(f"Error while closing Modbus client: {e}", exc_info=True)
                return False  # Error case, connection was not closed properly

        finally:
                self._client = None  # Reset client reference



    async def close(self) -> None:
        """Closes the Modbus connection with improved resource management."""
        if self._closing:
            return

        self._closing = True
        try:
            async with asyncio.timeout(5.0):
                async with self._connection_lock:
                    await self._safe_close()
        except asyncio.TimeoutError:
            _LOGGER.error("Close operation timed out")
            await self._safe_close()
        except Exception as e:
            _LOGGER.error(f"Unexpected error during close: {e}", exc_info=True)
            await self._safe_close()
        finally:
            self._closing = False

    async def ensure_connection(self) -> bool:
        """Ensures a stable Modbus connection."""
        async with self._connection_lock:
                try:
                        # Check if the connection is already active
                        if self._client and self._client.connected:
                                #_LOGGER.debug("Modbus client is already connected.")
                                return True

                        # Initialize the Modbus client if it doesn't exist
                        self._client = self._client or self._create_client()

                        # Multiple reconnection attempts with exponential backoff
                        for attempt in range(3):
                                try:
                                        _LOGGER.debug(f"Connection attempt {attempt + 1}/3 to Modbus server.")
                                        # Establish connection and adjust timeout
                                        if await asyncio.wait_for(self._client.connect(), timeout=10):
                                                _LOGGER.info("Successfully connected to Modbus server.")
                                                return True

                                except (asyncio.TimeoutError, ConnectionException) as e:
                                        _LOGGER.warning(f"Connection attempt {attempt + 1} failed: {e}")

                                        # Exponential backoff between attempts
                                        if attempt < 2:
                                                await asyncio.sleep(2 ** attempt + 2)

                                        # In case of error, safely close and create a new client
                                        if not await self._safe_close():
                                                _LOGGER.error("Error during safe close; attempting new client creation.")
                                        self._client = self._create_client()

                        # After all failed connection attempts
                        _LOGGER.error("All connection attempts to Modbus server failed.")
                        return False

                except Exception as e:
                        _LOGGER.error(f"Unexpected error in ensure_connection: {e}", exc_info=True)
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

                except (ModbusIOException, ConnectionException, TypeError, ValueError) as e:
                        _LOGGER.error(f"Read attempt {attempt + 1} failed at address {address}: {e}")

                        # Exponential backoff for retry
                        if attempt < max_retries - 1:
                                await asyncio.sleep(min(base_delay * (2 ** attempt), 10.0))

                                # In case of connection problems, safely close the current connection and rebuild it
                                if not await self._safe_close():
                                        _LOGGER.error("Failed to safely close the Modbus client.")
                                        
                                await asyncio.sleep(0.5)  # Additional pause after connection problem  
                                
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
                self.read_additional_modbus_data_3
        ]

        combined_data = {**self.inverter_data}

        for read_method in data_read_methods:
                combined_data.update(await read_method())
                await asyncio.sleep(0.5)  # 500ms pause between read operations

        return combined_data



    async def _read_modbus_data(
        self,
        start_address: int,
        count: int,
        decode_instructions: List[tuple],
        data_key: str
    ) -> Dict[str, Any]:
        """Reads and decodes Modbus data."""
        last_valid = self.last_valid_data.get(data_key, {})

        try:
            regs = await self.try_read_registers(1, start_address, count)
            decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)
            new_data: Dict[str, Any] = {}

            for instruction in decode_instructions:
                try:
                    key, method, factor = instruction
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
                    return last_valid

            self.last_valid_data[data_key] = new_data
            return new_data

        except Exception as e:
            _LOGGER.error(f"Error reading modbus data: {e}")
            return last_valid



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

            self.last_valid_data['inverter_data'] = data
            return data

        except Exception as e:
            _LOGGER.error(f"Error reading inverter data: {e}")
            return self.last_valid_data.get('inverter_data', {})

    async def read_modbus_realtime_data(self) -> Dict[str, Any]:
        """Reads real-time operating data."""
        decode_instructions = [
            ("mpvmode", "decode_16bit_uint", 1),
            ("faultMsg0", "decode_32bit_uint", 1),
            ("faultMsg1", "decode_32bit_uint", 1),
            ("faultMsg2", "decode_32bit_uint", 1),
            (None, "skip_bytes", 8),
            ("errorcount", "decode_16bit_uint", 1),
            ("SinkTemp", "decode_16bit_int", 0.1),
            ("AmbTemp", "decode_16bit_int", 0.1),
            ("gfci", "decode_16bit_int", 1),
            ("iso1", "decode_16bit_uint", 1),
            ("iso2", "decode_16bit_uint", 1),
            ("iso3", "decode_16bit_uint", 1),
            ("iso4", "decode_16bit_uint", 1),
        ]

        data = await self._read_modbus_data(16388, 19, decode_instructions, 'realtime_data')
        
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
                ("BatTemp", "decode_16bit_int", 0.1), ("batEnergyPercent", "decode_16bit_uint", 0.01), (None, "skip_bytes", 2),
                ("pv1Voltage", "decode_16bit_uint", 0.1), ("pv1TotalCurrent", "decode_16bit_uint", 0.01), ("pv1Power", "decode_16bit_uint", 1),
                ("pv2Voltage", "decode_16bit_uint", 0.1), ("pv2TotalCurrent", "decode_16bit_uint", 0.01), ("pv2Power", "decode_16bit_uint", 1),
                ("pv3Voltage", "decode_16bit_uint", 0.1), ("pv3TotalCurrent", "decode_16bit_uint", 0.01), ("pv3Power", "decode_16bit_uint", 1),
                ("pv4Voltage", "decode_16bit_uint", 0.1), ("pv4TotalCurrent", "decode_16bit_uint", 0.01), ("pv4Power", "decode_16bit_uint", 1),
        ]

        return await self._read_modbus_data(16494, 15, decode_instructions_part_1, 'additional_data_1_part_1')

    async def read_additional_modbus_data_1_part_2(self) -> Dict[str, Any]:
        """Reads the second part of additional operating data (Set 1), from sensor directionPV to gridPower."""

        decode_instructions_part_2 = [
                ("directionPV", "decode_16bit_uint", 1), ("directionBattery", "decode_16bit_int", 1),
                ("directionGrid", "decode_16bit_int", 1), ("directionOutput", "decode_16bit_uint", 1), (None, "skip_bytes", 14),
                ("TotalLoadPower", "decode_16bit_int", 1), (None, "skip_bytes", 8), ("pvPower", "decode_16bit_int", 1),
                ("batteryPower", "decode_16bit_int", 1), ("totalgridPower", "decode_16bit_int", 1), (None, "skip_bytes", 2),
                ("inverterPower", "decode_16bit_int", 1), (None, "skip_bytes", 6), ("gridPower", "decode_16bit_int", 1),
        ]

        return await self._read_modbus_data(16533, 25, decode_instructions_part_2, 'additional_data_1_part_2')


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
