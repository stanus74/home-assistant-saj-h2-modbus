import asyncio
import logging
from typing import List, Optional
import inspect
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException


_LOGGER = logging.getLogger(__name__)


async def safe_close(client: AsyncModbusTcpClient) -> bool:
    """Safely closes the Modbus connection."""
    if not client:
        return True

    try:
        if client.connected:
            close = getattr(client, "close", None)
            if close:
                await close() if inspect.iscoroutinefunction(close) else close()
            transport = getattr(client, "transport", None)
            if transport:
                transport.close()
            await asyncio.sleep(0.2)
            return not client.connected
        return True
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)
        return False


async def ensure_connection(client: AsyncModbusTcpClient, host: str, port: int) -> bool:
    """Ensure the Modbus connection is established and stable."""
    if client and client.connected:
        return True

    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        _LOGGER.info("Successfully connected to Modbus server.")
        return True
    except Exception as e:
        _LOGGER.warning(f"Error during connection attempt: {e}", exc_info=True)
        return False


async def close(client: AsyncModbusTcpClient) -> None:
    """Closes the Modbus connection with improved resource management."""
    try:
        async with asyncio.timeout(5.0):
            await safe_close(client)
    except (asyncio.TimeoutError, Exception) as e:
        _LOGGER.warning(f"Error during close: {e}", exc_info=True)



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
