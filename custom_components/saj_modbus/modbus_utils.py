import asyncio
import logging
from typing import List, Optional
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

_LOGGER = logging.getLogger(__name__)

async def safe_close(client: Optional[AsyncModbusTcpClient]) -> bool:
    """Safely close Modbus connection."""
    if not client or not client.connected: return True
    try:
        if close := getattr(client, "close", None):
            await close() if asyncio.iscoroutinefunction(close) else close()
        if transport := getattr(client, "transport", None): transport.close()
        await asyncio.sleep(0.2)
        return not client.connected
    except Exception as e:
        _LOGGER.warning(f"Error closing: {e}", exc_info=True)
        return False
    finally:
        client = None

async def close(client: Optional[AsyncModbusTcpClient], closing_flag: bool, connection_lock: asyncio.Lock) -> None:
    """Close Modbus connection with resource management."""
    if closing_flag: return
    closing_flag = True
    try:
        async with asyncio.timeout(5), connection_lock:
            await safe_close(client)
    except (asyncio.TimeoutError, Exception) as e:
        _LOGGER.warning(f"Error during close: {e}", exc_info=True)
    finally:
        closing_flag = False

async def ensure_connection(client: Optional[AsyncModbusTcpClient], host: str, port: int) -> AsyncModbusTcpClient:
    """Ensure stable Modbus connection."""
    if client and client.connected: return client
    client = client or AsyncModbusTcpClient(host=host, port=port, timeout=10)
    try:
        await asyncio.wait_for(client.connect(), timeout=10)
        _LOGGER.info("Connected to Modbus server.")
        return client
    except Exception as e:
        _LOGGER.warning(f"Connection failed: {e}", exc_info=True)
        raise ConnectionException("Failed to connect.") from e

async def try_read_registers(client: AsyncModbusTcpClient, read_lock: asyncio.Lock, unit: int, address: int, count: int, 
                             max_retries: int = 3, base_delay: float = 2.0) -> List[int]:
    """Read Modbus registers with error handling."""
    for attempt in range(max_retries):
        try:
            async with read_lock:
                response = await client.read_holding_registers(address=address, count=count)
            if not response or response.isError() or len(response.registers) != count:
                raise ModbusIOException(f"Invalid response from {address}")
            return response.registers
        except (ModbusIOException, ConnectionException) as e:
            _LOGGER.error(f"Attempt {attempt + 1} failed at {address}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(min(base_delay * (2 ** attempt), 10.0))
                if not await safe_close(client):
                    _LOGGER.warning("Failed to close client.")
                try:
                    client = AsyncModbusTcpClient(host=client.host, port=client.port, timeout=10)
                    await ensure_connection(client, client.host, client.port)
                    _LOGGER.info("Reconnected client.")
                except ConnectionException:
                    _LOGGER.error("Reconnect failed.")
                    continue
    _LOGGER.error(f"Failed to read from unit {unit}, address {address} after {max_retries} attempts")
    raise ConnectionException(f"Read failed for {address} after {max_retries} attempts")