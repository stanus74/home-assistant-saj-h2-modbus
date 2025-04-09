import asyncio
import logging
from typing import List

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
        close_method = getattr(client, "close", None)
        if client.connected and callable(close_method):
            if asyncio.iscoroutinefunction(close_method):
                await close_method()
            else:
                close_method()

        transport = getattr(client, "transport", None)
        if transport and hasattr(transport, "is_closing") and not transport.is_closing():
            transport.close()

        await asyncio.sleep(0.2)
        return not client.connected
    except Exception as e:
        _LOGGER.warning(f"Error during safe close: {type(e).__name__}: {e}", exc_info=True)
        return False

async def ensure_connection(client: AsyncModbusTcpClient, host: str, port: int, max_retries: int = 3) -> bool:
    """Ensures that the Modbus connection is established and stable."""
    if client and client.connected and getattr(client, "transport", None):
        return True

    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Connection attempt {attempt + 1}/{max_retries} to {host}:{port}")
            await asyncio.wait_for(client.connect(), timeout=10)
            if client.connected:
                _LOGGER.info("Successfully connected to Modbus server.")
                return True
            else:
                _LOGGER.warning("Client not connected after connect attempt.")
        except Exception as e:
            _LOGGER.warning(f"Error during connection attempt {attempt + 1}: {type(e).__name__}: {e}", exc_info=True)

        if attempt < max_retries - 1:
            await asyncio.sleep(min(2 * (attempt + 1), 10.0))

    return False

async def close(client: AsyncModbusTcpClient) -> None:
    """Closes the Modbus connection with improved resource management."""
    try:
        async with asyncio.timeout(5.0):
            await safe_close(client)
    except Exception as e:
        _LOGGER.warning(f"Error during close: {type(e).__name__}: {e}", exc_info=True)


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
    # Überprüfe zuerst, ob der Client verbunden ist
    if not client or not client.connected:
        _LOGGER.error(f"Client not connected before attempting to read registers from address {address}")
        raise ReconnectionNeededError("Client not connected, reconnection needed before reading")
    
    for attempt in range(max_retries):
        try:
            _LOGGER.debug(f"Reading registers attempt {attempt + 1}/{max_retries} from address {address}, count {count}")
            
            async with read_lock:
                response = await client.read_holding_registers(address=address, count=count)
            
            # Überprüfe die Antwort auf Fehler
            if not response:
                _LOGGER.error(f"No response received from address {address}")
            elif response.isError():
                error_msg = getattr(response, 'message', str(response))
                _LOGGER.error(f"Error response from address {address}: {error_msg}")
            elif len(response.registers) != count:
                _LOGGER.error(f"Incomplete response from address {address}: expected {count} registers, got {len(response.registers)}")
            else:
                # Erfolgreiche Antwort
                return response.registers
            
        except ConnectionException as e:
            _LOGGER.error(f"Connection error during read attempt {attempt + 1} at address {address}: {e}")
        except ModbusIOException as e:
            _LOGGER.error(f"Modbus IO error during read attempt {attempt + 1} at address {address}: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error during read attempt {attempt + 1} at address {address}: {e}")
        
        # Wenn wir hier ankommen, ist der Versuch fehlgeschlagen
        if attempt < max_retries - 1:
            # Warte vor dem nächsten Versuch
            delay = min(base_delay * (2 ** attempt), 10.0)
            _LOGGER.info(f"Waiting {delay:.1f}s before retry {attempt + 2}/{max_retries}")
            await asyncio.sleep(delay)
        else:
            # Letzter Versuch fehlgeschlagen, fordere eine Neuverbindung an
            _LOGGER.warning(f"All {max_retries} read attempts failed for address {address}, requesting reconnection")
            raise ReconnectionNeededError(f"Reconnection needed after {max_retries} failed read attempts at address {address}")
    
    # Dieser Code sollte nie erreicht werden, da wir entweder Register zurückgeben oder eine Exception werfen
    _LOGGER.error(f"Unexpected code path in try_read_registers for address {address}")
    raise ConnectionException(f"Unexpected error reading from address {address}")
