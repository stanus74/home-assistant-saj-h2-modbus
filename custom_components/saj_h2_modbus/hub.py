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
from .charge_control import ChargeSettingHandler, PENDING_FIELDS # Removed make_pending_setter

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

        self._reconnecting = False
        self._max_retries = 2
        self._retry_delay = 1
        self._operation_timeout = 30

        # Pending settings
        self._pending_settings: Dict[str, Any] = {}

        self._setting_handler = ChargeSettingHandler(self)

        # Explicitly define setter methods
        async def set_charge_start(self, value: Any) -> None:
            self._pending_settings["charge_start"] = value
        self.set_charge_start = set_charge_start.__get__(self, self.__class__)

        async def set_charge_end(self, value: Any) -> None:
            self._pending_settings["charge_end"] = value
        self.set_charge_end = set_charge_end.__get__(self, self.__class__)

        async def set_charge_day_mask(self, value: Any) -> None:
            self._pending_settings["charge_day_mask"] = value
        self.set_charge_day_mask = set_charge_day_mask.__get__(self, self.__class__)

        async def set_charge_power_percent(self, value: Any) -> None:
            self._pending_settings["charge_power_percent"] = value
        self.set_charge_power_percent = set_charge_power_percent.__get__(self, self.__class__)

        async def set_discharge_start(self, value: Any) -> None:
            self._pending_settings["discharge_start"] = value
        self.set_discharge_start = set_discharge_start.__get__(self, self.__class__)

        async def set_discharge_end(self, value: Any) -> None:
            self._pending_settings["discharge_end"] = value
        self.set_discharge_end = set_discharge_end.__get__(self, self.__class__)

        async def set_discharge_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge_day_mask"] = value
        self.set_discharge_day_mask = set_discharge_day_mask.__get__(self, self.__class__)

        async def set_discharge_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge_power_percent"] = value
        self.set_discharge_power_percent = set_discharge_power_percent.__get__(self, self.__class__)

        async def set_discharge2_start(self, value: Any) -> None:
            self._pending_settings["discharge2_start"] = value
        self.set_discharge2_start = set_discharge2_start.__get__(self, self.__class__)

        async def set_discharge2_end(self, value: Any) -> None:
            self._pending_settings["discharge2_end"] = value
        self.set_discharge2_end = set_discharge2_end.__get__(self, self.__class__)

        async def set_discharge2_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge2_day_mask"] = value
        self.set_discharge2_day_mask = set_discharge2_day_mask.__get__(self, self.__class__)

        async def set_discharge2_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge2_power_percent"] = value
        self.set_discharge2_power_percent = set_discharge2_power_percent.__get__(self, self.__class__)

        async def set_discharge3_start(self, value: Any) -> None:
            self._pending_settings["discharge3_start"] = value
        self.set_discharge3_start = set_discharge3_start.__get__(self, self.__class__)

        async def set_discharge3_end(self, value: Any) -> None:
            self._pending_settings["discharge3_end"] = value
        self.set_discharge3_end = set_discharge3_end.__get__(self, self.__class__)

        async def set_discharge3_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge3_day_mask"] = value
        self.set_discharge3_day_mask = set_discharge3_day_mask.__get__(self, self.__class__)

        async def set_discharge3_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge3_power_percent"] = value
        self.set_discharge3_power_percent = set_discharge3_power_percent.__get__(self, self.__class__)

        async def set_discharge4_start(self, value: Any) -> None:
            self._pending_settings["discharge4_start"] = value
        self.set_discharge4_start = set_discharge4_start.__get__(self, self.__class__)

        async def set_discharge4_end(self, value: Any) -> None:
            self._pending_settings["discharge4_end"] = value
        self.set_discharge4_end = set_discharge4_end.__get__(self, self.__class__)

        async def set_discharge4_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge4_day_mask"] = value
        self.set_discharge4_day_mask = set_discharge4_day_mask.__get__(self, self.__class__)

        async def set_discharge4_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge4_power_percent"] = value
        self.set_discharge4_power_percent = set_discharge4_power_percent.__get__(self, self.__class__)

        async def set_discharge5_start(self, value: Any) -> None:
            self._pending_settings["discharge5_start"] = value
        self.set_discharge5_start = set_discharge5_start.__get__(self, self.__class__)

        async def set_discharge5_end(self, value: Any) -> None:
            self._pending_settings["discharge5_end"] = value
        self.set_discharge5_end = set_discharge5_end.__get__(self, self.__class__)

        async def set_discharge5_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge5_day_mask"] = value
        self.set_discharge5_day_mask = set_discharge5_day_mask.__get__(self, self.__class__)

        async def set_discharge5_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge5_power_percent"] = value
        self.set_discharge5_power_percent = set_discharge5_power_percent.__get__(self, self.__class__)

        async def set_discharge6_start(self, value: Any) -> None:
            self._pending_settings["discharge6_start"] = value
        self.set_discharge6_start = set_discharge6_start.__get__(self, self.__class__)

        async def set_discharge6_end(self, value: Any) -> None:
            self._pending_settings["discharge6_end"] = value
        self.set_discharge6_end = set_discharge6_end.__get__(self, self.__class__)

        async def set_discharge6_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge6_day_mask"] = value
        self.set_discharge6_day_mask = set_discharge6_day_mask.__get__(self, self.__class__)

        async def set_discharge6_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge6_power_percent"] = value
        self.set_discharge6_power_percent = set_discharge6_power_percent.__get__(self, self.__class__)

        async def set_discharge7_start(self, value: Any) -> None:
            self._pending_settings["discharge7_start"] = value
        self.set_discharge7_start = set_discharge7_start.__get__(self, self.__class__)

        async def set_discharge7_end(self, value: Any) -> None:
            self._pending_settings["discharge7_end"] = value
        self.set_discharge7_end = set_discharge7_end.__get__(self, self.__class__)

        async def set_discharge7_day_mask(self, value: Any) -> None:
            self._pending_settings["discharge7_day_mask"] = value
        self.set_discharge7_day_mask = set_discharge7_day_mask.__get__(self, self.__class__)

        async def set_discharge7_power_percent(self, value: Any) -> None:
            self._pending_settings["discharge7_power_percent"] = value
        self.set_discharge7_power_percent = set_discharge7_power_percent.__get__(self, self.__class__)

        async def set_export_limit(self, value: Any) -> None:
            self._pending_settings["export_limit"] = value
        self.set_export_limit = set_export_limit.__get__(self, self.__class__)

        async def set_charging(self, value: Any) -> None:
            self._pending_settings["charging_state"] = value
        self.set_charging = set_charging.__get__(self, self.__class__)

        async def set_discharging(self, value: Any) -> None:
            self._pending_settings["discharging_state"] = value
        self.set_discharging = set_discharging.__get__(self, self.__class__)

        async def set_app_mode(self, value: Any) -> None:
            self._pending_settings["app_mode"] = value
        self.set_app_mode = set_app_mode.__get__(self, self.__class__)

        async def set_discharge_time_enable(self, value: Any) -> None:
            self._pending_settings["discharge_time_enable"] = value
        self.set_discharge_time_enable = set_discharge_time_enable.__get__(self, self.__class__)

        async def set_battery_on_grid_discharge_depth(self, value: Any) -> None:
            self._pending_settings["battery_on_grid_discharge_depth"] = value
        self.set_battery_on_grid_discharge_depth = set_battery_on_grid_discharge_depth.__get__(self, self.__class__)

        async def set_battery_off_grid_discharge_depth(self, value: Any) -> None:
            self._pending_settings["battery_off_grid_discharge_depth"] = value
        self.set_battery_off_grid_discharge_depth = set_battery_off_grid_discharge_depth.__get__(self, self.__class__)

        async def set_battery_capacity_charge_upper_limit(self, value: Any) -> None:
            self._pending_settings["battery_capacity_charge_upper_limit"] = value
        self.set_battery_capacity_charge_upper_limit = set_battery_capacity_charge_upper_limit.__get__(self, self.__class__)

        async def set_battery_charge_power_limit(self, value: Any) -> None:
            self._pending_settings["battery_charge_power_limit"] = value
        self.set_battery_charge_power_limit = set_battery_charge_power_limit.__get__(self, self.__class__)

        async def set_battery_discharge_power_limit(self, value: Any) -> None:
            self._pending_settings["battery_discharge_power_limit"] = value
        self.set_battery_discharge_power_limit = set_battery_discharge_power_limit.__get__(self, self.__class__)

        async def set_grid_max_charge_power(self, value: Any) -> None:
            self._pending_settings["grid_max_charge_power"] = value
        self.set_grid_max_charge_power = set_grid_max_charge_power.__get__(self, self.__class__)

        async def set_grid_max_discharge_power(self, value: Any) -> None:
            self._pending_settings["grid_max_discharge_power"] = value
        self.set_grid_max_discharge_power = set_grid_max_discharge_power.__get__(self, self.__class__)


    def get_pending_setting(self, key: str) -> Optional[Any]:
        """Get a pending setting value."""
        return self._pending_settings.get(key)

    def get_pending_settings(self, mode: str) -> Dict[str, Any]:
        """Get all pending settings for a given mode."""
        settings = {}
        for key, value in self._pending_settings.items():
            if key.startswith(mode):
                settings[key.replace(f"{mode}_", "")] = value
        return settings

    def reset_pending_setting(self, key: str) -> None:
        """Reset a pending setting."""
        self._pending_settings.pop(key, None)

    def reset_pending_settings(self, mode: str) -> None:
        """Reset all pending settings for a given mode."""
        keys_to_remove = [key for key in self._pending_settings if key.startswith(mode)]
        for key in keys_to_remove:
            self._pending_settings.pop(key)

    def _create_client(self) -> AsyncModbusTcpClient:
        client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=10,
        )
        _LOGGER.debug(f"Created new Modbus client: AsyncModbusTcpClient {self._host}:{self._port}")
        return client

    async def update_connection_settings(self, host: str, port: int, scan_interval: int) -> None:
        """Update connection settings from config entry options."""
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

                # Log the updated configuration
                _LOGGER.debug(
                    "Updated configuration - Host: %s, Port: %d, Scan Interval: %d",
                    self._host,
                    self._port,
                    scan_interval
                )
            except Exception as e:
                _LOGGER.error("Failed to update connection settings: %s", e)
                raise
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

                # Group pending settings to minimize Modbus accesses
                pending_settings = self._pending_settings.copy()
                self._pending_settings.clear()

                for key, value in pending_settings.items():
                    if key in ["charging_state", "discharging_state"]:
                        await self._setting_handler.handle_power_state_settings()
                    elif key == "discharge_time_enable":
                        await self.handle_discharge_time_enable()
                    else:
                        await self._setting_handler.handle_simple_register(key)

                combined_data: Dict[str, Any] = {}
                if not self.inverter_data:
                    self.inverter_data.update(
                        await modbus_readers.read_modbus_inverter_data(self._client, self._read_lock)
                    )
                combined_data.update(self.inverter_data)

                async def execute_reader_method(method):
                    """Helper function to execute a reader method with error handling."""
                    try:
                        result = await method(self._client, self._read_lock)
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
                    modbus_readers.read_inverter_phase_data,
                    modbus_readers.read_offgrid_output_data,
                    modbus_readers.read_side_net_data,
                    modbus_readers.read_charge_data,
                    modbus_readers.read_discharge_data,  # Reads all discharges at once
                    modbus_readers.read_anti_reflux_data,
                    modbus_readers.read_passive_battery_data,
                    modbus_readers.read_meter_a_data,
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

    async def _get_power_state(self, state_register: int, state_type: str) -> bool:
        try:
            # Read the state register
            state_regs = await self._read_registers(state_register)
            state_value = state_regs[0]
            
            # Read the App-Mode register (0x3647)
            app_mode_regs = await self._read_registers(0x3647)
            app_mode_value = app_mode_regs[0]
            
            # Return True if both conditions are met
            return state_value > 0 and app_mode_value == 1
        except Exception as e:
            _LOGGER.error(f"Error reading {state_type} state: {e}")
            return False
            
    async def get_charging_state(self) -> bool:
        return await self._get_power_state(0x3604, "Charging")

    async def get_discharging_state(self) -> bool:
        return await self._get_power_state(0x3605, "Discharging")

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

    async def handle_discharge_time_enable(self) -> None:
        """Handles the discharge time enable setting."""
        value = self._pending_discharge_time_enable
        if value is not None:
            success = await self._write_register(0x3605, value)
            if success:
                _LOGGER.info(f"Successfully set discharge time enable to: {value}")
            else:
                _LOGGER.error(f"Failed to write discharge time enable to register 0x3605")
            self._pending_discharge_time_enable = None
