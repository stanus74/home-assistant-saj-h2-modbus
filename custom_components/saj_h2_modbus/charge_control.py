"""Optimized charge control with exponential backoff and improved error handling."""
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, List, Dict, Tuple

_LOGGER = logging.getLogger(__name__)

CHARGE_PENDING_SUFFIXES = ("start", "end", "day_mask", "power_percent")
ADVANCED_LOGGING = False

# Retry configuration for handler write operations
MAX_HANDLER_RETRIES = 3
HANDLER_RETRY_DELAY = 1.0  # seconds

# --- Definitions for Pending Setter (Keep for hub.py compatibility) ---
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

# --- Configuration-based Address Mapping ---
MODBUS_ADDRESSES = {
    "power_states": {
        "charging": {"address": 0x3604, "label": "charging state"},
        "discharging": {"address": 0x3605, "label": "discharging state"},
        "passive": {"address": 0x3636, "label": "passive charge enable"},
    },
    "time_enables": {
        "charge": {"address": 0x3604, "label": "charge time enable"},
        "discharge": {"address": 0x3605, "label": "discharge time enable"},
    },
    "slots": {
        "charge": [
            {
                "start": 0x3606 + i * 3,
                "end": 0x3607 + i * 3,
                "day_mask_power": 0x3608 + i * 3,
                "label": f"charge{i+1}"
            }
            for i in range(7)
        ],
        "discharge": [
            {
                "start": 0x361B + i * 3,
                "end": 0x361C + i * 3,
                "day_mask_power": 0x361D + i * 3,
                "label": f"discharge{i+1}"
            }
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
    payload: Dict[str, Any]

class ChargeSettingHandler:
    """Handler for all Charge/Discharge-Settings using a command queue."""

    def __init__(self, hub) -> None:
        self.hub = hub
        self._command_queue: asyncio.Queue = asyncio.Queue()
        self._is_processing = False
        
        # Locks
        self._charging_state_lock_until: Optional[float] = None
        self._discharging_state_lock_until: Optional[float] = None
        self._time_enable_cache: Dict[str, int] = {}
        self._app_mode_before_passive: Optional[int] = None

        # Optimistic state storage (simplified)
        self._optimistic_values: Dict[str, Any] = {}

    # ========== HELPER METHODS ==========

    def _is_valid_time_format(self, time_str: str) -> bool:
        """Validates time format HH:MM."""
        if not isinstance(time_str, str):
            return False
        parts = time_str.split(":")
        if len(parts) != 2:
            return False
        try:
            hours, minutes = map(int, parts)
            return 0 <= hours < 24 and 0 <= minutes < 60
        except (ValueError, TypeError):
            return False

    def _capture_app_mode_before_passive(self) -> None:
        if self._app_mode_before_passive is not None:
            return
        current_mode = self.hub.inverter_data.get("AppMode")
        if current_mode is None:
            _LOGGER.debug("AppMode value unavailable when capturing passive baseline")
            return
        try:
            self._app_mode_before_passive = int(current_mode)
            _LOGGER.debug(
                "Captured AppMode %s before entering passive mode",
                self._app_mode_before_passive,
            )
        except (TypeError, ValueError):
            _LOGGER.debug("Invalid AppMode %s; skipping capture", current_mode)

    # ========== QUEUE MANAGEMENT ==========

    def queue_command(self, command: Command) -> None:
        """Add a command to the queue."""
        self._command_queue.put_nowait(command)
        # Update optimistic state
        self._update_optimistic_state(command)

    def _update_optimistic_state(self, command: Command) -> None:
        """Update local optimistic state based on queued command."""
        p = command.payload
        if command.type == CommandType.CHARGING_STATE:
            self._optimistic_values["charging_enabled"] = 1 if p["value"] else 0
        elif command.type == CommandType.DISCHARGING_STATE:
            self._optimistic_values["discharging_enabled"] = 1 if p["value"] else 0
        elif command.type == CommandType.PASSIVE_MODE:
            val = p["value"]
            if val is not None:
                self._optimistic_values["passive_charge_enable"] = val
                if val > 0:
                    self._optimistic_values["AppMode"] = 3

    async def process_pending(self) -> None:
        """Process all commands in the queue."""
        if self._command_queue.empty():
            return

        if self._is_processing:
            return
        
        self._is_processing = True
        try:
            while not self._command_queue.empty():
                command = await self._command_queue.get()
                try:
                    await self._execute_command(command)
                except Exception as e:
                    _LOGGER.error("Error executing command %s: %s", command.type, e)
                finally:
                    self._command_queue.task_done()
        finally:
            self._is_processing = False

    async def _execute_command(self, command: Command) -> None:
        """Dispatch command to specific handler."""
        if command.type == CommandType.SIMPLE_SETTING:
            await self._handle_simple_setting(command.payload)
        elif command.type == CommandType.CHARGE_SLOT:
            await self._handle_slot_command(command.payload, is_charge=True)
        elif command.type == CommandType.DISCHARGE_SLOT:
            await self._handle_slot_command(command.payload, is_charge=False)
        elif command.type == CommandType.CHARGING_STATE:
            await self._handle_charging_state(command.payload["value"])
        elif command.type == CommandType.DISCHARGING_STATE:
            await self._handle_discharging_state(command.payload["value"])
        elif command.type == CommandType.PASSIVE_MODE:
            await self._handle_passive_mode(command.payload["value"])

    # ========== COMMAND HANDLERS ==========

    async def _handle_simple_setting(self, payload: Dict[str, Any]) -> None:
        key = payload["key"]
        value = payload["value"]
        
        # Special handling for passive_charge_enable if it comes via simple setting
        if key == "passive_charge_enable":
            await self._handle_passive_mode(value)
            return

        config = MODBUS_ADDRESSES["simple_settings"].get(key)
        if not config:
            _LOGGER.warning("No configuration found for simple setting: %s", key)
            return

        await self._write_register_with_backoff(config["address"], int(value), config["label"])

    async def _handle_slot_command(self, payload: Dict[str, Any], is_charge: bool) -> None:
        index = payload["index"]
        field_name = payload["field"]
        value = payload["value"]
        
        if not (0 <= index < 7):
            return

        slot_type = "charge" if is_charge else "discharge"
        slot_config = MODBUS_ADDRESSES["slots"][slot_type][index]
        label = f"{slot_config['label']} {field_name}"

        if field_name in ("start", "end"):
            if not self._is_valid_time_format(value):
                _LOGGER.error("Invalid time format for %s: %s", label, value)
                return
            reg_key = "start" if field_name == "start" else "end"
            address = slot_config[reg_key]
            reg_value = self._time_to_register_value(value)
            await self._write_register_with_backoff(address, reg_value, label)

        elif field_name in ("day_mask", "power_percent"):
            address = slot_config["day_mask_power"]
            await self._update_day_mask_and_power(
                address,
                day_mask=value if field_name == "day_mask" else None,
                power_percent=value if field_name == "power_percent" else None,
                label=slot_config['label']
            )

        # Ensure slot is enabled (for slots 2-7)
        if index > 0:
            await self._ensure_slot_enabled(index, is_charge)

    async def _ensure_slot_enabled(self, index: int, is_charge: bool) -> None:
        """Ensures the time_enable bit is set for the given slot index."""
        type_key = "charge" if is_charge else "discharge"
        config = MODBUS_ADDRESSES["time_enables"][type_key]
        address = config["address"]
        label = f"{type_key} time enable"
        cache_key = f"{type_key}_time_enable"

        # Read current
        current_regs = await self.hub._read_registers(address, 1)
        if not current_regs:
            return
        
        current_mask = current_regs[0]
        new_mask = current_mask | (1 << index)

        if current_mask == new_mask:
            self._time_enable_cache[cache_key] = new_mask
            return

        # Write
        if await self._write_register_with_backoff(address, new_mask, label):
            self._time_enable_cache[cache_key] = new_mask
            # Update hub data
            self.hub.inverter_data[f"{type_key}_time_enable"] = new_mask

    async def _handle_power_state(self, state_type: str, enabled: bool) -> None:
        """Handles a generic power state (charging or discharging)."""
        config = MODBUS_ADDRESSES["power_states"][state_type]
        value = 1 if enabled else 0
        label = config["label"]
        
        if await self._write_register_with_backoff(config["address"], value, label):
            # Update hub data
            self.hub.inverter_data[f"{state_type}_enabled"] = value
            self.hub.inverter_data[f"{state_type}_time_enable"] = value # Same register
            
            # Update time_enable cache to prevent redundant writes in _ensure_slot_enabled
            self._time_enable_cache[f"{state_type}_time_enable"] = value

            # Set lock
            import time as time_module
            lock_attr = f"_{state_type}_state_lock_until"
            setattr(self, lock_attr, time_module.monotonic() + 10.0)
            
            # Sync AppMode
            other_state_type = "discharging" if state_type == "charging" else "charging"
            other_value = self.hub.inverter_data.get(f"{other_state_type}_enabled", 0)
            other_enabled = bool(other_value)
            
            await self._update_app_mode_from_states(
                charge_enabled=enabled if state_type == "charging" else other_enabled,
                discharge_enabled=enabled if state_type == "discharging" else other_enabled
            )

            # Force UI update
            self.hub.async_set_updated_data(self.hub.inverter_data)

    async def _handle_charging_state(self, enabled: bool) -> None:
        await self._handle_power_state("charging", enabled)

    async def _handle_discharging_state(self, enabled: bool) -> None:
        await self._handle_power_state("discharging", enabled)

    async def _handle_passive_mode(self, value: Optional[int]) -> None:
        if value is None:
            return
        target = int(value)
        config = MODBUS_ADDRESSES["power_states"]["passive"]
        
        if await self._write_register_with_backoff(config["address"], target, config["label"]):
            self.hub.inverter_data["passive_charge_enable"] = target
            
            if target > 0:
                self._capture_app_mode_before_passive()
                await self._set_app_mode(3, "passive mode activation")
            else:
                # Restore logic
                if self._app_mode_before_passive is not None:
                    await self._set_app_mode(self._app_mode_before_passive, "restore", force=True)
                else:
                    chg = bool(self.hub.inverter_data.get("charging_enabled", 0))
                    dchg = bool(self.hub.inverter_data.get("discharging_enabled", 0))
                    await self._update_app_mode_from_states(chg, dchg, force=True)
                self._app_mode_before_passive = None

    # ========== SETTERS (Called from Hub) ==========

    def set_pending(self, key: str, value: Any) -> None:
        """Generic setter that queues commands."""
        if "[" in key:
            # charges[0][start]
            parts = key.replace("]", "").split("[")
            if len(parts) == 3:
                base, idx_str, field = parts
                try:
                    idx = int(idx_str)
                    if base == "charges":
                        self.queue_command(Command(CommandType.CHARGE_SLOT, {"index": idx, "field": field, "value": value}))
                    elif base == "discharges":
                        self.queue_command(Command(CommandType.DISCHARGE_SLOT, {"index": idx, "field": field, "value": value}))
                except ValueError:
                    pass
        else:
            self.queue_command(Command(CommandType.SIMPLE_SETTING, {"key": key, "value": value}))

    def set_charging_state(self, value: bool) -> None:
        self.queue_command(Command(CommandType.CHARGING_STATE, {"value": value}))

    def set_discharging_state(self, value: bool) -> None:
        self.queue_command(Command(CommandType.DISCHARGING_STATE, {"value": value}))

    def set_passive_mode(self, value: Optional[int]) -> None:
        self.queue_command(Command(CommandType.PASSIVE_MODE, {"value": value}))

    def invalidate_cache(self) -> None:
        pass # No longer needed with queue

    def has_pending(self) -> bool:
        return not self._command_queue.empty()

    # ========== HELPER METHODS (Reading/Writing Registers) ==========
    
    async def _write_register_with_backoff(self, address: int, value: int, label: str = "register") -> bool:
        """Write register with exponential backoff retry."""
        for attempt in range(1, MAX_HANDLER_RETRIES + 1):
            try:
                ok = await self.hub._write_register(address, int(value))
                if ok:
                    _LOGGER.info(
                        "Successfully wrote %s=%s to 0x%04x (attempt %d/%d)",
                        label, value, address, attempt, MAX_HANDLER_RETRIES
                    )
                    return True
                else:
                    _LOGGER.warning(
                        "Failed to write %s (attempt %d/%d)",
                        label, attempt, MAX_HANDLER_RETRIES
                    )
            except Exception as e:
                _LOGGER.error(
                    "Error writing %s (attempt %d/%d): %s",
                    label, attempt, MAX_HANDLER_RETRIES, e
                )

            # Exponential backoff: 1s, 2s, 4s
            if attempt < MAX_HANDLER_RETRIES:
                delay = 2 ** (attempt - 1)
                _LOGGER.debug(
                    "Waiting %.1fs before retry (exponential backoff)", delay
                )
                await asyncio.sleep(delay)

        return False

    async def _update_day_mask_and_power(
        self,
        address: int,
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str,
    ) -> None:
        """Updates the day mask and power percentage, reading current values if not provided."""
        try:
            regs = await self.hub._read_registers(address)
            if not regs:
                _LOGGER.error(
                    "Failed to read current day_mask_power for %s at address %s. No registers returned.",
                    label, hex(address)
                )
                return

            current_value = regs[0]
            current_day_mask = (current_value >> 8) & 0xFF
            current_power_percent = current_value & 0xFF

            # Use current day_mask if not provided
            new_day_mask = current_day_mask if day_mask is None else day_mask

            # Handle power_percent:
            # 1. If explicitly provided, use it
            # 2. If register is uninitialized (0/0), use default 10%
            # 3. Otherwise preserve current value
            if power_percent is not None:
                new_power_percent = power_percent
            elif current_value == 0:
                # Register never initialized - use default 10% to make slot active
                new_power_percent = 10
                _LOGGER.info(
                    "Register for %s uninitialized, using default power_percent: 10%%",
                    label
                )
            else:
                # Preserve existing power_percent
                new_power_percent = current_power_percent

            combined_value = (new_day_mask << 8) | new_power_percent

            if combined_value == current_value:
                _LOGGER.info(
                    "No change detected for %s day_mask_power. Current value: %s. Not writing to Modbus.",
                    label, current_value
                )
                return

            success = await self._write_register_with_backoff(
                address, combined_value, f"{label} day_mask_power"
            )

            if success:
                _LOGGER.info(
                    "Successfully set %s day_mask_power to: %s (day_mask: %s, power_percent: %s)",
                    label, combined_value, new_day_mask, new_power_percent
                )
            else:
                _LOGGER.error(
                    "Failed to write %s day_mask_power", label
                )
        except Exception as e:
            _LOGGER.error(
                "Error updating day mask and power for %s: %s", label, e
            )

    def _time_to_register_value(self, time_str: str) -> int:
        """Convert time string HH:MM to register value."""
        parts = time_str.split(":")
        if len(parts) != 2:
            return 0

        try:
            hours, minutes = map(int, parts)
            return (hours << 8) | minutes
        except (ValueError, TypeError):
            return 0

    async def _set_app_mode(self, desired_app_mode: int, reason: str, force: bool = False) -> None:
        current_app_mode = self.hub.inverter_data.get("AppMode")
        if not force and current_app_mode == desired_app_mode:
            _LOGGER.debug("AppMode already %s (%s)", desired_app_mode, reason)
            return
        ok = await self._write_register_with_backoff(
            MODBUS_ADDRESSES["simple_settings"]["app_mode"]["address"],
            desired_app_mode,
            f"AppMode ({reason})",
        )
        if ok:
            self.hub.inverter_data["AppMode"] = desired_app_mode
        else:
            _LOGGER.error("Failed to set AppMode to %s (%s)", desired_app_mode, reason)

    async def _update_app_mode_from_states(
        self,
        charge_enabled: bool,
        discharge_enabled: bool,
        force: bool = False,
    ) -> None:
        passive_active = self._is_passive_mode_active()
        desired_app_mode = 3 if passive_active else (1 if (charge_enabled or discharge_enabled) else 0)
        await self._set_app_mode(
            desired_app_mode,
            "state synchronization",
            force=force,
        )

    def _is_passive_mode_active(self) -> bool:
        """Check if passive mode is currently active."""
        # Check current data
        val = self.hub.inverter_data.get("passive_charge_enable", 0)
        return int(val) > 0

    # --- Locking Logic ---

    def is_charging_locked(self, current_time: float) -> bool:
        return self._charging_state_lock_until is not None and current_time < self._charging_state_lock_until

    def is_discharging_locked(self, current_time: float) -> bool:
        return self._discharging_state_lock_until is not None and current_time < self._discharging_state_lock_until

    def cleanup_locks(self, current_time: float) -> None:
        if self._charging_state_lock_until and current_time >= self._charging_state_lock_until:
            self._charging_state_lock_until = None
        if self._discharging_state_lock_until and current_time >= self._discharging_state_lock_until:
            self._discharging_state_lock_until = None

    # --- Optimistic UI ---

    def get_optimistic_overlay(self, current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Returns a data overlay with pending values applied to the latest known state."""
        if not current_data:
            return None

        # Start with a fresh copy of the latest known data
        overlay = dict(current_data)
        
        # Apply all optimistic values on top
        if self._optimistic_values:
            for k, v in self._optimistic_values.items():
                overlay[k] = v
            
        # Derive dependent states for UI consistency
        # This ensures AppMode is always correct based on optimistic power states
        chg = bool(overlay.get("charging_enabled", 0))
        dchg = bool(overlay.get("discharging_enabled", 0))
        passive = int(overlay.get("passive_charge_enable", 0)) > 0

        desired_app_mode = 3 if passive else (1 if (chg or dchg) else 0)
        overlay["AppMode"] = desired_app_mode

        return overlay