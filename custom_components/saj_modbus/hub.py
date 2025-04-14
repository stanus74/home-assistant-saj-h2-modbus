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
from .modbus_utils import (
    try_read_registers,
    ensure_connection,
    safe_close,
    close_connection as modbus_close,
    ReconnectionNeededError
)

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
        
        # Pending charging and discharging state
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None
        
        # Pending Charge variables (Format "HH:MM" or int)
        self._pending_charge_start: Optional[str] = None
        self._pending_charge_end: Optional[str] = None
        self._pending_charge_day_mask: Optional[int] = None
        self._pending_charge_power_percent: Optional[int] = None
        
        # Pending Discharge variables (Format "HH:MM" or int)
        self._pending_discharge_start: Optional[str] = None
        self._pending_discharge_end: Optional[str] = None
        self._pending_discharge_day_mask: Optional[int] = None
        self._pending_discharge_power_percent: Optional[int] = None
        
        # Pending Export Limit variable
        self._pending_export_limit: Optional[int] = None

    def _create_client(self) -> AsyncModbusTcpClient:
        """Creates a new instance of AsyncModbusTcpClient."""
        client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=10,
        )
        _LOGGER.debug(f"Created new Modbus client: AsyncModbusTcpClient {self._host}:{self._port}")
        return client

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Updates the connection parameters with improved synchronization."""
        async with self._connection_lock:
            self.updating_settings = True
            try:
                connection_changed = (host != self._host) or (port != self._port)
                self._host = host
                self._port = port
                self.update_interval = timedelta(seconds=scan_interval)

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    if self._client:
                        await safe_close(self._client)
                    self._client = self._create_client()
                    connected = await ensure_connection(self._client, self._host, self._port, max_retries=3)
                    if not connected:
                        _LOGGER.error(f"Failed to connect to new address {host}:{port}")
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")
            finally:
                self.updating_settings = False

    async def reconnect_client(self) -> bool:
        """Closes the current client and creates a new one to restore the connection."""
        async with self._connection_lock:
            _LOGGER.info("Reconnecting Modbus client...")
            if self._reconnecting:
                _LOGGER.debug("Reconnection already in progress, waiting...")
                return False
                
            try:
                self._reconnecting = True
                if self._client:
                    await safe_close(self._client)
                
                # Short pause before reconnecting
                await asyncio.sleep(1)
                
                self._client = self._create_client()
                connected = await ensure_connection(self._client, self._host, self._port, max_retries=3)
                
                if connected:
                    _LOGGER.info("Reconnection successful.")
                else:
                    _LOGGER.error("Reconnection failed after multiple attempts.")
                return connected
            finally:
                self._reconnecting = False

    async def _async_update_data(self) -> Dict[str, Any]:
        # Create the client if it doesn't exist yet, and ensure the connection is established.
        if self._client is None:
            self._client = self._create_client()
        
        # Try to establish the connection with multiple retry attempts
        if not await ensure_connection(self._client, self._host, self._port, max_retries=3):
            _LOGGER.error("Connection could not be established after multiple attempts.")
            return {}

        try:
            # Initial reading of inverter data (one-time)
            if not self.inverter_data:
                self.inverter_data.update(await modbus_readers.read_modbus_inverter_data(self._client))
            
            combined_data = {**self.inverter_data}

            # List of all methods that provide additional data
            reader_methods = [
                modbus_readers.read_modbus_realtime_data,
                modbus_readers.read_additional_modbus_data_1_part_1,
                modbus_readers.read_additional_modbus_data_1_part_2,
                modbus_readers.read_additional_modbus_data_2_part_1,
                modbus_readers.read_additional_modbus_data_2_part_2,
                modbus_readers.read_additional_modbus_data_3,
                modbus_readers.read_additional_modbus_data_3_2,  # New method for the second part of the data
                modbus_readers.read_additional_modbus_data_4,
                modbus_readers.read_battery_data,
                modbus_readers.read_charge_data,
                modbus_readers.read_discharge_data,
                modbus_readers.read_anti_reflux_data,  # New method for Anti-Reflux data
            ]
            
            # Iterate over all reader methods
            for method in reader_methods:
                try:
                    result = await method(self._client)
                    combined_data.update(result)
                except ReconnectionNeededError as e:
                    _LOGGER.warning(f"{method.__name__} required reconnection: {e}")
                    if await self.reconnect_client():
                        # Try again after successful reconnection
                        try:
                            result = await method(self._client)
                            combined_data.update(result)
                        except Exception as inner_e:
                            _LOGGER.error(f"Error after reconnection in {method.__name__}: {inner_e}")
                    else:
                        _LOGGER.error("Reconnection failed during update cycle.")
                except Exception as e:
                    _LOGGER.error(f"Error in {method.__name__}: {e}")
                
                # Short pause between read operations
                await asyncio.sleep(0.5)
            
            # Query the current charging and discharging status
            try:
                # Lese den aktuellen Zustand des Charge-Schalters
                charging_state = await self.get_charging_state()
                combined_data["charging_enabled"] = charging_state
                
                # Lese den aktuellen Zustand des Discharge-Schalters
                discharging_state = await self.get_discharging_state()
                combined_data["discharging_enabled"] = discharging_state

                # Handle pending charging status update
                if self._pending_charging_state is not None:
                    if self._pending_charging_state != charging_state:
                        await self._handle_pending_charging_state()
                        charging_state = await self.get_charging_state()
                        combined_data["charging_enabled"] = charging_state
                    else:
                        _LOGGER.info("Charging state unchanged, no write required.")
                        self._pending_charging_state = None
                        
                # Handle pending discharging status update
                if self._pending_discharging_state is not None:
                    if self._pending_discharging_state != discharging_state:
                        await self._handle_pending_discharging_state()
                        discharging_state = await self.get_discharging_state()
                        combined_data["discharging_enabled"] = discharging_state
                    else:
                        _LOGGER.info("Discharging state unchanged, no write required.")
                        self._pending_discharging_state = None
            except Exception as e:
                _LOGGER.error(f"Error handling charging/discharging state: {e}")

            # Handle pending Charge settings
            if (self._pending_charge_start is not None or
                self._pending_charge_end is not None or
                self._pending_charge_day_mask is not None or
                self._pending_charge_power_percent is not None):
                _LOGGER.info(
                    "Writing Charge values: start=%s, end=%s, day_mask=%s, power_percent=%s",
                    self._pending_charge_start,
                    self._pending_charge_end,
                    self._pending_charge_day_mask,
                    self._pending_charge_power_percent
                )
                await self._handle_pending_charge_settings()
                # The new values will be read again in the next cycle.
            
            # Handle pending Discharge settings
            if (self._pending_discharge_start is not None or
                self._pending_discharge_end is not None or
                self._pending_discharge_day_mask is not None or
                self._pending_discharge_power_percent is not None):
                _LOGGER.info(
                    "Writing Discharge values: start=%s, end=%s, day_mask=%s, power_percent=%s",
                    self._pending_discharge_start,
                    self._pending_discharge_end,
                    self._pending_discharge_day_mask,
                    self._pending_discharge_power_percent
                )
                await self._handle_pending_discharge_settings()
                # The new values will be read again in the next cycle.
                
            # Handle pending Export Limit setting
            if self._pending_export_limit is not None:
                _LOGGER.info(f"Writing Export Limit value: {self._pending_export_limit}")
                await self._handle_pending_export_limit()
                # The new value will be read again in the next cycle.

             # Close connection after the update cycle
            if self._client:
                await modbus_close(self._client)
            
                
            return combined_data

        except Exception as e:
            _LOGGER.error(f"Unexpected error during update: {e}")
            return {}

    async def _handle_pending_charge_settings(self) -> None:
        """Writes the pending Charge settings to the corresponding registers."""
        async with self._read_lock:
            # Register 0x3606: Start time (High Byte = Hour, Low Byte = Minute)
            if self._pending_charge_start is not None:
                try:
                    hour, minute = map(int, self._pending_charge_start.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x3606, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set charge start time: {self._pending_charge_start}")
                    else:
                        _LOGGER.error(f"Failed to write charge start time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing charge start time: {e}")
                finally:
                    self._pending_charge_start = None

            # Register 0x3607: End time (High Byte = Hour, Low Byte = Minute)
            if self._pending_charge_end is not None:
                try:
                    hour, minute = map(int, self._pending_charge_end.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x3607, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set charge end time: {self._pending_charge_end}")
                    else:
                        _LOGGER.error(f"Failed to write charge end time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing charge end time: {e}")
                finally:
                    self._pending_charge_end = None

            # Register 0x3608: Power Time (High Byte = Day Mask, Low Byte = Power Percent)
            if self._pending_charge_day_mask is not None or self._pending_charge_power_percent is not None:
                try:
                    response = await self._client.read_holding_registers(address=0x3608, count=1)
                    if not response or response.isError() or len(response.registers) < 1:
                        current_value = 0
                    else:
                        current_value = response.registers[0]
                    current_day_mask = (current_value >> 8) & 0xFF
                    current_power_percent = current_value & 0xFF

                    day_mask = self._pending_charge_day_mask if self._pending_charge_day_mask is not None else current_day_mask
                    power_percent = self._pending_charge_power_percent if self._pending_charge_power_percent is not None else current_power_percent

                    value = (day_mask << 8) | power_percent
                    response = await self._client.write_register(0x3608, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set charge power time: day_mask={day_mask}, power_percent={power_percent}")
                    else:
                        _LOGGER.error(f"Failed to write charge power time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing charge power time: {e}")
                finally:
                    self._pending_charge_day_mask = None
                    self._pending_charge_power_percent = None
    
    async def _handle_pending_discharge_settings(self) -> None:
        """Writes the pending Discharge settings to the corresponding registers."""
        async with self._read_lock:
            # Register 0x361B: Start time (High Byte = Hour, Low Byte = Minute)
            if self._pending_discharge_start is not None:
                try:
                    hour, minute = map(int, self._pending_discharge_start.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x361B, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set discharge start time: {self._pending_discharge_start}")
                    else:
                        _LOGGER.error(f"Failed to write discharge start time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing discharge start time: {e}")
                finally:
                    self._pending_discharge_start = None

            # Register 0x361C: End time (High Byte = Hour, Low Byte = Minute)
            if self._pending_discharge_end is not None:
                try:
                    hour, minute = map(int, self._pending_discharge_end.split(":"))
                    value = (hour << 8) | minute
                    response = await self._client.write_register(0x361C, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set discharge end time: {self._pending_discharge_end}")
                    else:
                        _LOGGER.error(f"Failed to write discharge end time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing discharge end time: {e}")
                finally:
                    self._pending_discharge_end = None

            # Register 0x361D: Power Time (High Byte = Day Mask, Low Byte = Power Percent)
            if self._pending_discharge_day_mask is not None or self._pending_discharge_power_percent is not None:
                try:
                    response = await self._client.read_holding_registers(address=0x361D, count=1)
                    if not response or response.isError() or len(response.registers) < 1:
                        current_value = 0
                    else:
                        current_value = response.registers[0]
                    current_day_mask = (current_value >> 8) & 0xFF
                    current_power_percent = current_value & 0xFF

                    day_mask = self._pending_discharge_day_mask if self._pending_discharge_day_mask is not None else current_day_mask
                    power_percent = self._pending_discharge_power_percent if self._pending_discharge_power_percent is not None else current_power_percent

                    value = (day_mask << 8) | power_percent
                    response = await self._client.write_register(0x361D, value)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set discharge power time: day_mask={day_mask}, power_percent={power_percent}")
                    else:
                        _LOGGER.error(f"Failed to write discharge power time: {response}")
                except Exception as e:
                    _LOGGER.error(f"Error writing discharge power time: {e}")
                finally:
                    self._pending_discharge_day_mask = None
                    self._pending_discharge_power_percent = None
                    
    # Setter methods that are called by HA when the sensors change:
    async def set_charge_start(self, time_str: str) -> None:
        """Sets the new start time (format 'HH:MM') for Charge."""
        self._pending_charge_start = time_str

    async def set_charge_end(self, time_str: str) -> None:
        """Sets the new end time (format 'HH:MM') for Charge."""
        self._pending_charge_end = time_str

    async def set_charge_day_mask(self, day_mask: int) -> None:
        """Sets the new Day Mask value for Charge."""
        self._pending_charge_day_mask = day_mask

    async def set_charge_power_percent(self, power_percent: int) -> None:
        """Sets the new Power Percent value for Charge."""
        self._pending_charge_power_percent = power_percent

    async def _handle_pending_charging_state(self) -> dict:
        """Writes the pending charging status to register 0x3647."""
        if self._pending_charging_state is not None:
            # Prüfe den Status des anderen Schalters (Discharging)
            discharging_state = await self.get_discharging_state()
            
            # Setze Wert für Register 0x3647 nur auf 0, wenn beide Schalter aus sind
            value = 1 if self._pending_charging_state or discharging_state else 0
            
            async with self._read_lock:
                # Schreibe in Register 0x3647
                _LOGGER.debug(f"Schreibe Charging-Status in Register 0x3647: {value} (Charging={self._pending_charging_state}, Discharging={discharging_state})")
                response = await self._client.write_register(0x3647, value)
                if response and not response.isError():
                    _LOGGER.info(f"Successfully set charging to: {self._pending_charging_state} (Register 0x3647={value})")
                else:
                    _LOGGER.error(f"Failed to set charging state: {response}")
                
                # Schreibe in Register 0x3604 den Wert 1 (wenn aktiviert) oder 0 (wenn deaktiviert)
                reg_value = 1 if self._pending_charging_state else 0
                _LOGGER.debug(f"Schreibe Charging-Status in Register 0x3604: {reg_value}")
                response = await self._client.write_register(0x3604, reg_value)
                if response and not response.isError():
                    _LOGGER.info(f"Successfully set register 0x3604 to {reg_value}")
                else:
                    _LOGGER.error(f"Failed to set register 0x3604: {response}")
            
            self._pending_charging_state = None
        return {}
        
    async def _handle_pending_discharging_state(self) -> dict:
        """Writes the pending discharging status to register 0x3647."""
        if self._pending_discharging_state is not None:
            # Prüfe den Status des anderen Schalters (Charging)
            charging_state = await self.get_charging_state()
            
            # Setze Wert für Register 0x3647 nur auf 0, wenn beide Schalter aus sind
            value = 1 if self._pending_discharging_state or charging_state else 0
            
            async with self._read_lock:
                # Schreibe in Register 0x3647 (gleiches Register wie für Charging)
                _LOGGER.debug(f"Schreibe Discharging-Status in Register 0x3647: {value} (Discharging={self._pending_discharging_state}, Charging={charging_state})")
                response = await self._client.write_register(0x3647, value)
                if response and not response.isError():
                    _LOGGER.info(f"Successfully set discharging to: {self._pending_discharging_state} (Register 0x3647={value})")
                else:
                    _LOGGER.error(f"Failed to set discharging state: {response}")
                
                # Schreibe in Register 0x3605 den Wert 1 (wenn aktiviert) oder 0 (wenn deaktiviert)
                reg_value = 1 if self._pending_discharging_state else 0
                _LOGGER.debug(f"Schreibe Discharging-Status in Register 0x3605: {reg_value}")
                response = await self._client.write_register(0x3605, reg_value)
                if response and not response.isError():
                    _LOGGER.info(f"Successfully set register 0x3605 to {reg_value}")
                else:
                    _LOGGER.error(f"Failed to set register 0x3605: {response}")
            
            self._pending_discharging_state = None
        return {}

    async def get_charging_state(self) -> bool:
        """Reads the current charging status from register 0x3604."""
        try:
            regs = await try_read_registers(self._client, self._read_lock, 1, 0x3604, 1)
            _LOGGER.debug(f"Charging state from register 0x3604: {bool(regs[0])}")
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading charging state: {e}")
            return False

    async def get_discharging_state(self) -> bool:
        """Reads the current discharging status from register 0x3605."""
        try:
            regs = await try_read_registers(self._client, self._read_lock, 1, 0x3605, 1)
            _LOGGER.debug(f"Discharging state from register 0x3605: {bool(regs[0])}")
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading discharging state: {e}")
            return False

    async def set_charging(self, enable: bool) -> None:
        """Plans a change of the charging status for the next update cycle."""
        self._pending_charging_state = enable
        
    async def set_discharge_start(self, time_str: str) -> None:
        """Sets the new start time (format 'HH:MM') for Discharge."""
        self._pending_discharge_start = time_str

    async def set_discharge_end(self, time_str: str) -> None:
        """Sets the new end time (format 'HH:MM') for Discharge."""
        self._pending_discharge_end = time_str

    async def set_discharge_day_mask(self, day_mask: int) -> None:
        """Sets the new Day Mask value for Discharge."""
        self._pending_discharge_day_mask = day_mask

    async def set_discharge_power_percent(self, power_percent: int) -> None:
        """Sets the new Power Percent value for Discharge."""
        self._pending_discharge_power_percent = power_percent

    async def set_discharging(self, enable: bool) -> None:
        """Plans a change of the discharging status for the next update cycle."""
        self._pending_discharging_state = enable
        
    async def set_export_limit(self, limit: int) -> None:
        """Sets the new export limit value."""
        self._pending_export_limit = limit
        
    async def _handle_pending_export_limit(self) -> None:
        """Writes the pending export limit to register 0x365A."""
        if self._pending_export_limit is not None:
            try:
                async with self._read_lock:
                    response = await self._client.write_register(0x365A, self._pending_export_limit)
                    if response and not response.isError():
                        _LOGGER.info(f"Successfully set export limit to: {self._pending_export_limit}")
                    else:
                        _LOGGER.error(f"Failed to write export limit: {response}")
            except Exception as e:
                _LOGGER.error(f"Error writing export limit: {e}")
            finally:
                self._pending_export_limit = None
