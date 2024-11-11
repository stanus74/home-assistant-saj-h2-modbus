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
    """Optimierte SAJ Modbus Hub Implementation."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str,
        port: int,
        scan_interval: int,
    ) -> None:
        """Initialisiert den SAJ Modbus Hub mit verbesserter Fehlerbehandlung."""
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
        """Erstellt eine neue optimierte Instanz des AsyncModbusTcpClient."""
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
        """Aktualisiert die Verbindungseinstellungen mit verbesserter Synchronisation."""
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
        """Sichere Methode zum Schließen der Verbindung mit Rückmeldung."""
        client = self._client
        if not client:
                _LOGGER.debug("No client instance to close.")
                return True  # Keine aktive Verbindung, daher bereits "erfolgreich geschlossen"

        try:
                # Wenn die Verbindung aktiv ist, schließen
                if getattr(client, 'connected', False):
                        close = getattr(client, 'close', None)
                        if close:
                                # Wenn close eine Coroutine ist, await verwenden
                                if inspect.iscoroutinefunction(close):
                                        await close()
                                else:
                                        close()

                # Transportverbindung sicherstellen und schließen
                transport = getattr(client, 'transport', None)
                if transport:
                        transport.close()
                        _LOGGER.debug("Transport layer closed successfully.")

                await asyncio.sleep(0.2)

                # Überprüfen, ob die Verbindung geschlossen ist
                if not client.connected:
                        _LOGGER.info("Modbus client disconnected successfully.")
                        return True  # Erfolgreiche Schließung
                else:
                        _LOGGER.warning("Failed to disconnect Modbus client properly.")
                        return False  # Verbindung konnte nicht korrekt beendet werden

        except Exception as e:
                _LOGGER.error(f"Error while closing Modbus client: {e}", exc_info=True)
                return False  # Fehlerfall, Verbindung wurde nicht ordnungsgemäß geschlossen

        finally:
                self._client = None  # Client-Referenz zurücksetzen



    async def close(self) -> None:
        """Schließt die Modbus-Verbindung mit verbesserter Ressourcenverwaltung."""
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
        """Stellt eine stabile Modbus-Verbindung sicher."""
        async with self._connection_lock:
                try:
                        # Prüfen, ob die Verbindung bereits aktiv ist
                        if self._client and self._client.connected:
                                #_LOGGER.debug("Modbus client is already connected.")
                                return True

                        # Initialisieren des Modbus-Clients, falls nicht vorhanden
                        self._client = self._client or self._create_client()

                        # Mehrere Versuche zur Wiederverbindung mit exponentiellem Backoff
                        for attempt in range(3):
                                try:
                                        _LOGGER.debug(f"Connection attempt {attempt + 1}/3 to Modbus server.")
                                        # Verbindung herstellen und Timeout anpassen
                                        if await asyncio.wait_for(self._client.connect(), timeout=10):
                                                _LOGGER.info("Successfully connected to Modbus server.")
                                                return True

                                except (asyncio.TimeoutError, ConnectionException) as e:
                                        _LOGGER.warning(f"Connection attempt {attempt + 1} failed: {e}")

                                        # Exponentielles Backoff zwischen den Versuchen
                                        if attempt < 2:
                                                await asyncio.sleep(2 ** attempt + 2)

                                        # Bei Fehler, sicher schließen und neuen Client erstellen
                                        if not await self._safe_close():
                                                _LOGGER.error("Error during safe close; attempting new client creation.")
                                        self._client = self._create_client()

                        # Nach allen fehlgeschlagenen Verbindungsversuchen
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
        """Liest Modbus-Register mit optimierter Fehlerbehandlung und bedarfsbasierter Verbindungsprüfung."""
        start_time = time.time()

        for attempt in range(max_retries):
                try:
                        # Verbindung nur bei Bedarf herstellen
                        if not self._client or not await self.ensure_connection():
                                raise ConnectionException("Unable to establish connection")

                        # Leseversuch mit Modbus-Client
                        async with self._read_lock:
                                response = await self._client.read_holding_registers(address, count, slave=unit)

                        # Überprüfen der Antwort und Registeranzahl
                        if not isinstance(response, ReadHoldingRegistersResponse) or response.isError() or len(response.registers) != count:
                                raise ModbusIOException(f"Invalid response from address {address}")

                        #_LOGGER.info(f"Successfully read registers at address {address}.")
                        return response.registers

                except (ModbusIOException, ConnectionException, TypeError, ValueError) as e:
                        _LOGGER.error(f"Read attempt {attempt + 1} failed at address {address}: {e}")

                        # Exponentielles Backoff für die Wiederholung
                        if attempt < max_retries - 1:
                                await asyncio.sleep(min(base_delay * (2 ** attempt), 10.0))

                                # Bei Verbindungsproblemen aktuelle Verbindung sicher schließen und neu aufbauen
                                if not await self._safe_close():
                                        _LOGGER.error("Failed to safely close the Modbus client.")
                                        
                                await asyncio.sleep(0.5)  # Zusätzliche Pause nach Verbindungsproblem  
                                
                                # Sicherstellen der Neuverbindung
                                if not await self.ensure_connection():
                                        _LOGGER.error("Failed to reconnect Modbus client.")
                                else:
                                        _LOGGER.info("Reconnected Modbus client successfully.")

        # Wenn alle Versuche fehlgeschlagen sind
        _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
        raise ConnectionException(f"Read operation failed for address {address} after {max_retries} attempts")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Aktualisiert alle Datensätze."""
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
                await asyncio.sleep(0.5)  # 500ms Pause zwischen Lesevorgängen

        return combined_data



    async def _read_modbus_data(
        self,
        start_address: int,
        count: int,
        decode_instructions: List[tuple],
        data_key: str
    ) -> Dict[str, Any]:
        """Liest und dekodiert Modbus-Daten."""
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
        """Liest Inverter-Basisdaten."""
        try:
            regs = await self.try_read_registers(1, 0x8F00, 29)
            decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG)
            data = {}

            # Basis-Parameter
            for key in ["devtype", "subtype"]:
                data[key] = decoder.decode_16bit_uint()

            # Kommunikationsversion
            data["commver"] = round(decoder.decode_16bit_uint() * 0.001, 3)

            # Seriennummer und PC
            for key in ["sn", "pc"]:
                data[key] = decoder.decode_string(20).decode("ascii", errors="replace").strip()

            # Hardware-Versionen
            for key in ["dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]:
                data[key] = round(decoder.decode_16bit_uint() * 0.001, 3)

            self.last_valid_data['inverter_data'] = data
            return data

        except Exception as e:
            _LOGGER.error(f"Error reading inverter data: {e}")
            return self.last_valid_data.get('inverter_data', {})

    async def read_modbus_realtime_data(self) -> Dict[str, Any]:
        """Liest Echtzeit-Betriebsdaten."""
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
        
        # Fehlermeldungen verarbeiten
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
        """Liest den ersten Teil zusätzlicher Betriebsdaten (Set 1), bis Sensor pv4Power."""

        decode_instructions_part_1 = [
                ("BatTemp", "decode_16bit_int", 0.1), ("batEnergyPercent", "decode_16bit_uint", 0.01), (None, "skip_bytes", 2),
                ("pv1Voltage", "decode_16bit_uint", 0.1), ("pv1TotalCurrent", "decode_16bit_uint", 0.01), ("pv1Power", "decode_16bit_uint", 1),
                ("pv2Voltage", "decode_16bit_uint", 0.1), ("pv2TotalCurrent", "decode_16bit_uint", 0.01), ("pv2Power", "decode_16bit_uint", 1),
                ("pv3Voltage", "decode_16bit_uint", 0.1), ("pv3TotalCurrent", "decode_16bit_uint", 0.01), ("pv3Power", "decode_16bit_uint", 1),
                ("pv4Voltage", "decode_16bit_uint", 0.1), ("pv4TotalCurrent", "decode_16bit_uint", 0.01), ("pv4Power", "decode_16bit_uint", 1),
        ]

        return await self._read_modbus_data(16494, 15, decode_instructions_part_1, 'additional_data_1_part_1')

    async def read_additional_modbus_data_1_part_2(self) -> Dict[str, Any]:
        """Liest den zweiten Teil zusätzlicher Betriebsdaten (Set 1), ab Sensor directionPV bis gridPower."""

        decode_instructions_part_2 = [
                ("directionPV", "decode_16bit_uint", 1), ("directionBattery", "decode_16bit_int", 1),
                ("directionGrid", "decode_16bit_int", 1), ("directionOutput", "decode_16bit_uint", 1), (None, "skip_bytes", 14),
                ("TotalLoadPower", "decode_16bit_int", 1), (None, "skip_bytes", 8), ("pvPower", "decode_16bit_int", 1),
                ("batteryPower", "decode_16bit_int", 1), ("totalgridPower", "decode_16bit_int", 1), (None, "skip_bytes", 2),
                ("inverterPower", "decode_16bit_int", 1), (None, "skip_bytes", 6), ("gridPower", "decode_16bit_int", 1),
        ]

        return await self._read_modbus_data(16533, 25, decode_instructions_part_2, 'additional_data_1_part_2')


    async def read_additional_modbus_data_2_part_1(self) -> Dict[str, Any]:
        """Liest den ersten Teil zusätzlicher Betriebsdaten (Set 2)."""

        data_keys_part_1 = [
                "todayenergy", "monthenergy", "yearenergy", "totalenergy",
                "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
                "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
                "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
        ]
        decode_instructions_part_1 = [(key, "decode_32bit_uint", 0.01) for key in data_keys_part_1]

        return await self._read_modbus_data(16575, 32, decode_instructions_part_1, 'additional_data_2_part_1')

    async def read_additional_modbus_data_2_part_2(self) -> Dict[str, Any]:
        """Liest den zweiten Teil zusätzlicher Betriebsdaten (Set 2)."""

        data_keys_part_2 = [
                "total_today_load", "total_month_load", "total_year_load", "total_total_load",
                "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
                "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
                "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
        ]
        decode_instructions_part_2 = [(key, "decode_32bit_uint", 0.01) for key in data_keys_part_2]

        return await self._read_modbus_data(16607, 32, decode_instructions_part_2, 'additional_data_2_part_2')



    async def read_additional_modbus_data_3(self) -> Dict[str, Any]:
        """Liest zusätzliche Betriebsdaten (Set 3)."""
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
