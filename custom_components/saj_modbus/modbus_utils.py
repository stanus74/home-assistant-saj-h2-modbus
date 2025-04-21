import asyncio
import logging
import inspect
from typing import Any, Awaitable, Callable, List, Optional, TypeAlias, Union

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock

_LOGGER = logging.getLogger(__name__)

class ReconnectionNeededError(Exception):
    """Indicates that a reconnect is needed due to communication failure."""
    pass

async def _exponential_backoff(attempt: int, base: float, cap: float) -> None:
    """Wait with exponential backoff, capped at `cap` seconds."""
    delay = min(base * 2 ** (attempt - 1), cap)
    _LOGGER.debug(f"Backoff: waiting {delay:.2f}s before retry #{attempt}")
    await asyncio.sleep(delay)

async def _retry_with_backoff(
    func: Callable[[], Awaitable[Any]],
    should_retry: Callable[[Exception], bool],
    retries: int,
    base_delay: float,
    cap: float,
    on_retry: Optional[Callable[[int, Exception], Awaitable[None]]] = None
) -> Any:
    """
    Generic retry helper with exponential backoff.

    Args:
        func: Async function to execute.
        should_retry: Predicate to decide if an exception should trigger a retry.
        retries: Max number of attempts.
        base_delay: Base delay in seconds for backoff.
        cap: Maximum backoff delay.
        on_retry: Optional callback invoked before each retry.

    Returns:
        Result of `func()` if successful.

    Raises:
        The last exception if all retries fail.
    """
    last_exception: Exception
    for attempt in range(1, retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if not should_retry(e):
                _LOGGER.error("Non-retriable exception occurred", exc_info=True)
                raise
            _LOGGER.warning(f"Attempt {attempt} failed: {e}", exc_info=True)
            if on_retry:
                await on_retry(attempt, e)
            if attempt < retries:
                await _exponential_backoff(attempt, base_delay, cap)
    _LOGGER.error(f"All {retries} attempts failed: {last_exception}")
    raise last_exception

class ModbusConnection:
    """Async context manager for Modbus TCP connections with auto-connect and close."""
    def __init__(
        self,
        client: ModbusClient,
        host: str,
        port: int,
        max_retries: int = 3,
        timeout: float = 10.0,
        backoff_base: float = 2.0
    ):
        self._client = client
        self._host = host
        self._port = port
        self._max_retries = max_retries
        self._timeout = timeout
        self._backoff_base = backoff_base

    async def __aenter__(self) -> ModbusClient:
        await self.connect()
        return self._client

    async def __aexit__(
        self, exc_type: Any, exc: Any, tb: Any
    ) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                close_fn = getattr(self._client, "close", None)
                if close_fn:
                    if inspect.iscoroutinefunction(close_fn):
                        await close_fn()
                    else:
                        close_fn()
        except Exception:
            _LOGGER.warning("Error closing Modbus connection", exc_info=True)

    async def connect(self) -> None:
        """Attempt to connect to the Modbus server with retries and backoff."""
        async def do_connect():
            await asyncio.wait_for(
                self._client.connect(), timeout=self._timeout
            )
            if not self._client.connected:
                raise ConnectionException("Connection failed")
            return True

        async def on_retry(attempt: int, e: Exception) -> None:
            _LOGGER.info(f"Reconnect attempt {attempt} after error: {e}")

        await _retry_with_backoff(
            func=do_connect,
            should_retry=lambda e: True,
            retries=self._max_retries,
            base_delay=self._backoff_base,
            cap=self._backoff_base ** self._max_retries,
            on_retry=on_retry
        )

async def ensure_connection(
    client: ModbusClient,
    host: str,
    port: int,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
    backoff_base: float = 2.0
) -> bool:
    """Ensure the Modbus client is connected, retrying on failure."""
    try:
        conn = ModbusConnection(
            client, host, port, max_retries, timeout_seconds, backoff_base
        )
        await conn.connect()
        return True
    except Exception as e:
        _LOGGER.error(f"Could not establish Modbus connection: {e}")
        return False

async def try_read_registers(
    client: ModbusClient,
    lock: Lock,
    unit: int,
    address: int,
    count: int,
    max_retries: int = 3,
    base_delay: float = 2.0,
    cap_delay: float = 10.0,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> List[int]:
    """Read holding registers with retry logic and auto-reconnect."""
    if not client.connected:
        raise ReconnectionNeededError(
            "Client not connected before attempting to read registers"
        )

    async def read_once():
        async with lock:
            response = await client.read_holding_registers(
                address=address, count=count, slave=unit
            )
        if response.isError() or not hasattr(response, "registers"):
            raise ModbusIOException("Invalid or error response")
        return response.registers  # type: ignore

    def should_retry(e: Exception) -> bool:
        return isinstance(e, (ConnectionException, ModbusIOException))

    async def on_retry(attempt: int, e: Exception) -> None:
        if isinstance(e, ConnectionException) and host and port:
            _LOGGER.info("Connection lost during read, attempting reconnect")
            if not await ensure_connection(client, host, port):
                _LOGGER.error("Reconnect failed during read")
                raise ReconnectionNeededError from e

    return await _retry_with_backoff(
        func=read_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_retry,
    )

async def try_write_registers(
    client: ModbusClient,
    lock: Lock,
    unit: int,
    address: int,
    values: Union[int, List[int]],
    max_retries: int = 2,
    base_delay: float = 1.0,
    cap_delay: float = 5.0,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> bool:
    """Write single or multiple registers with retry logic and auto-reconnect."""
    if not client.connected:
        raise ReconnectionNeededError(
            "Client not connected before attempting to write registers"
        )

    is_single = isinstance(values, int)

    async def write_once() -> bool:
        async with lock:
            if is_single:
                result = await client.write_register(
                    address=address, value=values, slave=unit
                )
            else:
                result = await client.write_registers(
                    address=address, values=values, slave=unit
                )
        if result.isError():
            raise ModbusIOException("Write response error")
        return True

    def should_retry(e: Exception) -> bool:
        return isinstance(e, (ConnectionException, ModbusIOException))

    async def on_retry(attempt: int, e: Exception) -> None:
        if isinstance(e, ConnectionException) and host and port:
            _LOGGER.info("Connection lost during write, attempting reconnect")
            if not await ensure_connection(client, host, port):
                _LOGGER.error("Reconnect failed during write")
                raise ReconnectionNeededError from e

    return await _retry_with_backoff(
        func=write_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_retry,
    )
