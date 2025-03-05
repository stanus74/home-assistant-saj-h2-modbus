import asyncio
import logging
import inspect
from datetime import timedelta
from typing import Any, Dict, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from . import modbus_readers
from .modbus_utils import try_read_registers


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
        
         # Neue Pending-Variablen für First Charge:
        self._pending_first_charge_start: Optional[str] = None  # Erwartet im Format "HH:MM"
        self._pending_first_charge_end: Optional[str] = None    # Erwartet im Format "HH:MM"
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



    
    async def _async_update_data(self) -> Dict[str, Any]:
        await self.ensure_connection()
        if not self.inverter_data:
            self.inverter_data.update(await modbus_readers.read_modbus_inverter_data(self._client))
        combined_data = {**self.inverter_data}

        # Loop through all methods that provide dictionary data
        reader_methods = [
            modbus_readers.read_modbus_realtime_data,
            modbus_readers.read_additional_modbus_data_1_part_1,
            modbus_readers.read_additional_modbus_data_1_part_2,
            modbus_readers.read_additional_modbus_data_2_part_1,
            modbus_readers.read_additional_modbus_data_2_part_2,
            modbus_readers.read_additional_modbus_data_3,
            modbus_readers.read_additional_modbus_data_4,
            modbus_readers.read_battery_data,
            modbus_readers.read_first_charge_data,
        ]
        
        for method in reader_methods:
            result = await method(self._client)
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
        
        
        # Falls neue First-Charge-Werte vorliegen, diese schreiben
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
            # Direkt nach dem Schreiben wird im nächsten Zyklus ausgelesen.

        await self.close()
        return combined_data
        
    async def _handle_pending_first_charge_settings(self) -> None:
        """Schreibt die pending First-Charge-Werte in die Register 0x3606, 0x3607 und 0x3608."""
        async with self._read_lock:
            # Register 0x3606: Start Time (High Byte = Stunde, Low Byte = Minute)
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

            # Register 0x3607: End Time (High Byte = Stunde, Low Byte = Minute)
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
                    # Zuerst den aktuellen Registerwert für 0x3608 auslesen
                    response = await self._client.read_holding_registers(address=0x3608, count=1)
                    if not response or response.isError() or len(response.registers) < 1:
                        current_value = 0
                    else:
                        current_value = response.registers[0]
                    current_day_mask = (current_value >> 8) & 0xFF
                    current_power_percent = current_value & 0xFF

                    # Fehlende Teile mit den Pending-Werten ergänzen (falls vorhanden)
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
        """Setzt den neuen Startzeitpunkt (Format 'HH:MM') für First Charge."""
        self._pending_first_charge_start = time_str

    async def set_first_charge_end(self, time_str: str) -> None:
        """Setzt den neuen Endzeitpunkt (Format 'HH:MM') für First Charge."""
        self._pending_first_charge_end = time_str

    async def set_first_charge_day_mask(self, day_mask: int) -> None:
        """Setzt den neuen Day Mask Wert für First Charge."""
        self._pending_first_charge_day_mask = day_mask

    async def set_first_charge_power_percent(self, power_percent: int) -> None:
        """Setzt den neuen Power Percent Wert für First Charge."""
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
            regs = await try_read_registers(self._client, self._read_lock, 1, 0x3647, 1)  # Register for charging control
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading charging state: {e}")
            return False

    async def set_charging(self, enable: bool) -> None:
        """Set the charging control state by scheduling it for the next update cycle."""
        self._pending_charging_state = enable
        # The call to async_request_refresh() was removed so that the write operation
        # occurs exclusively in the regular update cycle.
