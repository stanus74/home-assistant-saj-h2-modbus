"""SAJ Modbus Hub"""
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.payload import BinaryPayloadDecoder
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from voluptuous.validators import Number
from homeassistant.core import HomeAssistant, CALLBACK_TYPE, callback
from datetime import timedelta
from typing import Tuple, List, Optional
import logging
import asyncio
import random
from .const import DEVICE_STATUSSES, FAULT_MESSAGES

_LOGGER = logging.getLogger(__name__)

class SAJModbusHub(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int, scan_interval: int):
        super().__init__(hass, _LOGGER, name=name, update_interval=timedelta(seconds=scan_interval))
        self._host = host
        self._port = port
        self._client = ModbusTcpClient(host=host, port=port, timeout=7)
        self._lock = asyncio.Lock()
        self.inverter_data: dict = {}
        self.data: dict = {}
        self.last_valid_data = {}
        self._scan_interval = scan_interval
        _LOGGER.info(f"Initialized SAJModbusHub with scan interval: {scan_interval} seconds")

    async def _async_update_data(self) -> dict:
        """Fetch all required data sequentially with pauses."""
        _LOGGER.debug(f"Starting data update for {self.name}")
        start_time = asyncio.get_event_loop().time()

        data_tasks = [
            ("inverter_data", self.read_modbus_inverter_data),
            ("realtime_data", self.read_modbus_realtime_data),
            ("additional_data", self.read_additional_modbus_data_1),
            ("additional_data_2", self.read_additional_modbus_data_2),
            ("additional_data_3", self.read_additional_modbus_data_3)
        ]

        results = {}

        for key, task_function in data_tasks:
            try:
                results[key] = await task_function()
                _LOGGER.debug(f"Updated {key} for {self.name}")
            except ConnectionException as e:
                _LOGGER.error(f"Connection error during {key} data fetch: {e}")
                if key == "realtime_data":
                    results[key] = {"mpvmode": 0, "mpvstatus": DEVICE_STATUSSES[0], "power": 0}
                else:
                    results[key] = {}
            except Exception as e:
                _LOGGER.error(f"Unexpected error during {key} data fetch: {e}")
                results[key] = {}

            finally:
                # Ensure the connection is closed even in case of errors
                await self.close()

            # Wait 2 seconds before the next query
            await asyncio.sleep(2)

        # Update the inverter data
        self.inverter_data.update(results.get("inverter_data", {}))

        end_time = asyncio.get_event_loop().time()
        _LOGGER.debug(f"Completed data update for {self.name} in {end_time - start_time:.2f} seconds")

        return {**self.inverter_data, **results.get("realtime_data", {}), **results.get("additional_data", {}),
                **results.get("additional_data_2", {}), **results.get("additional_data_3", {})}

    # ... (rest of the methods remain unchanged)

    async def update_connection_settings(self, host: str, port: int, scan_interval: int):
        """Update connection settings and recreate the Modbus client if needed."""
        if self._host != host or self._port != port:
            _LOGGER.info(f"Updating Modbus client connection settings: host={host}, port={port}")
            async with self._lock:
                await self.hass.async_add_executor_job(self._client.close)
                self._client = ModbusTcpClient(host=host, port=port, timeout=7)
                self._host = host
                self._port = port

        # Update the scan interval
        self.update_interval = timedelta(seconds=scan_interval)
        self._scan_interval = scan_interval
        _LOGGER.info(f"Updated polling interval to {scan_interval} seconds.")
        
        # Force an immediate update
        await self.async_refresh()

    # ... (rest of the methods remain unchanged)