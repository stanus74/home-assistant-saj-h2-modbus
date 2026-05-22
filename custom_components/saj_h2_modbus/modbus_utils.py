"""Low-level Modbus TCP utilities, retry logic, and connection caching."""
from __future__ import annotations
import asyncio
import functools
import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

import socket

from pymodbus.exceptions import ConnectionException, ModbusIOException
from pymodbus.client import ModbusTcpClient

# We use ModbusTcpClient explicitly, so we don't import the generic ModbusClient alias
from .const import Lock

_LOGGER = logging.getLogger(__name__)

# Set to True to enable detailed Modbus read attempt logging, False to disable.
# Either set DEBUG_READ_DEFAULT=True or use env `SAJ_DEBUG_MODBUS_READ=1`.
DEBUG_READ_DEFAULT = False
ENABLE_DETAILED_MODBUS_READ_LOGGING = (
    os.getenv("SAJ_DEBUG_MODBUS_READ", "0") == "1" or DEBUG_READ_DEFAULT
)

# Toggle detailed Modbus write logging.
# Either set DEBUG_WRITE_DEFAULT=True or use env `SAJ_DEBUG_MODBUS_WRITE=1`.
DEBUG_WRITE_DEFAULT = False
ENABLE_DETAILED_MODBUS_WRITE_LOGGING = (
    os.getenv("SAJ_DEBUG_MODBUS_WRITE", "0") == "1" or DEBUG_WRITE_DEFAULT
)

class ReconnectionNeededError(Exception):
    """Indicates that a reconnect is needed due to communication failure."""
    pass


class CircuitBreaker:
    """Generic circuit breaker pattern for protecting against cascading failures.

    States:
        CLOSED:    Normal operation; failures are counted.
        OPEN:      Failure threshold exceeded; calls are rejected immediately.
        HALF_OPEN: Testing whether the service has recovered.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: int = 30,
        name: str = "CircuitBreaker",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._name = name

    async def call(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        should_trip: Callable[[Exception], bool] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute *func* through the circuit breaker.

        Args:
            func: Async callable to protect.
            *args: Positional arguments forwarded to *func*.
            should_trip: Optional predicate; the breaker only opens when this
                returns True for the raised exception.  Defaults to always-trip.
            **kwargs: Keyword arguments forwarded to *func*.
        """
        now = time.monotonic()
        if should_trip is None:
            def should_trip(_: Exception) -> bool:
                return True

        if self.state == "OPEN":
            if now - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                _LOGGER.info("%s Circuit Breaker transitioning to HALF_OPEN", self._name)
            else:
                raise ConnectionError(f"{self._name} Circuit Breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                _LOGGER.info("%s Circuit Breaker transitioning to CLOSED", self._name)
            return result
        except Exception as e:
            if should_trip(e):
                self.failure_count += 1
                self.last_failure_time = now
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    _LOGGER.warning(
                        "%s Circuit Breaker OPEN after %s failures",
                        self._name,
                        self.failure_count,
                    )
            raise


class ModbusCircuitBreaker(CircuitBreaker):
    """Circuit breaker pattern for Modbus operations (reads/connect)."""

    def __init__(self, failure_threshold: int = 3, timeout: int = 30) -> None:
        super().__init__(failure_threshold, timeout, "Modbus")


# Module-level default used when no per-instance circuit breaker is active
# (e.g. during tests or direct calls outside of hub context).
_DEFAULT_CIRCUIT_BREAKER = ModbusCircuitBreaker()

# ContextVar that carries the per-ModbusConnectionManager circuit breaker
# through the coroutine call chain without changing every function signature.
# Set by SAJModbusHub before calling any reader; resets automatically when
# the enclosing asyncio task finishes.
_CIRCUIT_BREAKER_CTX: ContextVar[ModbusCircuitBreaker | None] = ContextVar(
    "saj_modbus_circuit_breaker", default=None
)


def get_modbus_circuit_breaker() -> ModbusCircuitBreaker:
    """Return the active per-instance circuit breaker, or the module-level default."""
    return _CIRCUIT_BREAKER_CTX.get() or _DEFAULT_CIRCUIT_BREAKER

# Global lock that serializes all reconnect attempts across polling loops.
# Fast-Loop and Slow-Loop share the same ModbusTcpClient; without this lock
# both loops would try to reconnect the same broken socket simultaneously,
# causing cascading "Connection refused" errors in the logs.
_RECONNECT_LOCK: asyncio.Lock = asyncio.Lock()

# Event that is SET when no reconnect is running, CLEARED while one is in progress.
# Coroutines that detect "another task is already reconnecting" wait on this event
# so they retry their read only AFTER the reconnect has completed (success or failure),
# instead of immediately retrying on a still-broken socket.
_RECONNECT_DONE: asyncio.Event = asyncio.Event()
_RECONNECT_DONE.set()  # Initially set: no reconnect in progress

# Global Modbus config storage
class ModbusGlobalConfig:
    host: str | None = None
    port: int | None = None
    hass: Any | None = None

def set_modbus_config(host: str, port: int, hass: Any = None) -> None:
    ModbusGlobalConfig.host = host
    ModbusGlobalConfig.port = port
    ModbusGlobalConfig.hass = hass
    _LOGGER.debug("Global Modbus config set: %s:%s (hass configured: %s)", host, port, hass is not None)

# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

# ============================================================================
# CONNECTION POOLING OPTIMIZATION
# ============================================================================

class ConnectionCache:
    """
    Caches Modbus client connections to reduce connection overhead.
    
    PERFORMANCE OPTIMIZATION: Reduces redundant connection checks and
    reconnection attempts by caching the client for a configurable TTL.
    """
    
    def __init__(self, cache_ttl: float = 30.0):
        """
        Initialize connection cache.
        
        Args:
            cache_ttl: Time to live for cached connections in seconds
        """
        self._cached_client: ModbusTcpClient | None = None
        self._cache_expiry: float = 0.0
        self._cache_ttl: float = cache_ttl
        self._last_health_check: float = 0.0
        self._health_check_interval: float = 5.0  # Check health every 5s
        self._connection_healthy: bool = True
        self._cache_lock = asyncio.Lock()  # Protects concurrent read-modify-write on cache state

    def _do_invalidate(self) -> None:
        """Internal invalidate without lock. Must be called while holding _cache_lock."""
        self._cached_client = None
        self._cache_expiry = 0.0

    async def get_cached_client(self) -> ModbusTcpClient | None:
        """
        Get cached client if still valid.
        
        Returns:
            Cached client if valid, None otherwise
        """
        async with self._cache_lock:
            now = time.monotonic()

            if self._cached_client is not None and now < self._cache_expiry:
                if self._is_connection_healthy(now):
                    return self._cached_client
                else:
                    # Connection not healthy, invalidate cache
                    self._do_invalidate()
                    return None

            return None

    async def set_cached_client(self, client: ModbusTcpClient) -> None:
        """
        Set cached client with TTL.
        
        Args:
            client: The client to cache
        """
        async with self._cache_lock:
            self._cached_client = client
            self._cache_expiry = time.monotonic() + self._cache_ttl
            self._connection_healthy = True
            self._last_health_check = time.monotonic()

    async def invalidate(self) -> None:
        """Invalidate the cached connection."""
        async with self._cache_lock:
            self._do_invalidate()

    async def notify_error(self) -> None:
        """Mark cache as immediately expired after a connection error.

        Faster than invalidate(): skips acquiring the lock for the expiry
        reset so concurrent tasks stop receiving the stale client right away.
        The next get_cached_client() call will fall through to a fresh connect.
        """
        async with self._cache_lock:
            self._cache_expiry = 0.0
            self._connection_healthy = False

    async def cleanup_stale(self) -> bool:
        """Invalidate cached client if expired or unhealthy."""
        async with self._cache_lock:
            now = time.monotonic()
            if self._cached_client is None:
                return False
            if now >= self._cache_expiry or not self._is_connection_healthy(now):
                self._do_invalidate()
                return True
            return False
    
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


async def _connect_client_inplace(client: ModbusTcpClient, host: str, port: int) -> None:
    """
    Connect an existing ModbusTcpClient in-place (close if needed, then connect).

    This is the ONLY correct way to reconnect under the single-client model:
    the object is never replaced, so all polling loops continue referencing
    the same socket after the reconnect completes.
    """
    if client.connected:
        return
    _LOGGER.debug("Connecting Modbus client to %s:%s", host, port)
    try:
        if ModbusGlobalConfig.hass:
            await ModbusGlobalConfig.hass.async_add_executor_job(client.connect)
        else:
            client.connect()
        if not client.connected:
            raise ConnectionError("Client failed to connect to %s:%s" % (host, port))
        _LOGGER.info("ModbusTcpClient successfully connected to %s:%s", host, port)
    except Exception as e:
        _LOGGER.error("Error connecting client to %s:%s: %s", host, port, e)
        raise ConnectionError("Failed to connect to %s:%s due to %s" % (host, port, e)) from e

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
    on_retry: Callable[[int, Exception], Awaitable[None]] | None = None,
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
DEFAULT_READ_BASE_DELAY = 0.5
DEFAULT_READ_CAP_DELAY = 5.0

DEFAULT_WRITE_RETRIES = 3
DEFAULT_WRITE_BASE_DELAY = 1.0
DEFAULT_WRITE_CAP_DELAY = 5.0

def _should_retry_modbus_error(e: Exception) -> bool:
    """
    Determines if a Modbus error should trigger a retry.
    
    Includes ConnectionError to catch standard OS connection errors (like ConnectionResetError).
    """
    # Treat low-level socket failures (e.g. Bad file descriptor) as retriable by default
    if isinstance(e, (OSError, socket.error)):
        return True

    return isinstance(e, (ConnectionException, ModbusIOException, ConnectionError))


def _should_trip_circuit_breaker(e: Exception) -> bool:
    """Trip CB only for connection-class failures (not protocol errors)."""
    return isinstance(e, (ConnectionException, ConnectionError, OSError))


async def _on_modbus_retry(
    client: ModbusTcpClient,
    host: str,
    port: int,
    logger: logging.Logger,
    operation_name: str,
    _lock: Lock,  # kept for functools.partial compatibility; reconnect uses _RECONNECT_LOCK
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
        _lock: Unused; kept so functools.partial in _create_retry_handlers binds correctly
        attempt: Current attempt number
        e: The exception that triggered the retry
    """
    # Trigger reconnection for both pymodbus ConnectionException and standard ConnectionError
    if isinstance(e, (ConnectionException, ConnectionError, OSError)):
        logger.info("Connection lost during %s, attempting reconnect", operation_name)

        # Fast path: another coroutine is already inside _RECONNECT_LOCK doing the reconnect.
        # Wait until that reconnect finishes (success or failure) before we retry our read,
        # so we don't immediately hit a still-broken socket.
        if _RECONNECT_LOCK.locked():
            logger.debug("Reconnect for %s waiting for in-progress reconnect to finish", operation_name)
            try:
                await asyncio.wait_for(_RECONNECT_DONE.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Reconnect wait timed out for %s, continuing anyway", operation_name)
            return

        # Signal that a reconnect is starting so concurrent tasks wait.
        _RECONNECT_DONE.clear()
        try:
            async with _RECONNECT_LOCK:
                # Double-checked: another coroutine may have already reconnected while we waited.
                if client.connected:
                    logger.debug("Reconnect for %s skipped – client already connected after lock", operation_name)
                    return

                # Force close to ensure connected state is reset
                try:
                    if hasattr(client, "socket") and client.socket:
                        try:
                            fileno = client.socket.fileno()
                        except Exception:
                            fileno = "unknown"
                        logger.debug("Closing Modbus socket (fd=%s) due to %s", fileno, e)
                    client.close()
                except Exception:
                    pass  # Ignore errors during close

                try:
                    await _connect_client_inplace(client, host, port)
                    logger.info("Reconnect during %s successful", operation_name)
                except Exception as reconnect_error:
                    logger.warning(
                        "Reconnect during %s failed: %s – aborting retry loop.",
                        operation_name,
                        reconnect_error,
                    )
                    raise ReconnectionNeededError(
                        f"Reconnect during {operation_name} failed: {reconnect_error}"
                    ) from reconnect_error
        finally:
            # Always unblock waiting tasks, whether reconnect succeeded or failed.
            _RECONNECT_DONE.set()


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
) -> list[int]:
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

    try:
        operation = functools.partial(
            _retry_with_backoff,
            func=read_once,
            should_retry=should_retry,
            retries=max_retries,
            base_delay=base_delay,
            cap=cap_delay,
            on_retry=on_read_retry,
            task_name="Modbus-Read",
        )
        return await get_modbus_circuit_breaker().call(
            operation,
            should_trip=_should_trip_circuit_breaker,
        )
    except (ConnectionException, ConnectionError, OSError) as final_e:
        # All retries exhausted on a connection-class error.
        # _on_modbus_retry already tried to reconnect on each attempt without success.
        # Convert to ReconnectionNeededError so _run_reader_methods can trigger a
        # hub-level reconnect and abort the poll cycle instead of continuing to
        # hammer the broken socket with every remaining reader group.
        raise ReconnectionNeededError(
            f"Modbus read failed after {max_retries} retries – connection lost: {final_e}"
        ) from final_e


async def try_write_registers(
    client: ModbusTcpClient,
    lock: Lock,
    unit: int,
    address: int,
    values: int | list[int],
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

    async def on_write_retry(attempt: int, e: Exception) -> None:
        _LOGGER.warning("[Modbus-Write] Retry %d after error: %s", attempt, e)
        await on_retry(attempt, e)

    try:
        operation = functools.partial(
            _retry_with_backoff,
            func=write_once,
            should_retry=should_retry,
            retries=max_retries,
            base_delay=base_delay,
            cap=cap_delay,
            on_retry=on_write_retry,
            task_name="Modbus-Write",
        )
        return await get_modbus_circuit_breaker().call(
            operation,
            should_trip=_should_trip_circuit_breaker,
        )
    except (ConnectionException, ConnectionError, OSError) as final_e:
        raise ReconnectionNeededError(
            f"Modbus write failed after {max_retries} retries – connection lost: {final_e}"
        ) from final_e
