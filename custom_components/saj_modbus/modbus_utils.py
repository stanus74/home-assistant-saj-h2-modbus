import asyncio
import logging
from typing import List, Optional, TypeAlias
import inspect # Keep inspect for safe_close (though less critical now)

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

# --- Type Aliases --- (Optional, but can improve readability)
ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    """Special exception that signals that a reconnection is required."""
    pass

async def safe_close(client: Optional[ModbusClient]) -> None:
    """
    Safely attempts to close the Modbus connection.
    Logs warnings on failure but does not raise exceptions.
    """
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
            if inspect.iscoroutinefunction(close_method):
                await close_method()
                _LOGGER.debug("Async close method called.")
            else:
                close_method()
                _LOGGER.debug("Sync close method called.")
            # Removed explicit transport.close() - should be handled by client.close()
            # Removed asyncio.sleep() - unnecessary delay
            # Removed unreliable check of client.connected post-close
        else:
             _LOGGER.warning("Client object has no 'close' method.")

    except Exception as e:
        # Catching broadly as errors during close can be varied
        _LOGGER.warning(f"Error during safe close: {e}", exc_info=True)
        # Do not return True/False, just log the attempt/error

async def ensure_connection(
    client: ModbusClient,
    host: str,
    port: int,
    max_retries: int = 3,
    timeout_seconds: float = 10.0 # Parameterized timeout
) -> bool:
    """
    Ensures that the Modbus connection is established.

    Args:
        client: The Modbus client instance.
        host: The server host address.
        port: The server port.
        max_retries: Maximum number of connection attempts.
        timeout_seconds: Timeout for each connection attempt.

    Returns:
        True if connected, False otherwise.
    """
    if client and client.connected:
        return True

    if not client:
        _LOGGER.error("ensure_connection called with an invalid client instance.")
        return False

    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Connection attempt {attempt + 1}/{max_retries} to {host}:{port}")
            # Use parameterized timeout
            await asyncio.wait_for(client.connect(), timeout=timeout_seconds)

            if client.connected:
                _LOGGER.info(f"Successfully connected to Modbus server {host}:{port}.")
                return True
            else:
                # This case might occur if connect() returns without error but doesn't set connected flag
                _LOGGER.warning(f"Connection attempt {attempt + 1} to {host}:{port} finished, but client is not marked as connected.")
                # Wait before retrying even in this unusual case
                if attempt < max_retries - 1:
                    delay = 2 * (attempt + 1) # Exponential backoff
                    _LOGGER.info(f"Waiting {delay}s before connection retry {attempt + 2}/{max_retries}")
                    await asyncio.sleep(delay)

        except asyncio.TimeoutError:
             _LOGGER.warning(f"Connection attempt {attempt + 1} to {host}:{port} timed out after {timeout_seconds}s.")
             if attempt < max_retries - 1:
                 delay = 2 * (attempt + 1)
                 _LOGGER.info(f"Waiting {delay}s before connection retry {attempt + 2}/{max_retries}")
                 await asyncio.sleep(delay)
        except ConnectionRefusedError:
             _LOGGER.warning(f"Connection attempt {attempt + 1} to {host}:{port} refused.")
             if attempt < max_retries - 1:
                 delay = 2 * (attempt + 1)
                 _LOGGER.info(f"Waiting {delay}s before connection retry {attempt + 2}/{max_retries}")
                 await asyncio.sleep(delay)
        except Exception as e:
            # Catch other potential errors like OSError, etc.
            _LOGGER.warning(f"Error during connection attempt {attempt + 1} to {host}:{port}: {e}", exc_info=True)
            if attempt < max_retries - 1:
                delay = 2 * (attempt + 1)
                _LOGGER.info(f"Waiting {delay}s before connection retry {attempt + 2}/{max_retries}")
                await asyncio.sleep(delay)

    _LOGGER.error(f"Failed to connect to Modbus server {host}:{port} after {max_retries} attempts.")
    return False

async def close_connection( # Renamed from 'close' to be more descriptive
    client: Optional[ModbusClient],
    timeout_seconds: float = 5.0 # Parameterized timeout
) -> None:
    """
    Closes the Modbus connection with a timeout.

    Args:
        client: The Modbus client instance.
        timeout_seconds: Maximum time to wait for close operation.
    """
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
        # Catch potential errors raised by safe_close itself, although it aims not to.
        _LOGGER.warning(f"Error during close_connection: {e}", exc_info=True)


async def try_read_registers(
    client: ModbusClient,
    read_lock: Lock,
    unit: int, # Keep unit as it's needed by read_holding_registers
    address: int,
    count: int,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 10.0 # Add max delay cap parameter
) -> List[int]:
    """
    Reads Modbus holding registers with retries, locking, and detailed error handling.

    Args:
        client: The connected Modbus client instance.
        read_lock: An asyncio.Lock to serialize read operations if needed.
        unit: The Modbus unit/slave ID.
        address: The starting register address.
        count: The number of registers to read.
        max_retries: Maximum number of read attempts.
        base_delay: Initial delay in seconds for retries.
        max_delay: Maximum delay in seconds between retries.

    Returns:
        A list of register values (integers).

    Raises:
        ReconnectionNeededError: If the client is not connected initially or if all read attempts fail.
        ModbusIOException: For certain communication errors not handled by retries.
    """
    # --- Initial Connection Check ---
    if not client or not client.connected:
        _LOGGER.error(f"Read failed: Client not connected before attempting to read {count} registers from address {address}, unit {unit}.")
        raise ReconnectionNeededError("Client not connected, reconnection needed before reading")

    # --- Retry Loop ---
    last_exception: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Read attempt {attempt + 1}/{max_retries}: Reading {count} registers from address {address}, unit {unit}")

            # --- Acquire Lock and Read ---
            async with read_lock:
                # Pass unit/slave parameter
                response = await client.read_holding_registers(address=address, count=count, slave=unit)

            # --- Validate Response ---
            if not response:
                # This case might happen for timeouts handled within pymodbus differently
                _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: No response object received.")
                # Treat as a failure for retry logic
                last_exception = ModbusIOException("No response received")
            elif response.isError():
                # Specific Modbus exception response
                error_msg = getattr(response, 'message', str(response)) # Try to get specific message
                _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Modbus Error Response: {error_msg}")
                # Store exception info for potential re-raise later
                last_exception = ModbusIOException(f"Modbus Error Response: {error_msg}")
            elif not hasattr(response, 'registers') or response.registers is None:
                 _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Response object invalid (no 'registers' attribute or None).")
                 last_exception = ModbusIOException("Invalid response object received")
            elif len(response.registers) != count:
                # Received data, but not the expected amount
                _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Incomplete response: expected {count} registers, got {len(response.registers)}")
                last_exception = ModbusIOException(f"Incomplete response: expected {count}, got {len(response.registers)}")
            else:
                # --- Success ---
                _LOGGER.debug(f"Read attempt {attempt + 1} successful for address {address}, unit {unit}.")
                return response.registers

        # --- Handle Exceptions During Read/Lock ---
        except ConnectionException as e:
            _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Connection error: {e}")
            last_exception = e # Store for potential final raise
        except ModbusIOException as e:
            _LOGGER.warning(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Modbus IO error: {e}")
            last_exception = e
        except Exception as e:
            # Catch other potential errors (e.g., issues with the lock, unexpected client errors)
            _LOGGER.error(f"Read attempt {attempt + 1} for address {address}, unit {unit}: Unexpected error: {e}", exc_info=True)
            last_exception = e

        # --- Wait Before Retry (if not the last attempt) ---
        if attempt < max_retries - 1:
            delay = min(base_delay * (2 ** attempt), max_delay) # Exponential backoff with cap
            _LOGGER.info(f"Read failed on attempt {attempt + 1}/{max_retries}. Waiting {delay:.1f}s before retry {attempt + 2}/{max_retries} for address {address}, unit {unit}")
            await asyncio.sleep(delay)
        else:
            # --- All Retries Failed ---
            _LOGGER.error(f"All {max_retries} read attempts failed for address {address}, unit {unit}. Last error: {last_exception}")
            # Raise ReconnectionNeededError to signal upstream that communication is likely broken
            raise ReconnectionNeededError(f"Reconnection needed after {max_retries} failed read attempts at address {address}, unit {unit}. Last error: {last_exception}") from last_exception

    # --- Should Not Be Reached ---
    # This path implies the loop finished without returning or raising, which shouldn't happen.
    assert False, f"Unexpected code path reached in try_read_registers for address {address}, unit {unit}"

