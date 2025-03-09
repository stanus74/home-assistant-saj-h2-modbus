import asyncio
import logging
from typing import List, Optional
import inspect
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    """Special exception that signals that a reconnection is required."""
    pass

async def safe_close(client: AsyncModbusTcpClient) -> bool:
    """Safely closes the Modbus connection."""
    if not client:
        return True

    try:
        if client.connected:
            close_method = getattr(client, "close", None)
            if close_method:
                if inspect.iscoroutinefunction(close_method):
                    await close_method()
                else:
                    close_method()
            transport = getattr(client, "transport", None)
            if transport:
                transport.close()
            await asyncio.sleep(0.2)
            # Optional: Check status again
            return not client.connected
        return True
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)
        return False

async def ensure_connection(client: AsyncModbusTcpClient, host: str, port: int) -> bool:
    """Ensures that the Modbus connection is established and stable."""
    if client and client.connected:
        return True

    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        if client.connected:
            _LOGGER.info("Successfully connected to Modbus server.")
            return True
        else:
            _LOGGER.warning("Client not connected after connect attempt.")
            return False
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
                # Instead of creating a new client here, an exception is thrown
                # that can be caught in the hub and the reconnection logic can be centrally controlled.
                raise ReconnectionNeededError("Reconnection needed due to read failure.")
    _LOGGER.error(f"Failed to read registers from unit {unit}, address {address} after {max_retries} attempts")
    raise ConnectionException(f"Read operation failed for address {address} after {max_retries} attempts")
