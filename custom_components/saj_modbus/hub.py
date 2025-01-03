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
            for attempt in range(max_retries):
                try:
                    async with self._read_lock:
                        response = await self._client.read_holding_registers(address, count, slave=unit)
                    if not (
                        isinstance(response, ReadHoldingRegistersResponse)
                        and not response.isError()
                        and len(response.registers) == count
                    ):
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
            for method in [
                self.read_modbus_realtime_data,
                self.read_additional_modbus_data_1_part_1,
                self.read_additional_modbus_data_1_part_2,
                self.read_additional_modbus_data_2_part_1,
                self.read_additional_modbus_data_2_part_2,
                self.read_additional_modbus_data_3,
                self.read_additional_modbus_data_4
            ]:
                combined_data.update(await method())
                await asyncio.sleep(0.2)
            await self.close()
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
            try:
                regs = await self.try_read_registers(1, start_address, count)
                decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)
                new_data = {}

                for instruction in decode_instructions:
                    key, method, factor = (instruction + (default_factor,))[:3]
                    method = method or default_decoder

                    if method == "skip_bytes":
                        decoder.skip_bytes(factor)
                        continue

                    if not key:
                        continue

                    try:
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
            incorporating the provided registers and correct skip_bytes adjustments.
            """
            decode_instructions_part_2 = [
                ("directionPV", None),  # 16533
                ("directionBattery", "decode_16bit_int"),  # 16534
                ("directionGrid", "decode_16bit_int"),  # 16535
                ("directionOutput", None),  # 16536
                (None, "skip_bytes", 14),  # Skip to 16544 (16544 - 16536 = 8 registers or 16 bytes)
                ("TotalLoadPower", "decode_16bit_int"),  # 16544
                ("CT_GridPowerWatt", "decode_16bit_int"),  # 16545
                ("CT_GridPowerVA", "decode_16bit_int"),  # 16546
                ("CT_PVPowerWatt", "decode_16bit_int"),  # 16547
                ("CT_PVPowerVA", "decode_16bit_int"),  # 16548
                ("pvPower", "decode_16bit_int"),  # 16549
                ("batteryPower", "decode_16bit_int"),  # 16550
                ("totalgridPower", "decode_16bit_int"),  # 16551
                ("totalgridPowerVA", "decode_16bit_int"),  # 16552
                ("inverterPower", "decode_16bit_int"),  # 16553
                ("TotalInvPowerVA", "decode_16bit_int"),  # 16554
                ("BackupTotalLoadPowerWatt", "decode_16bit_uint"),  # 16555
                ("BackupTotalLoadPowerVA", "decode_16bit_uint"),  # 16556
                ("gridPower", "decode_16bit_int"),  # 16557
            ]

            # Total register count: (16557 - 16533 + 1) = 25
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
        
        
        
    async def read_additional_modbus_data_4(self) -> Dict[str, Any]:
            """
            Reads data for grid parameters (R, S, and T phase).
            """
            decode_instructions = [
                ("RGridVolt", None, 0.1),  # 16433, Spannung in V
                ("RGridCurr", "decode_16bit_int", 0.01),  # 16434, Strom in A
                ("RGridFreq", None, 0.01),  # 16435, Frequenz in Hz
                ("RGridDCI", "decode_16bit_int", 0.001),  # 16436, DC-Komponente in mA
                ("RGridPowerWatt", "decode_16bit_int", 1),  # 16437, Leistung in W
                ("RGridPowerVA", None, 1),  # 16438, Scheinleistung in VA
                ("RGridPowerPF", "decode_16bit_int", 0.001),  # 16439, Leistungsfaktor
                ("SGridVolt", None, 0.1),  # 16440, Spannung in V
                ("SGridCurr", "decode_16bit_int", 0.01),  # 16441, Strom in A
                ("SGridFreq", None, 0.01),  # 16442, Frequenz in Hz
                ("SGridDCI", "decode_16bit_int", 0.001),  # 16443, DC-Komponente in mA
                ("SGridPowerWatt", "decode_16bit_int", 1),  # 16444, Leistung in W
                ("SGridPowerVA", None, 1),  # 16445, Scheinleistung in VA
                ("SGridPowerPF", "decode_16bit_int", 0.001),  # 16446, Leistungsfaktor
                ("TGridVolt", None, 0.1),  # 16447, Spannung in V
                ("TGridCurr", "decode_16bit_int", 0.01),  # 16448, Strom in A
                ("TGridFreq", None, 0.01),  # 16449, Frequenz in Hz
                ("TGridDCI", "decode_16bit_int", 0.001),  # 16450, DC-Komponente in mA
                ("TGridPowerWatt", "decode_16bit_int", 1),  # 16451, Leistung in W
                ("TGridPowerVA", None, 1),  # 16452, Scheinleistung in VA
                ("TGridPowerPF", "decode_16bit_int", 0.001),  # 16453, Leistungsfaktor
                ]


            # Total register count: (16453 - 16433 + 1) = 21
            return await self._read_modbus_data(
                16433, 21, decode_instructions, "grid_phase_data",
                default_decoder="decode_16bit_uint", default_factor=1
            )

