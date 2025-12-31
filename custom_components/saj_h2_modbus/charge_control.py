"""Optimized charge control with exponential backoff and improved error handling."""
import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, List, Dict, Tuple, Callable, TYPE_CHECKING

from .const import DOMAIN

if TYPE_CHECKING:
    from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

CHARGE_PENDING_SUFFIXES = ("start", "end", "day_mask", "power_percent")

# App Mode Constants
APP_MODE_SELF_CONSUMPTION = 0
APP_MODE_FORCE_CHARGE_DISCHARGE = 1
APP_MODE_PASSIVE = 3

# Default Power Percent
DEFAULT_POWER_PERCENT = 10

# Retry configuration for handler write operations
MAX_HANDLER_RETRIES = 3
HANDLER_RETRY_DELAY = 1.0  # seconds

# --- Definitions for Pending Setter (Restored for compatibility) ---
PENDING_FIELDS: List[tuple[str, str]] = (
    [
        (f"charge{i}_{suffix}", f"charges[{i-1}][{suffix}]")
        for i in range(1, 8)
        for suffix in ["start", "end", "day_mask", "power_percent"]
    ]
    + [
        (f"discharge{i}_{suffix}", f"discharges[{i-1}][{suffix}]")
        for i in range(1, 8)
        for suffix in ["start", "end", "day_mask", "power_percent"]
    ]
    + [
        ("export_limit", "export_limit"),
        ("charging", "charging_state"),
        ("discharging", "discharging_state"),
        ("app_mode", "app_mode"),
        ("charge_time_enable", "charge_time_enable"),
        ("discharge_time_enable", "discharge_time_enable"),
        ("battery_on_grid_discharge_depth", "battery_on_grid_discharge_depth"),
        ("battery_off_grid_discharge_depth", "battery_off_grid_discharge_depth"),
        ("battery_capacity_charge_upper_limit", "battery_capacity_charge_upper_limit"),
        ("battery_charge_power_limit", "battery_charge_power_limit"),
        ("battery_discharge_power_limit", "battery_discharge_power_limit"),
        ("grid_max_charge_power", "grid_max_charge_power"),
        ("grid_max_discharge_power", "grid_max_discharge_power"),
        ("passive_charge_enable", "passive_charge_enable"),
        ("passive_grid_charge_power", "passive_grid_charge_power"),
        ("passive_grid_discharge_power", "passive_grid_discharge_power"),
        ("passive_bat_charge_power", "passive_bat_charge_power"),
        ("passive_bat_discharge_power", "passive_bat_discharge_power"),
    ]
)

# --- Centralized Modbus Address Definitions ---
MODBUS_ADDRESSES = {
    "power_states": {
        "charging": {"address": 0x3604, "label": "charging state"},
        "discharging": {"address": 0x3605, "label": "discharging state"},
    },
    "time_enables": {
        "charge": {"address": 0x3604, "label": "charge time enable"},
        "discharge": {"address": 0x3605, "label": "discharge time enable"},
    },
    "slots": {
        "charge": [
            {"start": 0x3606 + i * 3, "end": 0x3606 + i * 3 + 1, "day_mask_power": 0x3606 + i * 3 + 2}
            for i in range(7)
        ],
        "discharge": [
            {"start": 0x361B + i * 3, "end": 0x361B + i * 3 + 1, "day_mask_power": 0x361B + i * 3 + 2}
            for i in range(7)
        ],
    },
    "simple_settings": {
        "export_limit": {"address": 0x365A, "label": "export limit"},
        "app_mode": {"address": 0x3647, "label": "app mode"},
        "charge_time_enable": {"address": 0x3604, "label": "charge time enable"},
        "discharge_time_enable": {"address": 0x3605, "label": "discharge time enable"},
        "battery_on_grid_discharge_depth": {"address": 0x3644, "label": "battery on grid discharge depth"},
        "battery_off_grid_discharge_depth": {"address": 0x3645, "label": "battery off grid discharge depth"},
        "battery_capacity_charge_upper_limit": {"address": 0x3646, "label": "battery capacity charge upper limit"},
        "battery_charge_power_limit": {"address": 0x364D, "label": "battery charge power limit"},
        "battery_discharge_power_limit": {"address": 0x364E, "label": "battery discharge power limit"},
        "grid_max_charge_power": {"address": 0x364F, "label": "grid max charge power"},
        "grid_max_discharge_power": {"address": 0x3650, "label": "grid max discharge power"},
        "passive_charge_enable": {"address": 0x3636, "label": "passive charge enable"},
        "passive_grid_charge_power": {"address": 0x3637, "label": "passive grid charge power"},
        "passive_grid_discharge_power": {"address": 0x3638, "label": "passive grid discharge power"},
        "passive_bat_charge_power": {"address": 0x3639, "label": "passive battery charge power"},
        "passive_bat_discharge_power": {"address": 0x363A, "label": "passive battery discharge power"},
    }
}

class CommandType(Enum):
    CHARGE_SLOT = "charge_slot"
    DISCHARGE_SLOT = "discharge_slot"
    CHARGING_STATE = "charging_state"
    DISCHARGING_STATE = "discharging_state"
    PASSIVE_MODE = "passive_mode"
    SIMPLE_SETTING = "simple_setting"

@dataclass
class Command:
    type: CommandType
    payload: dict

class ChargeSettingHandler:
    """Handler for all Charge/Discharge-Settings using a Command Queue."""

    def __init__(self, hub: "SAJModbusHub") -> None:
        self.hub = hub
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._is_processing = False
        self._processing_lock = asyncio.Lock()

        # Locks & Caches
        self._app_mode_before_passive: Optional[int] = None
        # Locks removed
        # Cache removed

        # Initialize hub pending states (kept for compatibility if hub accesses them directly)

        # Command Dispatcher
        self._handlers = {
            CommandType.SIMPLE_SETTING: self._handle_simple_setting,
            CommandType.CHARGE_SLOT: lambda p: self._handle_slot_setting("charge", p),
            CommandType.DISCHARGE_SLOT: lambda p: self._handle_slot_setting("discharge", p),
            CommandType.CHARGING_STATE: lambda p: self._handle_power_state("charging", p.get("value")),
            CommandType.DISCHARGING_STATE: lambda p: self._handle_power_state("discharging", p.get("value")),
            CommandType.PASSIVE_MODE: lambda p: self._handle_passive_mode(p.get("value")),
        }

    # ========== QUEUE MANAGEMENT ==========

    async def queue_command(self, command: Command) -> None:
        """Adds a new command to the queue and starts processing if needed."""
        async with self._processing_lock:
            await self._command_queue.put(command)
            if not self._is_processing:
                self._is_processing = True
                asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Processes the command queue."""
        while not self._command_queue.empty():
            command = await self._command_queue.get()
            try:
                await self._execute_command(command)
            except Exception as e:
                _LOGGER.error("Error executing command %s: %s", command.type, e, exc_info=True)
            
            # Small delay to prevent bus saturation
            await asyncio.sleep(0.1)
            
        self._is_processing = False

    async def _execute_command(self, command: Command) -> None:
        """Executes a single command based on its type."""
        handler = self._handlers.get(command.type)
        if handler:
            await handler(command.payload)
        else:
            _LOGGER.warning("No handler for command type: %s", command.type)

    # ========== COMMAND HANDLERS ==========

    async def _handle_simple_setting(self, payload: dict) -> None:
        key = payload.get("key")
        value = payload.get("value")
        
        setting_def = MODBUS_ADDRESSES["simple_settings"].get(key)
        if not setting_def:
            _LOGGER.warning("Unknown simple setting: %s", key)
            return

        # Special handling for passive_charge_enable if it comes through simple settings
        if key == "passive_charge_enable":
            await self._handle_passive_mode(value)
            return

        try:
            int_value = int(value)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid value for %s: %s", key, value)
            return

        # Write and update cache immediately
        if await self._write_register_with_backoff(setting_def["address"], int_value, setting_def["label"]):
            self._update_cache({key: int_value})

    async def _handle_slot_setting(self, mode_type: str, payload: dict) -> None:
        """Handles settings for a specific slot (charge/discharge)."""
        index = payload.get("index") # 0-based index
        field = payload.get("field")
        value = payload.get("value")

        if index is None or index < 0 or index > 6:
            _LOGGER.error("Invalid slot index: %s", index)
            return

        slot_defs = MODBUS_ADDRESSES["slots"][mode_type][index]
        label = f"{mode_type}{index+1}"

        if field in ["start", "end"]:
            reg_val = self._parse_time_to_register(value)
            if reg_val is not None:
                if await self._write_register_with_backoff(slot_defs[field], reg_val, f"{label} {field}"):
                    # Update cache
                    self._update_cache({f"{label}_{field}": value})
            else:
                _LOGGER.error("Invalid time format for %s %s: %s", label, field, value)
        
        elif field in ["day_mask", "power_percent"]:
            # For day_mask and power_percent, we need read-modify-write
            await self._update_day_mask_and_power(
                slot_defs["day_mask_power"],
                value if field == "day_mask" else None,
                value if field == "power_percent" else None,
                label
            )

        # Handle time_enable for slots 2-7 (index 1-6)
        if index > 0:
            await self._ensure_slot_enabled(mode_type, index, label)

    async def _ensure_slot_enabled(self, mode_type: str, index: int, label: str) -> None:
        """Ensures the time_enable bit is set for the given slot."""
        enable_def = MODBUS_ADDRESSES["time_enables"][mode_type]
        
        def modifier(current_mask):
            return current_mask | (1 << index)

        success, new_mask = await self._modify_register(enable_def["address"], modifier, f"{label} time_enable")
        if success:
            # Update cache
            key = "charge_time_enable" if mode_type == "charge" else "discharge_time_enable"
            self._update_cache({key: new_mask})

    async def _handle_power_state(self, state_type: str, value: bool) -> None:
        """Handles charging or discharging state changes generically."""
        addr = MODBUS_ADDRESSES["power_states"][state_type]["address"]
        write_value = 1 if value else 0
        
        try:
            if await self._write_register_with_backoff(addr, write_value, f"{state_type} state"):
                # Update cache immediately
                self._update_cache({f"{state_type}_enabled": write_value})
                
                # Update AppMode logic
                chg, dchg = self._get_power_states()
                await self._update_app_mode_from_states(charge_enabled=chg, discharge_enabled=dchg)
        finally:
            self._clear_pending_state(state_type)
            # Force UI update to clear pending flag and show new state
            self.hub.async_set_updated_data(self.hub.inverter_data)

    async def _handle_passive_mode(self, value: Optional[int]) -> None:
        if value is None:
            return
        desired_int = int(value)
        
        addr = MODBUS_ADDRESSES["simple_settings"]["passive_charge_enable"]["address"]
        try:
            if await self._write_register_with_backoff(addr, desired_int, "passive charge enable"):
                # Update cache immediately
                self._update_cache({"passive_charge_enable": desired_int})

                if desired_int > 0:
                    await self._activate_passive_mode()
                else:
                    await self._deactivate_passive_mode()
        finally:
            self._clear_pending_state("passive_mode")
            # Force UI update to clear pending flag and show new state
            self.hub.async_set_updated_data(self.hub.inverter_data)

    async def _activate_passive_mode(self) -> None:
        """Activate passive mode by capturing current app mode and setting to passive."""
        self._capture_app_mode_before_passive()
        await self._set_app_mode(APP_MODE_PASSIVE, "passive mode activation")

    async def _deactivate_passive_mode(self) -> None:
        """Deactivate passive mode by restoring previous app mode or calculating from states."""
        restored = False
        if self._app_mode_before_passive is not None:
            await self._set_app_mode(self._app_mode_before_passive, "restore from passive mode", force=True)
            restored = True
        
        if not restored:
            chg, dchg = self._get_power_states()
            await self._update_app_mode_from_states(charge_enabled=chg, discharge_enabled=dchg, force=True)
        self._app_mode_before_passive = None

    def _get_power_states(self) -> Tuple[bool, bool]:
        """Get current charging and discharging states from inverter data."""
        chg = bool(self.hub.inverter_data.get("charging_enabled", 0))
        dchg = bool(self.hub.inverter_data.get("discharging_enabled", 0))
        return chg, dchg

    def _clear_pending_state(self, state_type: str) -> None:
        """Clear pending state for the given type."""
        setattr(self.hub, f"_pending_{state_type}_state", None)

    # ========== HELPER METHODS ==========

    def _update_cache(self, updates: Dict[str, Any]) -> None:
        """Update hub inverter_data and notify listeners."""
        self.hub.inverter_data.update(updates)
        self.hub.async_set_updated_data(self.hub.inverter_data)

    def _parse_time_to_register(self, time_str: str) -> Optional[int]:
        """Validates and converts time string HH:MM to register value."""
        if not isinstance(time_str, str):
            _LOGGER.debug("Invalid time format: not a string: %s", time_str)
            return None
        try:
            hours, minutes = map(int, time_str.split(":"))
            if 0 <= hours < 24 and 0 <= minutes < 60:
                return (hours << 8) | minutes
            _LOGGER.debug("Invalid time range: hours=%s, minutes=%s", hours, minutes)
        except ValueError as e:
            _LOGGER.debug("Invalid time format '%s': %s", time_str, e)
        except AttributeError as e:
            _LOGGER.debug("Invalid time format '%s': %s", time_str, e)
        return None

    def _capture_app_mode_before_passive(self) -> None:
        if self._app_mode_before_passive is not None:
            return
        current_mode = self.hub.inverter_data.get("AppMode")
        if current_mode is not None:
            try:
                self._app_mode_before_passive = int(current_mode)
            except (TypeError, ValueError):
                pass

    async def _set_app_mode(self, desired_app_mode: int, reason: str, force: bool = False) -> None:
        current_app_mode = self.hub.inverter_data.get("AppMode")
        if not force and current_app_mode == desired_app_mode:
            return
        
        addr = MODBUS_ADDRESSES["simple_settings"]["app_mode"]["address"]
        if await self._write_register_with_backoff(addr, desired_app_mode, f"AppMode ({reason})"):
            # Update cache
            self.hub.inverter_data["AppMode"] = desired_app_mode
            
            # Only notify if value actually changed
            if current_app_mode != desired_app_mode:
                self.hub.async_set_updated_data(self.hub.inverter_data)

    async def _update_app_mode_from_states(self, charge_enabled: bool, discharge_enabled: bool, force: bool = False) -> None:
        passive_active = int(self.hub.inverter_data.get("passive_charge_enable", 0)) > 0
        desired_app_mode = APP_MODE_PASSIVE if passive_active else (APP_MODE_FORCE_CHARGE_DISCHARGE if (charge_enabled or discharge_enabled) else APP_MODE_SELF_CONSUMPTION)
        await self._set_app_mode(desired_app_mode, "state synchronization", force=force)

    async def _write_register_with_backoff(self, address: int, value: int, label: str = "register") -> bool:
        """Write register with exponential backoff retry."""
        for attempt in range(1, MAX_HANDLER_RETRIES + 1):
            try:
                ok = await self.hub._write_register(address, int(value))
                if ok:
                    _LOGGER.info("Successfully wrote %s=%s to 0x%04x", label, value, address)
                    return True
            except Exception as e:
                _LOGGER.error("Error writing %s (attempt %d/%d): %s", label, attempt, MAX_HANDLER_RETRIES, e)

            if attempt < MAX_HANDLER_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))
        return False

    async def _modify_register(self, address: int, modifier: Callable[[int], int], label: str) -> Tuple[bool, int]:
        """Generic read-modify-write. Returns (success, new_value)."""
        try:
            regs = await self.hub._read_registers(address, 1)
            if not regs:
                return False, 0
            
            current_val = regs[0]
            new_val = modifier(current_val)
            
            if new_val != current_val:
                success = await self._write_register_with_backoff(address, new_val, label)
                return success, new_val
            return True, current_val # No change needed
        except Exception as e:
            _LOGGER.error("Error modifying %s: %s", label, e)
            return False, 0

    async def _update_day_mask_and_power(self, address: int, day_mask: Optional[int], power_percent: Optional[int], label: str) -> None:
        """Updates the day mask and power percentage using generic modifier."""
        def modifier(current_value):
            current_day_mask = (current_value >> 8) & 0xFF
            current_power_percent = current_value & 0xFF
            
            new_day_mask = current_day_mask if day_mask is None else day_mask
            
            if power_percent is not None:
                new_power_percent = power_percent
            elif current_value == 0:
                new_power_percent = DEFAULT_POWER_PERCENT
            else:
                new_power_percent = current_power_percent

            return (new_day_mask << 8) | new_power_percent

        success, new_value = await self._modify_register(address, modifier, f"{label} day_mask_power")
        if success:
            # Update cache
            self._update_cache({
                f"{label}_day_mask": (new_value >> 8) & 0xFF,
                f"{label}_power_percent": new_value & 0xFF
            })

    # --- Public API (Adapters to Queue) ---

    def _queue_command_async(self, command: Command) -> None:
        """Queue a command asynchronously."""
        asyncio.create_task(self.queue_command(command))

    def set_pending(self, key: str, value: Any) -> None:
        """Generic setter that queues commands."""
        # Handle array-based keys (e.g. charges[0][start]) using regex
        match = re.match(r"(charges|discharges)\[(\d+)\]\[(\w+)\]", key)
        if match:
            base, idx_str, field = match.groups()
            idx = int(idx_str)
            cmd_type = CommandType.CHARGE_SLOT if base == "charges" else CommandType.DISCHARGE_SLOT
            self._queue_command_async(Command(cmd_type, {"index": idx, "field": field, "value": value}))
            return

        # Handle simple attributes
        self._queue_command_async(Command(CommandType.SIMPLE_SETTING, {"key": key, "value": value}))

    def _set_state_with_pending(self, state_type: str, command_type: CommandType, value: Any) -> None:
        """Set a state with pending flag and queue command."""
        setattr(self.hub, f"_pending_{state_type}_state", value)
        self._queue_command_async(Command(command_type, {"value": value}))

    def set_charging_state(self, value: bool) -> None:
        """Set the charging state."""
        self._set_state_with_pending("charging", CommandType.CHARGING_STATE, value)

    def set_discharging_state(self, value: bool) -> None:
        """Set the discharging state."""
        self._set_state_with_pending("discharging", CommandType.DISCHARGING_STATE, value)

    def set_passive_mode(self, value: Optional[int]) -> None:
        """Set the passive mode."""
        self._set_state_with_pending("passive_mode", CommandType.PASSIVE_MODE, value)

    # --- Legacy / Compatibility Methods ---

    def has_pending(self) -> bool:
        """Check if there are any pending settings."""
        return not self._command_queue.empty() or self._is_processing

    async def process_pending(self) -> None:
        """Legacy method. Queue processing is now automatic."""
        # Ensure processing is running if queue is not empty
        if not self._command_queue.empty() and not self._is_processing:
            self._is_processing = True
            asyncio.create_task(self._process_queue())

    def get_optimistic_overlay(self, current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Returns None as optimistic UI is less relevant with immediate queue processing."""
        return None