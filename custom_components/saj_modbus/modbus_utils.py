import asyncio
import logging
import inspect
from typing import List, Optional, TypeAlias, Union

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    """Indicates that a reconnect is needed due to communication failure."""
    pass

async def safe_close(client: Optional[ModbusClient]) -> None:
    """
    Safely close the Modbus client, suppressing exceptions.
    """
    if not client:
        return
    try:
        close = getattr(client, "close", None)
        if close:
            if inspect.iscoroutinefunction(close):
                await close()
            else:
                close()
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)

async def ensure_connection(
    client: ModbusClient,
    host: str,
    port: int,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
) -> bool:
    """
    Ensure the client is connected, retrying on failure.
    """
    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Connecting to {host}:{port}, attempt {attempt+1}/{max_retries}")
            await asyncio.wait_for(client.connect(), timeout=timeout_seconds)
            if client.connected:
                return True
        except Exception as e:
            _LOGGER.warning(f"Connection error on attempt {attempt+1}: {e}")
        await asyncio.sleep(2)
    return False

async def close_connection(
    client: Optional[ModbusClient],
    timeout_seconds: float = 5.0,
) -> None:
    """
    Close the client with a timeout.
    """
    if not client:
        return
    try:
        async with asyncio.timeout(timeout_seconds):
            await safe_close(client)
    except asyncio.TimeoutError:
        _LOGGER.warning(f"Closing connection timed out after {timeout_seconds}s")
    except Exception as e:
        _LOGGER.warning(f"Error during close_connection: {e}", exc_info=True)

# ==========================
# Centralized Read/Write
# ==========================

async def try_read_registers(
    client: ModbusClient,
    lock: Lock,
    unit: int,
    address: int,
    count: int,
    max_retries: int = 3,
    base_delay: float = 2.0,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> List[int]:
    """
    Read holding registers with retry logic, serializing via lock.
    """
    last_exception: Optional[Exception] = None

    if not client or not client.connected:
        _LOGGER.error(
            f"Read failed: Client not connected before attempting to read {count} registers "
            f"from address {address}, unit {unit}."
        )
        raise ReconnectionNeededError("Client not connected, reconnection needed before reading")

    for attempt in range(max_retries):
        try:
            async with lock:
                resp = await client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=unit,
                )
            if resp and not resp.isError() and hasattr(resp, 'registers'):
                return resp.registers  # type: ignore
            last_exception = ModbusIOException("Invalid or error response")
        except (ConnectionException, ModbusIOException, Exception) as e:
            _LOGGER.warning(
                f"Read attempt {attempt+1} for address {address}, unit {unit}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            last_exception = e
            if isinstance(e, ConnectionException) and host and port:
                _LOGGER.info("Attempting reconnect due to connection loss...")
                if not await ensure_connection(client, host, port):
                    _LOGGER.error("Reconnect failed")
                    raise ReconnectionNeededError("Reconnect failed") from e
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), 10.0)
            _LOGGER.info(
                f"Waiting {delay:.1f}s before retry {attempt+2}/{max_retries} "
                f"for address {address}, unit {unit}"
            )
            await asyncio.sleep(delay)

    _LOGGER.error(
        f"All {max_retries} read attempts failed for address {address}, unit {unit}. "
        f"Last error: {last_exception}"
    )
    raise ReconnectionNeededError(
        f"Reconnection needed after {max_retries} failed read attempts at address {address}, unit {unit}. "
        f"Last error: {last_exception}"
    )

async def try_write_registers(
    client: ModbusClient,
    lock: Lock,
    unit: int,
    address: int,
    values: Union[int, List[int]],
    max_retries: int = 2,
    base_delay: float = 1.0,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> bool:
    """
    Write single or multiple registers with retry logic, serializing via lock.
    """
    last_exception: Optional[Exception] = None
    if not client or not client.connected:
        _LOGGER.error(
            f"Write failed: Client not connected before attempting to write to address {address}, unit {unit}."
        )
        raise ReconnectionNeededError("Client not connected, reconnection needed before writing")

    is_single = isinstance(values, int)
    for attempt in range(max_retries):
        try:
            async with lock:
                if is_single:
                    resp = await client.write_register(
                        address=address,
                        value=values,  # type: ignore
                        slave=unit,
                    )
                else:
                    resp = await client.write_registers(
                        address=address,
                        values=values,  # type: ignore
                        slave=unit,
                    )
            if resp and not resp.isError():
                _LOGGER.debug(
                    f"Successfully wrote {'value' if is_single else 'values'} to address {address}, unit {unit}"
                )
                return True
            last_exception = ModbusIOException(f"Invalid or error response: {resp}")
        except (ConnectionException, ModbusIOException, Exception) as e:
            _LOGGER.warning(
                f"Write attempt {attempt+1} for address {address}, unit {unit}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            last_exception = e
            if isinstance(e, ConnectionException) and host and port:
                _LOGGER.info("Attempting reconnect due to connection loss...")
                if not await ensure_connection(client, host, port):
                    _LOGGER.error("Reconnect failed")
                    raise ReconnectionNeededError("Reconnect failed") from e
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), 5.0)
            _LOGGER.info(
                f"Waiting {delay:.1f}s before retry {attempt+2}/{max_retries} "
                f"for writing to address {address}, unit {unit}"
            )
            await asyncio.sleep(delay)

    _LOGGER.error(
        f"All {max_retries} write attempts failed for address {address}, unit {unit}. "
        f"Last error: {last_exception}"
    )
    return False
