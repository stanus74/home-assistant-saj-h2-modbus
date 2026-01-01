import asyncio
import functools
import logging
import os
import time
from typing import Any, Awaitable, Callable, List, Optional, Union

from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.client import ModbusTcpClient

# We use ModbusTcpClient explicitly, so we don't import the generic ModbusClient alias
from .const import Lock

_LOGGER = logging.getLogger(__name__)

# Set to True to enable detailed Modbus read attempt logging, False to disable
# Entweder hier per DEBUG_READ_DEFAULT auf True setzen oder per Env `SAJ_DEBUG_MODBUS_READ=1`
DEBUG_READ_DEFAULT = False
ENABLE_DETAILED_MODBUS_READ_LOGGING = (
    os.getenv("SAJ_DEBUG_MODBUS_READ", "0") == "1" or DEBUG_READ_DEFAULT
)

# Toggle für detailliertes Write-Logging
# Entweder hier direkt auf True setzen oder per Env `SAJ_DEBUG_MODBUS_WRITE=1`
DEBUG_WRITE_DEFAULT = False
ENABLE_DETAILED_MODBUS_WRITE_LOGGING = (
    os.getenv("SAJ_DEBUG_MODBUS_WRITE", "0") == "1" or DEBUG_WRITE_DEFAULT
)

class ReconnectionNeededError(Exception):
    """Indicates that a reconnect is needed due to communication failure."""
    pass

# Global Modbus config storage
class ModbusGlobalConfig:
    host: Optional[str] = None
    port: Optional[int] = None
    hass: Optional[Any] = None

def set_modbus_config(host: str, port: int, hass: Any = None) -> None:
    ModbusGlobalConfig.host = host
    ModbusGlobalConfig.port = port
    ModbusGlobalConfig.hass = hass
    _LOGGER.debug("Global Modbus config set: %s:%s (hass configured: %s)", host, port, hass is not None)

# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

# OPTIMIZATION: Combined ensure_client_connected() and connect_if_needed()
# into a single _connect_client() function to reduce code duplication.
# The original functions are kept as backward compatibility wrappers.

async def _connect_client(
    client: ModbusTcpClient,
    host: str,
    port: int,
    logger: logging.Logger,
    create_new: bool = False
) -> ModbusTcpClient:
    """
    Ensures the Modbus client is connected.
    
    This is a unified function that handles both:
    - Creating new clients when needed (if create_new=True)
    - Connecting existing clients if not already connected
    
    Args:
        client: The Modbus client to connect (or None if create_new is True)
        host: The host to connect to
        port: The port to connect to
        logger: Logger instance for logging
        create_new: If True, creates a new client when client is None
    
    Returns:
        The connected Modbus client
    
    Raises:
        ConnectionError: If connection fails
        ValueError: If client is None and create_new is False
    """
    # Create new client if needed and requested
    if client is None:
        if not create_new:
            raise ValueError("Client is None and create_new is False")
        logger.debug("Creating new ModbusTcpClient for %s:%s", host, port)
        client = ModbusTcpClient(host=host, port=port, timeout=10)
    
    # Connect if not already connected
    if not client.connected:
        logger.debug("Attempting to connect ModbusTcpClient to %s:%s", host, port)
        try:
            if ModbusGlobalConfig.hass:
                await ModbusGlobalConfig.hass.async_add_executor_job(client.connect)
            else:
                client.connect()
                
            # Verify that the client is actually connected after the connection attempt
            if not client.connected:
                raise ConnectionError("Client failed to connect to %s:%s" % (host, port))
            logger.info("ModbusTcpClient successfully connected to %s:%s", host, port)
        except Exception as e:
            logger.error("Error connecting client to %s:%s: %s", host, port, e)
            raise ConnectionError("Failed to connect to %s:%s due to %s" % (host, port, e)) from e
    
    
    return client


# ============================================================================
# CONNECTION POOLING OPTIMIZATION
# ============================================================================

class ConnectionCache:
    """
    Caches Modbus client connections to reduce connection overhead.
    
    PERFORMANCE OPTIMIZATION: Reduces redundant connection checks and
    reconnection attempts by caching the client for a configurable TTL.
    """
    
    def __init__(self, cache_ttl: float = 60.0):
        """
        Initialize connection cache.
        
        Args:
            cache_ttl: Time to live for cached connections in seconds
        """
        self._cached_client: Optional[ModbusTcpClient] = None
        self._cache_expiry: float = 0.0
        self._cache_ttl: float = cache_ttl
        self._last_health_check: float = 0.0
        self._health_check_interval: float = 30.0  # Check health every 30s
        self._connection_healthy: bool = True
    
    def get_cached_client(self) -> Optional[ModbusTcpClient]:
        """
        Get cached client if still valid.
        
        PERFORMANCE OPTIMIZATION: Returns cached client without lock acquisition
        if it's still valid and healthy.
        
        Returns:
            Cached client if valid, None otherwise
        """
        now = time.monotonic()
        
        # Check if cache is still valid
        if self._cached_client is not None and now < self._cache_expiry:
            # Check if connection is healthy
            if self._is_connection_healthy(now):
                return self._cached_client
            else:
                # Connection not healthy, invalidate cache
                self._cached_client = None
                return None
        
        return None
    
    def set_cached_client(self, client: ModbusTcpClient) -> None:
        """
        Set cached client with TTL.
        
        Args:
            client: The client to cache
        """
        self._cached_client = client
        self._cache_expiry = time.monotonic() + self._cache_ttl
        self._connection_healthy = True
        self._last_health_check = time.monotonic()
    
    def invalidate(self) -> None:
        """Invalidate the cached connection."""
        self._cached_client = None
        self._cache_expiry = 0.0
    
    def _is_connection_healthy(self, now: float) -> bool:
        """
        Check if connection is healthy without full reconnect.
        
        PERFORMANCE OPTIMIZATION: Only checks connection health periodically
        to reduce overhead.
        
        Args:
            now: Current monotonic time
            
        Returns:
            True if connection is healthy, False otherwise
        """
        # Only check health periodically
        if now - self._last_health_check < self._health_check_interval:
            return self._connection_healthy
        
        self._last_health_check = now
        
        if self._cached_client and self._cached_client.connected:
            self._connection_healthy = True
            return True
        
        self._connection_healthy = False
        return False


# Backward compatibility wrappers - these maintain the original function signatures
async def ensure_client_connected(client: ModbusTcpClient, host: str, port: int, logger: logging.Logger) -> None:
    """Ensures the Modbus client is connected, attempting to connect if not."""
    await _connect_client(client, host, port, logger, create_new=False)


async def connect_if_needed(client: Optional[ModbusTcpClient], host: str, port: int) -> ModbusTcpClient:
    """Creates a new client if needed and ensures it is connected."""
    return await _connect_client(client, host, port, _LOGGER, create_new=True)

# ============================================================================
# RETRY LOGIC
# ============================================================================

# OPTIMIZATION: Refactored retry handlers to use separate functions for
# should_retry and on_retry logic, reducing code duplication and improving
# maintainability. The _create_retry_handlers() function now uses
# functools.partial to create on_retry callback.

async def _exponential_backoff(attempt: int, base: float, cap: float) -> None:
    delay = min(base * 2 ** (attempt - 1), cap)
    _LOGGER.debug("Backoff: waiting %.2fs before retry #%d", delay, attempt)
    await asyncio.sleep(delay)

async def _retry_with_backoff(
    func: Callable[[], Awaitable[Any]],
    should_retry: Callable[[Exception], bool],
    retries: int,
    base_delay: float,
    cap: float,
    on_retry: Optional[Callable[[int, Exception], Awaitable[None]]] = None,
    task_name: str = "Task"
) -> Any:
    last_exception: Exception
    for attempt in range(1, retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if not should_retry(e):
                _LOGGER.error("Non-retriable exception occurred", exc_info=True)
                raise
            _LOGGER.warning("[%s] Attempt %d failed: %s", task_name, attempt, e, exc_info=(attempt == retries))
            if on_retry:
                await on_retry(attempt, e)
            if attempt < retries:
                await _exponential_backoff(attempt, base_delay, cap)
    _LOGGER.warning("[%s] All %d attempts failed: %s", task_name, retries, last_exception)
    raise last_exception

# Default retry settings
DEFAULT_READ_RETRIES = 3
DEFAULT_READ_BASE_DELAY = 2.0
DEFAULT_READ_CAP_DELAY = 10.0

DEFAULT_WRITE_RETRIES = 2
DEFAULT_WRITE_BASE_DELAY = 1.0
DEFAULT_WRITE_CAP_DELAY = 5.0

def _should_retry_modbus_error(e: Exception) -> bool:
    """
    Determines if a Modbus error should trigger a retry.
    
    Includes ConnectionError to catch standard OS connection errors (like ConnectionResetError).
    """
    return isinstance(e, (ConnectionException, ModbusIOException, ConnectionError))


async def _on_modbus_retry(
    client: ModbusTcpClient,
    host: str,
    port: int,
    logger: logging.Logger,
    operation_name: str,
    lock: Lock,
    attempt: int,
    e: Exception
) -> None:
    """
    Handles retry logic for Modbus operations, including reconnection on connection errors.
    
    Args:
        client: The Modbus client
        host: The host to connect to
        port: The port to connect to
        logger: Logger instance
        operation_name: Name of the operation being retried
        lock: Lock for thread safety
        attempt: Current attempt number
        e: The exception that triggered the retry
    """
    # Trigger reconnection for both pymodbus ConnectionException and standard ConnectionError
    if isinstance(e, (ConnectionException, ConnectionError)):
        logger.info("Connection lost during %s, attempting reconnect", operation_name)
        
        # Acquire lock to ensure we don't interfere with other tasks using the client
        async with lock:
            # Force close to ensure connected state is reset
            try:
                client.close()
            except Exception:
                pass  # Ignore errors during close

            try:
                await _connect_client(client, host, port, logger, create_new=False)
                logger.info("Reconnect during %s successful", operation_name)
            except Exception as reconnect_error:
                logger.warning("Reconnect during %s failed: %s. Will retry in next attempt.", operation_name, reconnect_error)
                # Do NOT raise here, let the backoff loop continue


def _create_retry_handlers(client: ModbusTcpClient, host: str, port: int, logger: logging.Logger, operation_name: str, lock: Lock):
    """
    Create standard retry handlers for Modbus operations.
    
    Returns:
        Tuple of (should_retry, on_retry) functions
    """
    should_retry = _should_retry_modbus_error
    on_retry = functools.partial(_on_modbus_retry, client, host, port, logger, operation_name, lock)
    return should_retry, on_retry

# ============================================================================
# MODBUS OPERATIONS
# ============================================================================

async def _perform_modbus_operation(
    client: ModbusTcpClient,
    lock: Lock,
    unit: int,
    operation: Callable[..., Any],
    *args: Any,
    **kwargs: Any
) -> Any:
    """
    Performs a Modbus operation, setting the unit_id on the client.
    Executes blocking Modbus calls in the executor to avoid blocking the event loop.
    """
    async with lock:
        client.unit_id = unit
        if ModbusGlobalConfig.hass:
            return await ModbusGlobalConfig.hass.async_add_executor_job(
                functools.partial(operation, *args, **kwargs)
            )
        else:
            # Fallback for testing or if hass is not configured
            return operation(*args, **kwargs)

async def try_read_registers(
    client: ModbusTcpClient,
    lock: Lock,
    unit: int,
    address: int,
    count: int,
    max_retries: int = DEFAULT_READ_RETRIES,
    base_delay: float = DEFAULT_READ_BASE_DELAY,
    cap_delay: float = DEFAULT_READ_CAP_DELAY,
) -> List[int]:
    host = ModbusGlobalConfig.host
    port = ModbusGlobalConfig.port
    if host is None or port is None:
        raise ReconnectionNeededError("Modbus client not configured with host and port.")

    should_retry, on_retry = _create_retry_handlers(client, host, port, _LOGGER, "read", lock)
    
    async def read_once():
        if ENABLE_DETAILED_MODBUS_READ_LOGGING:
            _LOGGER.debug("[read] unit=%s addr=%s count=%s", unit, hex(address), count)
        response = await _perform_modbus_operation(
            client, lock, unit, client.read_holding_registers, address=address, count=count
        )

        # Detect specific exception error early
        if response.isError():
            exc_code = getattr(response, "exception_code", None)
            if exc_code == 1:  # Illegal Function (Exception Code 1)
                raise ValueError("Unsupported register (Exception response 131 / 0)")
            raise ModbusIOException("General Modbus read error")

        if not hasattr(response, "registers"):
            raise ModbusIOException("No registers in response")
        if ENABLE_DETAILED_MODBUS_READ_LOGGING:
            _LOGGER.debug("[read-ok] unit=%s addr=%s count=%s regs=%s", unit, hex(address), count, response.registers)
        return response.registers  # type: ignore
    
    async def on_read_retry(attempt: int, e: Exception) -> None:
        _LOGGER.warning("[Modbus-Read] Retry %d after error: %s", attempt, e)
        await on_retry(attempt, e)

    return await _retry_with_backoff(
        func=read_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_read_retry,
        task_name="Modbus-Read"
    )


async def try_write_registers(
    client: ModbusTcpClient,
    lock: Lock,
    unit: int,
    address: int,
    values: Union[int, List[int]],
    max_retries: int = DEFAULT_WRITE_RETRIES,
    base_delay: float = DEFAULT_WRITE_BASE_DELAY,
    cap_delay: float = DEFAULT_WRITE_CAP_DELAY,
) -> bool:
    host = ModbusGlobalConfig.host
    port = ModbusGlobalConfig.port
    if host is None or port is None:
        raise ReconnectionNeededError("Modbus client not configured with host and port.")

    should_retry, on_retry = _create_retry_handlers(client, host, port, _LOGGER, "write", lock)

    is_single = isinstance(values, int)

    async def write_once() -> bool:
        if ENABLE_DETAILED_MODBUS_WRITE_LOGGING:
            _LOGGER.debug("[write] unit=%s addr=%s values=%s", unit, hex(address), values)

        if is_single:
            result = await _perform_modbus_operation(
                client, lock, unit, client.write_register, address=address, value=values
            )
        else:
            result = await _perform_modbus_operation(
                client, lock, unit, client.write_registers, address=address, values=values
            )
        if result.isError():
            raise ModbusIOException("Write response error")

        if ENABLE_DETAILED_MODBUS_WRITE_LOGGING:
            _LOGGER.debug("[write-ok] unit=%s addr=%s values=%s", unit, hex(address), values)
        return True

    return await _retry_with_backoff(
        func=write_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_retry,
        task_name="Modbus-Write"
    )
