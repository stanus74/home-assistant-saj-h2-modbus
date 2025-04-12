import asyncio
import logging
from typing import List, Optional, TypeAlias
import inspect

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

# --- Type Aliases ---
ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    """Special exception that signals that a reconnection is required."""
    pass

# --- Utility Functions ---

def _validate_response(response, address: int, unit: int, count: int) -> Optional[Exception]:
    if not response:
        return ModbusIOException("No response received")
    if response.isError():
        msg = getattr(response, 'message', str(response))
        return ModbusIOException(f"Modbus Error Response: {msg}")
    if not hasattr(response, 'registers') or response.registers is None:
        return ModbusIOException("Invalid response object received")
    if len(response.registers) != count:
        return ModbusIOException(f"Incomplete response: expected {count}, got {len(response.registers)}")
    return None

async def _delay_retry(attempt: int, max_retries: int, factor: float = 2.0, cap: float = 10.0):
    if attempt < max_retries - 1:
        delay = min(factor * (attempt + 1), cap)
        _LOGGER.info(f"Waiting {delay:.1f}s before retry {attempt + 2}/{max_retries}")
        await asyncio.sleep(delay)

# --- Core Functions ---

async def safe_close(client: Optional[ModbusClient]) -> None:
    if not client:
        _LOGGER.debug("safe_close called with no client instance.")
        return

    if not client.connected:
        _LOGGER.debug("safe_close called but client was not connected.")
        return

    try:
        _LOGGER.debug("Attempting to safely close Modbus connection.")
        close_method = getattr(client, "close", None)
        if close_method:
            await close_method() if inspect.iscoroutinefunction(close_method) else close_method()
            _LOGGER.debug("Close method called.")
        else:
            _LOGGER.warning("Client object has no 'close' method.")
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)

async def ensure_connection(
    client: ModbusClient,
    host: str,
    port: int,
    max_retries: int = 3,
    timeout_seconds: float = 10.0
) -> bool:
    if client and client.connected:
        return True

    if not client:
        _LOGGER.error("ensure_connection called with an invalid client instance.")
        return False

    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Connection attempt {attempt + 1}/{max_retries} to {host}:{port}")
            await asyncio.wait_for(client.connect(), timeout=timeout_seconds)

            if client.connected:
                _LOGGER.info(f"Successfully connected to Modbus server {host}:{port}.")
                return True
            else:
                _LOGGER.warning(f"Connect attempt {attempt + 1} finished, but client is not marked as connected.")
        except (asyncio.TimeoutError, ConnectionRefusedError, Exception) as e:
            _LOGGER.warning(f"Error during connection attempt {attempt + 1} to {host}:{port}: {e}", exc_info=True)

        await _delay_retry(attempt, max_retries)

    _LOGGER.error(f"Failed to connect to Modbus server {host}:{port} after {max_retries} attempts.")
    return False

async def close_connection(
    client: Optional[ModbusClient],
    timeout_seconds: float = 5.0
) -> None:
    if not client:
        _LOGGER.debug("close_connection called with no client instance.")
        return

    try:
        _LOGGER.debug(f"Closing connection with {timeout_seconds}s timeout.")
        async with asyncio.timeout(timeout_seconds):
            await safe_close(client)
        _LOGGER.debug("Connection close process finished.")
    except asyncio.TimeoutError:
        _LOGGER.warning(f"Closing connection timed out after {timeout_seconds}s.")
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
    max_delay: float = 10.0
) -> List[int]:
    if not client or not client.connected:
        _LOGGER.error(f"Read failed: Client not connected before attempting to read {count} registers from address {address}, unit {unit}.")
        raise ReconnectionNeededError("Client not connected, reconnection needed before reading")

    last_exception: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Read attempt {attempt + 1}/{max_retries}: Reading {count} registers from address {address}, unit {unit}")
            async with read_lock:
                response = await client.read_holding_registers(address=address, count=count, slave=unit)

            err = _validate_response(response, address, unit, count)
            if err:
                _LOGGER.warning(f"Read attempt {attempt + 1} failed: {err}")
                last_exception = err
            else:
                _LOGGER.debug(f"Read attempt {attempt + 1} successful for address {address}, unit {unit}.")
                return response.registers

        except (ConnectionException, ModbusIOException, Exception) as e:
            _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: {type(e).__name__}: {e}", exc_info=True)
            last_exception = e

        await _delay_retry(attempt, max_retries, base_delay, max_delay)

    _LOGGER.error(f"All {max_retries} read attempts failed for address {address}, unit {unit}. Last error: {last_exception}")
    raise ReconnectionNeededError(f"Reconnection needed after {max_retries} failed read attempts at address {address}, unit {unit}. Last error: {last_exception}") from last_exception