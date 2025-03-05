import asyncio
import logging
from typing import List, Optional
import inspect
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException


_LOGGER = logging.getLogger(__name__)



async def try_read_registers(
    client: AsyncModbusTcpClient,
    read_lock: asyncio.Lock,
    unit: int,
    address: int,
    count: int,
    max_retries: int = 3,
    base_delay: float = 2.0
) -> List[int]:
    """Reads Modbus registers with optimized error handling."""
    for attempt in range(max_retries):
        try:
            async with read_lock:
                response = await client.read_holding_registers(address=address, count=count)
            
            if (not response) or response.isError() or len(response.registers) != count:
                raise ModbusIOException(f"Invalid response from address {address}")
                
            return response.registers
            
        except (ModbusIOException, ConnectionException) as e:
            _LOGGER.error(f"Read attempt {attempt + 1} failed at address {address}: {e}")
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), 10.0)
                await asyncio.sleep(delay)
                if not await safe_close(client):
                    _LOGGER.warning("Failed to safely close the Modbus client.")
                try:
                    client = AsyncModbusTcpClient(host=client.host, port=client.port, timeout=10)
                    await ensure_connection(client, client.host, client.port)
                except ConnectionException:
                    _LOGGER.error("Failed to reconnect Modbus client.")
                    continue
                else:
                    _LOGGER.info("Reconnected Modbus client successfully.")
    _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
    raise ConnectionException(f"Read operation failed for address {address} after {max_retries} attempts")