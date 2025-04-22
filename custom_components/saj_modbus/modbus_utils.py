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

# Global Modbus config storage
class ModbusGlobalConfig:
    host: Optional[str] = None
    port: Optional[int] = None

def set_modbus_config(host: str, port: int) -> None:
    ModbusGlobalConfig.host = host
    ModbusGlobalConfig.port = port
    _LOGGER.debug(f"Global Modbus config set: {host}:{port}")

async def _exponential_backoff(attempt: int, base: float, cap: float) -> None:
    delay = min(base * 2 ** (attempt - 1), cap)
    _LOGGER.debug(f"Backoff: waiting {delay:.2f}s before retry #{attempt}")
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
            _LOGGER.warning(f"[{task_name}] Attempt {attempt} failed: {e}", exc_info=(attempt == retries))
            if on_retry:
                await on_retry(attempt, e)
            if attempt < retries:
                await _exponential_backoff(attempt, base_delay, cap)
    _LOGGER.warning(f"[{task_name}] All {retries} attempts failed: {last_exception}")
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
            timeout = self._timeout or 5.0
            async with asyncio.timeout(timeout):
                close_fn = getattr(self._client, "close", None)
                if close_fn:
                    if inspect.iscoroutinefunction(close_fn):
                        await close_fn()
                    else:
                        close_fn()
        except Exception:
            _LOGGER.warning("Error closing Modbus connection", exc_info=True)

    async def connect(self) -> None:
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
            should_retry=lambda e: isinstance(e, ConnectionException),
            retries=self._max_retries,
            base_delay=self._backoff_base,
            cap=self._backoff_base ** self._max_retries,
            on_retry=on_retry,
            task_name="Modbus-Connect"
        )

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
    host = host or ModbusGlobalConfig.host
    port = port or ModbusGlobalConfig.port

    if not client.connected:
        if host is None or port is None:
            raise ReconnectionNeededError("Client not connected and no host/port available")
        _LOGGER.info("Client not connected, reconnecting...")
        async with ModbusConnection(client, host, port):
            _LOGGER.info("Reconnect before read successful")

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
            async with ModbusConnection(client, host, port):
                _LOGGER.info("Reconnect during read successful")

    return await _retry_with_backoff(
        func=read_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_retry,
        task_name="Modbus-Read"
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
    host = host or ModbusGlobalConfig.host
    port = port or ModbusGlobalConfig.port

    if not client.connected:
        if host is None or port is None:
            raise ReconnectionNeededError("Client not connected and no host/port available")
        _LOGGER.info("Client not connected, reconnecting...")
        async with ModbusConnection(client, host, port):
            _LOGGER.info("Reconnect before write successful")

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
            async with ModbusConnection(client, host, port):
                _LOGGER.info("Reconnect during write successful")

    return await _retry_with_backoff(
        func=write_once,
        should_retry=should_retry,
        retries=max_retries,
        base_delay=base_delay,
        cap=cap_delay,
        on_retry=on_retry,
        task_name="Modbus-Write"
    )
