import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pymodbus.client import AsyncModbusTcpClient

from . import modbus_readers
from .modbus_utils import (
    try_read_registers,
    try_write_registers,
    ModbusConnection,
    ReconnectionNeededError,
    set_modbus_config,
)

# Import of the Pending-Setter Factory and Fields
from .charge_control import ChargeSettingHandler, PENDING_FIELDS, make_pending_setter

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

        # Pending settings
        self._pending_charge_start: Optional[str] = None
        self._pending_charge_end: Optional[str] = None
        self._pending_charge_day_mask: Optional[int] = None
        self._pending_charge_power_percent: Optional[int] = None
        self._pending_discharge_start: Optional[str] = None
        self._pending_discharge_end: Optional[str] = None
        self._pending_discharge_day_mask: Optional[int] = None
        self._pending_discharge_power_percent: Optional[int] = None
        
        # Pending settings for additional discharge times
        self._pending_discharge2_start: Optional[str] = None
        self._pending_discharge2_end: Optional[str] = None
        self._pending_discharge2_day_mask: Optional[int] = None
        self._pending_discharge2_power_percent: Optional[int] = None
        self._pending_discharge3_start: Optional[str] = None
        self._pending_discharge3_end: Optional[str] = None
        self._pending_discharge3_day_mask: Optional[int] = None
        self._pending_discharge3_power_percent: Optional[int] = None
        self._pending_discharge4_start: Optional[str] = None
        self._pending_discharge4_end: Optional[str] = None
        self._pending_discharge4_day_mask: Optional[int] = None
        self._pending_discharge4_power_percent: Optional[int] = None
        self._pending_discharge5_start: Optional[str] = None
        self._pending_discharge5_end: Optional[str] = None
        self._pending_discharge5_day_mask: Optional[int] = None
        self._pending_discharge5_power_percent: Optional[int] = None
        self._pending_discharge6_start: Optional[str] = None
        self._pending_discharge6_end: Optional[str] = None
        self._pending_discharge6_day_mask: Optional[int] = None
        self._pending_discharge6_power_percent: Optional[int] = None
        self._pending_discharge7_start: Optional[str] = None
        self._pending_discharge7_end: Optional[str] = None
        self._pending_discharge7_day_mask: Optional[int] = None
        self._pending_discharge7_power_percent: Optional[int] = None
        
        self._pending_export_limit: Optional[int] = None
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None
        self._pending_app_mode: Optional[int] = None
        self._pending_discharge_time_enable: Optional[int] = None

        self._setting_handler = ChargeSettingHandler(self)

    for _name, _suffix in PENDING_FIELDS:
        locals()[f"set_{_name}"] = make_pending_setter(_name, _suffix)
    del _name, _suffix

    def _create_client(self) -> AsyncModbusTcpClient:
        client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=10,
        )
        _LOGGER.debug(f"Created new Modbus client: AsyncModbusTcpClient {self._host}:{self._port}")
        return client

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        async with self._connection_lock:
            self.updating_settings = True
            try:
                connection_changed = (host != self._host) or (port != self._port)
                self._host = host
                self._port = port
                set_modbus_config(self._host, self._port)
                self.update_interval = timedelta(seconds=scan_interval)

                if connection_changed:
                    _LOGGER.info(f"Connection settings changed to {host}:{port}, reconnecting...")
                    self._client = self._create_client()
                else:
                    _LOGGER.info(f"Updated scan interval to {scan_interval} seconds")
            finally:
                self.updating_settings = False

    async def reconnect_client(self) -> bool:
        async with self._connection_lock:
            _LOGGER.info("Reconnecting Modbus client...")
            if self._reconnecting:
                _LOGGER.debug("Reconnection already in progress, waiting...")
                return False
            try:
                self._reconnecting = True
                self._client = self._create_client()
                async with ModbusConnection(self._client, self._host, self._port):
                    _LOGGER.info("Reconnection successful.")
                    return True
            except Exception as e:
                _LOGGER.error("Reconnection failed: %s", e)
                return False
            finally:
                self._reconnecting = False

    async def _async_update_data(self) -> Dict[str, Any]:
        start_total = time.monotonic()

        if self._client is None:
            self._client = self._create_client()

        try:
            async with ModbusConnection(self._client, self._host, self._port):

                
                pending_handlers = [
                    (self._pending_charging_state is not None, self._setting_handler.handle_pending_charging_state),
                    (self._pending_discharging_state is not None, self._setting_handler.handle_pending_discharging_state),
                    (True, self._setting_handler.handle_charge_settings),
                    (True, self._setting_handler.handle_discharge_settings),
                    (self._pending_discharge2_start is not None or 
                     self._pending_discharge2_end is not None or 
                     self._pending_discharge2_day_mask is not None or 
                     self._pending_discharge2_power_percent is not None, 
                     self._setting_handler.handle_discharge2_settings),
                    (self._pending_discharge3_start is not None or 
                     self._pending_discharge3_end is not None or 
                     self._pending_discharge3_day_mask is not None or 
                     self._pending_discharge3_power_percent is not None, 
                     self._setting_handler.handle_discharge3_settings),
                    (self._pending_discharge4_start is not None or 
                     self._pending_discharge4_end is not None or 
                     self._pending_discharge4_day_mask is not None or 
                     self._pending_discharge4_power_percent is not None, 
                     self._setting_handler.handle_discharge4_settings),
                    (self._pending_discharge5_start is not None or 
                     self._pending_discharge5_end is not None or 
                     self._pending_discharge5_day_mask is not None or 
                     self._pending_discharge5_power_percent is not None, 
                     self._setting_handler.handle_discharge5_settings),
                    (self._pending_discharge6_start is not None or 
                     self._pending_discharge6_end is not None or 
                     self._pending_discharge6_day_mask is not None or 
                     self._pending_discharge6_power_percent is not None, 
                     self._setting_handler.handle_discharge6_settings),
                    (self._pending_discharge7_start is not None or 
                     self._pending_discharge7_end is not None or 
                     self._pending_discharge7_day_mask is not None or 
                     self._pending_discharge7_power_percent is not None, 
                     self._setting_handler.handle_discharge7_settings),
                    (True, self._setting_handler.handle_export_limit),
                    (self._pending_app_mode is not None, self._setting_handler.handle_app_mode),
                    (self._pending_discharge_time_enable is not None, self._setting_handler.handle_discharge_time_enable),
                ]
                
                for condition, handler in pending_handlers:
                    if condition:
                        await handler()

                combined_data: Dict[str, Any] = {}
                if not self.inverter_data:
                    self.inverter_data.update(
                        await modbus_readers.read_modbus_inverter_data(self._client)
                    )
                combined_data.update(self.inverter_data)

                async def execute_reader_method(method):
                    """Helper function to execute a reader method with error handling."""
                    try:
                        result = await method(self._client)
                        combined_data.update(result)
                    except ReconnectionNeededError as e:
                        _LOGGER.warning(f"{method.__name__} required reconnection: {e}")
                    except Exception:
                        _LOGGER.exception("Unexpected error during update")
                    await asyncio.sleep(0.3)

                reader_methods = [
                    modbus_readers.read_modbus_realtime_data,
                    modbus_readers.read_additional_modbus_data_1_part_1,
                    modbus_readers.read_additional_modbus_data_1_part_2,
                    modbus_readers.read_additional_modbus_data_2_part_1,
                    modbus_readers.read_additional_modbus_data_2_part_2,
                    modbus_readers.read_additional_modbus_data_3,
                    modbus_readers.read_additional_modbus_data_3_2,
                    modbus_readers.read_additional_modbus_data_4,
                    modbus_readers.read_battery_data,
                    modbus_readers.read_charge_data,
                    modbus_readers.read_discharge_data,  # Reads all discharges at once
                    modbus_readers.read_anti_reflux_data,
                    modbus_readers.read_passive_battery_data,
                ]
                
                for method in reader_methods:
                    await execute_reader_method(method)

                combined_data["charging_enabled"] = await self.get_charging_state()
                combined_data["discharging_enabled"] = await self.get_discharging_state()

                duration_total = time.monotonic() - start_total
                
                return combined_data
        except Exception as e:
            _LOGGER.error(f"Unexpected error during update: {e}")
            return {}

    async def _get_state(self, register: int, state_type: str) -> bool:
        
        try:
            regs = await self._read_registers(register)
            
            return bool(regs[0])
        except Exception as e:
            _LOGGER.error(f"Error reading {state_type} state: {e}")
            return False
            
    async def get_charging_state(self) -> bool:
        return await self._get_state(0x3604, "Charging")

    async def get_discharging_state(self) -> bool:
        return await self._get_state(0x3605, "Discharging")

    async def _read_registers(self, address: int, count: int = 1) -> List[int]:
        return await try_read_registers(
            self._client,
            self._read_lock,
            1,
            address,
            count,
        )

    async def _write_register(self, address: int, value: int) -> bool:
        return await try_write_registers(
            self._client,
            self._read_lock,
            1,
            address,
            value,
        )
