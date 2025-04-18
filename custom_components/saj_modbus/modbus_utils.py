import asyncio
import logging
from typing import List, Optional, TypeAlias
import inspect

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    pass

async def safe_close(client: Optional[ModbusClient]) -> None:
    if not client:
        return
    try:
        close = getattr(client, "close", None)
        if close:
            await close() if inspect.iscoroutinefunction(close) else close()
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)

async def ensure_connection(client: ModbusClient, host: str, port: int, max_retries: int = 3, timeout_seconds: float = 10.0) -> bool:
    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Connecting to {host}:{port}, attempt {attempt + 1}/{max_retries}")
            await asyncio.wait_for(client.connect(), timeout=timeout_seconds)
            if client.connected:
                return True
        except Exception as e:
            _LOGGER.warning(f"Connection error on attempt {attempt + 1}: {e}")
        await asyncio.sleep(2)
    return False

async def close_connection(client: Optional[ModbusClient], timeout_seconds: float = 5.0) -> None:
    if not client:
        return
    try:
        async with asyncio.timeout(timeout_seconds):
            await safe_close(client)
    except asyncio.TimeoutError:
        _LOGGER.warning(f"Closing connection timed out after {timeout_seconds}s")
    except Exception as e:
        _LOGGER.warning(f"Error during close_connection: {e}", exc_info=True)

async def try_read_registers(
    client: ModbusClient,
    read_lock: Lock,
    unit: int,
    address: int,
    count: int,
    max_retries: int = 3,
    base_delay: float = 2.0,
    host: Optional[str] = None,
    port: Optional[int] = None
) -> List[int]:
    last_exception: Optional[Exception] = None

    if not client or not client.connected:
        _LOGGER.error(f"Read failed: Client not connected before attempting to read {count} registers from address {address}, unit {unit}.")
        raise ReconnectionNeededError("Client not connected, reconnection needed before reading")

    for attempt in range(max_retries):
        try:
            async with read_lock:
                coro = client.read_holding_registers(address=address, count=count, slave=unit)
            resp = await coro
            if resp and not resp.isError() and hasattr(resp, 'registers') and resp.registers:
                return resp.registers
            else:
                last_exception = ModbusIOException("Invalid or error response")
        except (ConnectionException, ModbusIOException, Exception) as e:
            _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: {type(e).__name__}: {e}", exc_info=True)
            last_exception = e

            if isinstance(e, ConnectionException) and host and port:
                _LOGGER.info("Attempting reconnect due to connection loss...")
                connected = await ensure_connection(client, host, port)
                if not connected:
                    _LOGGER.error("Reconnect failed")
                    raise ReconnectionNeededError("Reconnect failed") from e

        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), 10.0)
            _LOGGER.info(f"Waiting {delay:.1f}s before retry {attempt + 2}/{max_retries} for address {address}, unit {unit}")
            await asyncio.sleep(delay)

    _LOGGER.error(f"All {max_retries} read attempts failed for address {address}, unit {unit}. Last error: {last_exception}")
    raise ReconnectionNeededError(f"Reconnection needed after {max_retries} failed read attempts at address {address}, unit {unit}. Last error: {last_exception}")
