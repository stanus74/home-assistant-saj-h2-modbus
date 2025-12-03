"""Optimized charge control with exponential backoff and improved error handling."""
import asyncio
import logging
import re
from typing import Optional, Any, List, Dict, Tuple, Callable

_LOGGER = logging.getLogger(__name__)

CHARGE_PENDING_SUFFIXES = ("start", "end", "day_mask", "power_percent")
ADVANCED_LOGGING = False

# Retry configuration for handler write operations
MAX_HANDLER_RETRIES = 3
HANDLER_RETRY_DELAY = 1.0  # seconds

# --- Definitions for Pending Setter ---
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
CHARGE_BLOCK_START_ADDRESSES = [0x3606 + i * 3 for i in range(7)]
DISCHARGE_BLOCK_START_ADDRESSES = [0x361B + i * 3 for i in range(7)]

# --- Register Definitions ---
REGISTERS = {
    **{
        f"charge{i+1}": {
            "start_time": CHARGE_BLOCK_START_ADDRESSES[i],
            "end_time": CHARGE_BLOCK_START_ADDRESSES[i] + 1,
            "day_mask_power": CHARGE_BLOCK_START_ADDRESSES[i] + 2,
        }
        for i in range(7)
    },
    **{
        f"discharge{i+1}": {
            "start_time": DISCHARGE_BLOCK_START_ADDRESSES[i],
            "end_time": DISCHARGE_BLOCK_START_ADDRESSES[i] + 1,
            "day_mask_power": DISCHARGE_BLOCK_START_ADDRESSES[i] + 2,
        }
        for i in range(7)
    },
    "export_limit": 0x365A,
    "app_mode": 0x3647,
    "charging_state": 0x3604,
    "charge_time_enable": 0x3604,
    "discharging_state": 0x3605,
    "discharge_time_enable": 0x3605,
    "battery_on_grid_discharge_depth": 0x3644,
    "battery_off_grid_discharge_depth": 0x3645,
    "battery_capacity_charge_upper_limit": 0x3646,
    "battery_charge_power_limit": 0x364D,
    "battery_discharge_power_limit": 0x364E,
    "grid_max_charge_power": 0x364F,
    "grid_max_discharge_power": 0x3650,
    "passive_charge_enable": 0x3636,
    "passive_grid_charge_power": 0x3637,
    "passive_grid_discharge_power": 0x3638,
    "passive_bat_charge_power": 0x3639,
    "passive_bat_discharge_power": 0x363A,
}

# Mapping of simple pending attributes to their register addresses and labels
SIMPLE_REGISTER_MAP: Dict[str, Tuple[int, str]] = {
    "export_limit": (REGISTERS["export_limit"], "export limit"),
    "app_mode": (REGISTERS["app_mode"], "app mode"),
    "charge_time_enable": (REGISTERS["charge_time_enable"], "charge time enable"),
    "discharge_time_enable": (REGISTERS["discharge_time_enable"], "discharge time enable"),
    "battery_on_grid_discharge_depth": (
        REGISTERS["battery_on_grid_discharge_depth"],
        "battery on grid discharge depth",
    ),
    "battery_off_grid_discharge_depth": (
        REGISTERS["battery_off_grid_discharge_depth"],
        "battery off grid discharge depth",
    ),
    "battery_capacity_charge_upper_limit": (
        REGISTERS["battery_capacity_charge_upper_limit"],
        "battery capacity charge upper limit",
    ),
    "battery_charge_power_limit": (
        REGISTERS["battery_charge_power_limit"],
        "battery charge power limit",
    ),
    "battery_discharge_power_limit": (
        REGISTERS["battery_discharge_power_limit"],
        "battery discharge power limit",
    ),
    "grid_max_charge_power": (
        REGISTERS["grid_max_charge_power"],
        "grid max charge power",
    ),
    "grid_max_discharge_power": (
        REGISTERS["grid_max_discharge_power"],
        "grid max discharge power",
    ),
    "passive_charge_enable": (
        REGISTERS["passive_charge_enable"],
        "passive charge enable",
    ),
    "passive_grid_charge_power": (
        REGISTERS["passive_grid_charge_power"],
        "passive grid charge power",
    ),
    "passive_grid_discharge_power": (
        REGISTERS["passive_grid_discharge_power"],
        "passive grid discharge power",
    ),
    "passive_bat_charge_power": (
        REGISTERS["passive_bat_charge_power"],
        "passive battery charge power",
    ),
    "passive_bat_discharge_power": (
        REGISTERS["passive_bat_discharge_power"],
        "passive battery discharge power",
    ),
}


class ChargeSettingHandler:
    """Handler for all Charge/Discharge-Settings."""

    def __init__(self, hub) -> None:
        self.hub = hub

        # --- Pending State Management (Moved from Hub) ---
        self._pending_cache: Optional[bool] = None
        self._pending_cache_valid: bool = False

        # Simple attributes storage
        self._pending_simple: Dict[str, Any] = {}

        # Charge/Discharge slots
        self._pending_charges = [
            {key: None for key in CHARGE_PENDING_SUFFIXES}
            for _ in range(7)
        ]
        self._pending_discharges = [
            {key: None for key in CHARGE_PENDING_SUFFIXES}
            for _ in range(7)
        ]

        # Time enable masks
        self._pending_charge_time_enable: Optional[int] = None
        self._pending_discharge_time_enable: Optional[int] = None

        # Power states
        self._pending_charging_state: Optional[bool] = None
        self._pending_discharging_state: Optional[bool] = None

        # Locks
        self._charging_state_lock_until: Optional[float] = None
        self._discharging_state_lock_until: Optional[float] = None

        self._time_enable_cache: Dict[str, int] = {}  # Cache to avoid duplicate writes

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

    async def handle_settings(self, mode: str, label: str) -> None:
        """Handles settings dynamically based on mode (charge1-7 or discharge1-7) with optimized batch processing."""
        _LOGGER.debug(
            "[PENDING DEBUG] handle_settings called for mode=%s, label=%s",
            mode, label
        )

        try:
            registers = REGISTERS[mode]
            _LOGGER.debug(
                "[PENDING DEBUG] Registers for %s: %s", mode, registers
            )

            # Determine if this is a charge or discharge slot
            if mode.startswith("charge"):
                index = int(mode.replace("charge", "")) - 1
                slot_pending = self._pending_charges[index]
                is_charge = True
                time_enable_entity_id = REGISTERS["charge_time_enable"]
            else:  # discharge
                index = int(mode.replace("discharge", "")) - 1
                slot_pending = self._pending_discharges[index]
                is_charge = False
                time_enable_entity_id = REGISTERS["discharge_time_enable"]

            start_value = slot_pending.get("start")
            end_value = slot_pending.get("end")
            day_mask_value = slot_pending.get("day_mask")
            power_percent_value = slot_pending.get("power_percent")

            # Only write if there are pending values for this slot
            if not any(v is not None for v in [start_value, end_value, day_mask_value, power_percent_value]):
                _LOGGER.debug(f"No pending values for {mode}, skipping write.")
                return

            # IMPORTANT: Check if slot has complete data (start, end, power are REQUIRED)
            has_complete_data = (
                start_value is not None and
                end_value is not None and
                power_percent_value is not None
            )

            if not has_complete_data:
                _LOGGER.warning(
                    "[PENDING DEBUG] %s incomplete: start=%s, end=%s, power=%s. "
                    "Skipping time_enable write. Please provide start time, end time AND power.",
                    label, start_value, end_value, power_percent_value
                )
                self._reset_pending_values(mode)
                return

            # Batch write operations for better performance
            write_operations = []

            # Add start and end times if available
            if start_value is not None:
                if not self._is_valid_time_format(start_value):
                    _LOGGER.error(
                        "Invalid time format for start (%s) of %s.",
                        start_value, label
                    )
                else:
                    _LOGGER.debug(
                        "[PENDING DEBUG] Adding start time: %s", start_value
                    )
                    write_operations.append((registers["start_time"], self._time_to_register_value(start_value), f"{label} start"))

            if end_value is not None:
                if not self._is_valid_time_format(end_value):
                    _LOGGER.error(
                        "Invalid time format for end (%s) of %s.",
                        end_value, label
                    )
                else:
                    _LOGGER.debug(
                        "[PENDING DEBUG] Adding end time: %s", end_value
                    )
                    write_operations.append((registers["end_time"], self._time_to_register_value(end_value), f"{label} end"))

            # Handle day mask and power percent
            if "day_mask_power" in registers:
                # Read current day_mask from inverter cache if not provided
                if day_mask_value is None:
                    # Try to get current day_mask from inverter data cache
                    cache_key = f"{mode}_day_mask"
                    if cache_key in self.hub.inverter_data:
                        # Extract day_mask from cached day_mask_power value
                        cached_day_mask_power = self.hub.inverter_data.get(f"{mode}_day_mask_power", 0)
                        effective_day_mask = (cached_day_mask_power >> 8) & 0xFF
                        _LOGGER.debug(
                            "[PENDING DEBUG] Using cached day_mask for %s: %s",
                            label, effective_day_mask
                        )
                    else:
                        # Fallback to default if not in cache
                        effective_day_mask = 127
                        _LOGGER.debug(
                            "[PENDING DEBUG] Using default day_mask for %s: %s",
                            label, effective_day_mask
                        )
                else:
                    effective_day_mask = day_mask_value

                if power_percent_value is not None and not (0 <= power_percent_value <= 100):
                    _LOGGER.error(
                        "Invalid power range for %s: %s%%. Expected 0-100.",
                        label, power_percent_value
                    )
                    power_percent_value = None

                day_mask_power_value = self._calculate_day_mask_power_value(effective_day_mask, power_percent_value)
                if day_mask_power_value is not None:
                    _LOGGER.debug(
                        "[PENDING DEBUG] Adding day_mask_power update for %s", label
                    )
                    write_operations.append((
                        registers["day_mask_power"],
                        day_mask_power_value,
                        f"{label} day_mask_power"
                    ))
                else:
                    _LOGGER.warning(
                        "[PENDING DEBUG] Skipping day_mask_power update for %s - power_percent is None",
                        label
                    )
            else:
                _LOGGER.warning(
                    "[PENDING DEBUG] No day_mask_power register found for %s", mode
                )

            # Execute all write operations in parallel where possible
            if write_operations:
                _LOGGER.debug(
                    "[PENDING DEBUG] Executing %d write operations for %s",
                    len(write_operations), label
                )

                # Write all operations except time_enable
                for address, value, label in write_operations[:-1]:  # Exclude time_enable
                    await self._write_register_with_backoff(address, value, label)

                # Reset pending values for this specific slot
                _LOGGER.debug(
                    "[PENDING DEBUG] Resetting pending values for %s", mode
                )
                self._reset_pending_values(mode)

                # Handle time_enable separately for slots 2-7
                if index > 0:  # index 0 = Slot 1, skip it
                    cache_key = f"{'charge' if is_charge else 'discharge'}_time_enable"

                    _LOGGER.debug(
                        "[PENDING DEBUG] Starting time_enable update for %s (index %d)",
                        label, index
                    )

                    # Add delay to allow inverter to process previous writes
                    await asyncio.sleep(1.0)

                    # Read current time_enable value
                    current_regs = await self.hub._read_registers(time_enable_entity_id, 1)
                    if not current_regs:
                        _LOGGER.error(
                            "[PENDING DEBUG] Failed to read current time_enable for %s", label
                        )
                        return

                    current_mask = current_regs[0]
                    # IMPORTANT: Bit ADD (OR), not replace!
                    new_mask = current_mask | (1 << index)

                    # Check cache to avoid duplicate writes
                    if cache_key in self._time_enable_cache and self._time_enable_cache[cache_key] == new_mask:
                        _LOGGER.debug(
                            "[PENDING DEBUG] %s time_enable already cached with value %s, skipping write",
                            label, new_mask
                        )
                        return

                    if new_mask == current_mask:
                        _LOGGER.debug(
                            "[PENDING DEBUG] %s already enabled in time_enable (%s)",
                            label, current_mask
                        )
                        # Update cache even if no write needed
                        self._time_enable_cache[cache_key] = new_mask
                        return

                    _LOGGER.info(
                        "[PENDING DEBUG] Enabling %s in time_enable register: %s (binary: %s) → %s (binary: %s)",
                        label, current_mask, bin(current_mask), new_mask, bin(new_mask)
                    )
                    write_ok = await self._write_register_with_backoff(
                        time_enable_entity_id, new_mask, f"{label} time_enable"
                    )

                    if not write_ok:
                        _LOGGER.error(
                            "[PENDING DEBUG] Failed to write time_enable for %s", label
                        )
                        return

                    # Update cache immediately after successful write
                    self._time_enable_cache[cache_key] = new_mask

                    # Wait for write to complete
                    await asyncio.sleep(0.3)

                    # IMPORTANT: Read back to confirm
                    verify_regs = await self.hub._read_registers(time_enable_entity_id, 1)
                    if not verify_regs:
                        _LOGGER.error(
                            "[PENDING DEBUG] Failed to verify time_enable write for %s", label
                        )
                        return

                    actual_value = verify_regs[0]
                    _LOGGER.info(
                        "[PENDING DEBUG] Verified time_enable after write: %s (binary: %s) (expected: %s)",
                        actual_value, bin(actual_value), new_mask
                    )

                    # Update cache with ACTUAL value from inverter
                    if is_charge:
                        self.hub.inverter_data["charge_time_enable"] = actual_value
                        _LOGGER.info(
                            "[PENDING DEBUG] Updated cache: charge_time_enable = %s", actual_value
                        )
                    else:
                        self.hub.inverter_data["discharge_time_enable"] = actual_value
                        _LOGGER.info(
                            "[PENDING DEBUG] Updated cache: discharge_time_enable = %s", actual_value
                        )

                    # Force immediate data update to UI
                    self.hub.async_set_updated_data(self.hub.inverter_data)
                    _LOGGER.debug(
                        "[PENDING DEBUG] Forced UI update for %s", label
                    )

                    if actual_value != new_mask:
                        _LOGGER.warning(
                            "[PENDING DEBUG] Inverter returned different value! Wrote %s, got %s",
                            new_mask, actual_value
                        )
                        # Update cache with actual value from inverter
                        self._time_enable_cache[cache_key] = actual_value
                else:
                    _LOGGER.debug(
                        "[PENDING DEBUG] Skipping time_enable write for Slot 1 (controlled by master switch)"
                    )

        except Exception as e:
            _LOGGER.error(
                "Error handling %s settings: %s", label, e, exc_info=True
            )

    async def handle_charge_settings_by_index(self, index: int) -> None:
        """Handle charge settings for a specific slot index (1-7)."""
        mode = f"charge{index}"
        await self.handle_settings(mode, mode)

    async def handle_discharge_settings_by_index(self, index: int) -> None:
        """Handle discharge settings for a specific slot index (1-7)."""
        mode = f"discharge{index}"
        await self.handle_settings(mode, mode)

    async def _process_simple_setting(self, key: str) -> None:
        """Process a simple setting by looking up its register map."""
        value = self._pending_simple.get(key)
        
        if value is None:
            _LOGGER.debug("Skip %s: no pending value", key)
            return

        if key not in SIMPLE_REGISTER_MAP:
            _LOGGER.warning("No register map found for pending key: %s", key)
            # Remove unhandled key to prevent stuck pending state
            if key in self._pending_simple:
                del self._pending_simple[key]
            return

        address, label = SIMPLE_REGISTER_MAP[key]

        if address is None:
            _LOGGER.warning("%s register not configured; skip write", key)
            return

        # Use exponential backoff retry
        ok = await self._write_register_with_backoff(address, int(value), label)
        if ok:
            try:
                # Clear pending value
                if key in self._pending_simple:
                    del self._pending_simple[key]
            except Exception:
                pass
        else:
            _LOGGER.error(
                "Failed to write %s after %d attempts with exponential backoff",
                label, MAX_HANDLER_RETRIES
            )

    def _reset_pending_values(self, mode: str) -> None:
        """Reset pending values for a charge or discharge slot."""
        attributes = ["start", "end", "day_mask", "power_percent"]
        if mode.startswith("charge"):
            index = int(mode.replace("charge", "")) - 1
            for attr in attributes:
                self._pending_charges[index][attr] = None
        elif mode.startswith("discharge"):
            index = int(mode.replace("discharge", "")) - 1
            for attr in attributes:
                self._pending_discharges[index][attr] = None

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
        _LOGGER.debug(
            "[PENDING DEBUG] _update_day_mask_and_power called for %s. Provided day_mask: %s, power_percent: %s",
            label, day_mask, power_percent
        )
        try:
            _LOGGER.debug(
                "Reading current day_mask_power from address %s for %s",
                hex(address), label
            )
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
            _LOGGER.debug(
                "Current day_mask_power for %s: %s (day_mask: %s, power_percent: %s)",
                label, current_value, current_day_mask, current_power_percent
            )

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
                _LOGGER.debug(
                    "Using current power_percent: %s%% for %s",
                    current_power_percent, label
                )

            _LOGGER.debug(
                "Calculated new day_mask: %s, new_power_percent: %s for %s",
                new_day_mask, new_power_percent, label
            )

            combined_value = (new_day_mask << 8) | new_power_percent

            if combined_value == current_value:
                _LOGGER.info(
                    "No change detected for %s day_mask_power. Current value: %s. Not writing to Modbus.",
                    label, current_value
                )
                return

            _LOGGER.debug(
                "Writing combined value %s to register %s for %s",
                combined_value, hex(address), label
            )
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

    def _calculate_day_mask_power_value(self, day_mask: int, power_percent: Optional[int]) -> Optional[int]:
        """Calculate day_mask_power register value."""
        if power_percent is None:
            # Read current value to preserve power_percent
            return None  # Signal to read current value first

        return (day_mask << 8) | power_percent

    async def _write_time_register(
        self, address: int, time_str: str, label: str
    ) -> None:
        """Writes a time register in HH:MM format with exponential backoff retry."""
        parts = time_str.split(":")
        if len(parts) != 2:
            _LOGGER.error(
                "Invalid time format for %s: %s", label, time_str
            )
            return

        try:
            hours, minutes = map(int, parts)
        except ValueError:
            _LOGGER.error(
                "Non-integer time parts for %s: %s", label, time_str
            )
            return

        value = (hours << 8) | minutes
        success = await self._write_register_with_backoff(address, value, label)
        if success:
            _LOGGER.info(
                "Successfully set %s: %s", label, time_str
            )
        else:
            _LOGGER.error(
                "Failed to write %s", label
            )

    # ========== POWER STATE HANDLER (Charging/Discharging) ==========
    
    async def handle_charging_state(self) -> bool:
        """Handles the pending charging state with optimized time_enable handling."""
        _LOGGER.debug("handle_charging_state called")
        desired = self._pending_charging_state
        if desired is None:
            _LOGGER.debug("No pending charging state to handle")
            return False

        _LOGGER.debug(f"Processing pending charging state: {desired}")

        addr = REGISTERS["charging_state"]
        write_value = 1 if desired else 0

        _LOGGER.info(
            "Charging turned %s, writing %s to register 0x3604",
            "ON" if desired else "OFF", write_value
        )

        ok = await self._write_register_with_backoff(
            addr, write_value, "charging state (0x3604)"
        )
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3604")
            return False

        _LOGGER.info("Successfully wrote %s to register 0x3604", write_value)
        self.hub.inverter_data["charging_enabled"] = write_value

        # Update charge_time_enable in cache to reflect new state (same register)
        self.hub.inverter_data["charge_time_enable"] = write_value

        # Update time_enable cache to avoid duplicate writes
        self._time_enable_cache["charge_time_enable"] = write_value

        # Set locks to prevent overwrites for next 10 seconds
        import time as time_module
        self._charging_state_lock_until = time_module.monotonic() + 10.0
        self._charge_time_enable_lock_until = time_module.monotonic() + 10.0
        _LOGGER.debug(
            "[PENDING DEBUG] Updated cache after charging state: charge_time_enable = %s (LOCKED for 10s)",
            write_value
        )

        # Clear pending state
        self._pending_charging_state = None
        _LOGGER.debug("Cleared _pending_charging_state after successful write")

        # Get current discharging state from cache (not async call)
        dchg_value = self.hub.inverter_data.get("discharging_enabled", 0)
        dchg = bool(dchg_value > 0)

        # Update AppMode: 1 if ANY is enabled, 0 if BOTH are disabled
        await self._update_app_mode_from_states(charge_enabled=desired, discharge_enabled=dchg)

        # Force immediate data update to UI
        self.hub.async_set_updated_data(self.hub.inverter_data)

        return True

    async def handle_discharging_state(self) -> bool:
        """Handles the pending discharging state with optimized time_enable handling."""
        desired = self._pending_discharging_state
        if desired is None:
            return False

        _LOGGER.debug(f"Processing discharging state change: {desired}")

        addr = REGISTERS["discharging_state"]
        write_value = 0 if not desired else 1

        _LOGGER.info(
            "Discharging turned %s, writing %s to register 0x3605",
            "OFF" if not desired else "ON", write_value
        )

        ok = await self._write_register_with_backoff(
            addr, write_value, "discharging state (0x3605)"
        )
        if not ok:
            _LOGGER.error(f"Failed to write {write_value} to register 0x3605")
            return False

        _LOGGER.info("Successfully wrote %s to register 0x3605", write_value)
        self.hub.inverter_data["discharging_enabled"] = write_value

        # Update discharge_time_enable in cache to reflect new state (same register)
        self.hub.inverter_data["discharge_time_enable"] = write_value

        # Update time_enable cache to avoid duplicate writes
        self._time_enable_cache["discharge_time_enable"] = write_value

        # Set locks to prevent overwrites for next 10 seconds
        import time as time_module
        self._discharging_state_lock_until = time_module.monotonic() + 10.0
        self._discharge_time_enable_lock_until = time_module.monotonic() + 10.0
        _LOGGER.debug(
            "[PENDING DEBUG] Updated cache after discharging state: discharge_time_enable = %s (LOCKED for 10s)",
            write_value
        )

        # Clear pending state
        self._pending_discharging_state = None
        _LOGGER.debug("Cleared _pending_discharging_state after successful write")

        # Get current charging state from cache (not async call)
        chg_value = self.hub.inverter_data.get("charging_enabled", 0)
        chg = bool(chg_value > 0)

        # Update AppMode: 1 if ANY is enabled, 0 if BOTH are disabled
        await self._update_app_mode_from_states(charge_enabled=chg, discharge_enabled=desired)

        # Force immediate data update to UI
        self.hub.async_set_updated_data(self.hub.inverter_data)

        return True

    async def _update_app_mode_from_states(
        self,
        charge_enabled: bool,
        discharge_enabled: bool,
    ) -> None:
        """Update AppMode (0x3647) based on charging/discharging states."""
        desired_app_mode = 1 if (charge_enabled or discharge_enabled) else 0

        current_app_mode = self.hub.inverter_data.get("AppMode")

        if current_app_mode == desired_app_mode:
            _LOGGER.info(f"AppMode already at {desired_app_mode}, skipping write")
            return

        _LOGGER.info(
            "Updating AppMode from %s to %s (charge=%s, discharge=%s)",
            current_app_mode, desired_app_mode, charge_enabled, discharge_enabled
        )

        ok = await self._write_register_with_backoff(
            REGISTERS["app_mode"], desired_app_mode, "AppMode"
        )
        if ok:
            _LOGGER.info("Successfully set AppMode to %s", desired_app_mode)
            self.hub.inverter_data["AppMode"] = desired_app_mode
        else:
            _LOGGER.error(
                "Failed to write AppMode %s", desired_app_mode
            )

    # --- State Setters ---

    def set_pending(self, key: str, value: Any) -> None:
        """Generic setter for pending values."""
        # Handle array-based keys (e.g. charges[0][start])
        if "[" in key:
            # Parse charges[0][start] -> ['charges', '0', 'start']
            parts = key.replace("]", "").split("[")
            
            if len(parts) == 3:
                base = parts[0]
                try:
                    idx = int(parts[1])
                    field = parts[2]
                except ValueError:
                    _LOGGER.warning("Invalid index in pending key: %s", key)
                    return

                if base == "charges":
                    if 0 <= idx < 7 and field in CHARGE_PENDING_SUFFIXES:
                        self._pending_charges[idx][field] = value
                        self.invalidate_cache()
                        return
                elif base == "discharges":
                    if 0 <= idx < 7 and field in CHARGE_PENDING_SUFFIXES:
                        self._pending_discharges[idx][field] = value
                        self.invalidate_cache()
                        return
            else:
                _LOGGER.warning("Unexpected array key format: %s", key)

        # Handle simple attributes
        self._pending_simple[key] = value
        self.invalidate_cache()

    def set_charging_state(self, value: bool) -> None:
        self._pending_charging_state = value
        self.invalidate_cache()

    def set_discharging_state(self, value: bool) -> None:
        self._pending_discharging_state = value
        self.invalidate_cache()

    def invalidate_cache(self) -> None:
        self._pending_cache_valid = False

    def has_pending(self) -> bool:
        """Check if there are any pending settings."""
        if self._pending_cache_valid:
            return self._pending_cache

        has_pending = False

        # Check simple attributes
        if self._pending_simple:
            has_pending = True

        # Check power states
        if not has_pending:
            has_pending = (
                self._pending_charging_state is not None or
                self._pending_discharging_state is not None
            )

        # Check time enables
        if not has_pending:
            has_pending = (
                self._pending_charge_time_enable is not None or
                self._pending_discharge_time_enable is not None
            )

        # Check slots
        if not has_pending:
            has_pending = any(
                any(slot[suffix] is not None for suffix in CHARGE_PENDING_SUFFIXES)
                for slot in (self._pending_charges + self._pending_discharges)
            )

        self._pending_cache = has_pending
        self._pending_cache_valid = True
        return has_pending

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
        """Returns a data overlay with pending values applied."""
        if not current_data:
            return None

        base = dict(current_data)
        chg = base.get("charging_enabled")
        dchg = base.get("discharging_enabled")

        if self._pending_charging_state is not None:
            chg = 1 if self._pending_charging_state else 0
        if self._pending_discharging_state is not None:
            dchg = 1 if self._pending_discharging_state else 0

        app_mode = 1 if bool(chg) or bool(dchg) else 0

        overlay = dict(base)
        if chg is not None:
            overlay["charging_enabled"] = 1 if chg else 0
        if dchg is not None:
            overlay["discharging_enabled"] = 1 if dchg else 0
        overlay["AppMode"] = app_mode

        return overlay

    # --- Processing Logic (Moved from Hub) ---

    async def process_pending(self) -> None:
        """Process all pending settings."""
        if ADVANCED_LOGGING:
            _LOGGER.info("[ADVANCED] process_pending started")

        if not self.has_pending():
            return

        results = []

        # 1. Power States
        if self._pending_charging_state is not None:
            try:
                await self.handle_charging_state()
                results.append(("charging_state", True))
            except Exception as e:
                _LOGGER.error("Error setting charging state: %s", e)

        if self._pending_discharging_state is not None:
            try:
                await self.handle_discharging_state()
                results.append(("discharging_state", True))
            except Exception as e:
                _LOGGER.error("Error setting discharging state: %s", e)

        # 2. Slots
        charge_indices = [i for i, s in enumerate(self._pending_charges) if any(s.values())]
        discharge_indices = [i for i, s in enumerate(self._pending_discharges) if any(s.values())]

        slot_tasks = []
        for idx in charge_indices:
            slot_tasks.append(self.handle_charge_settings_by_index(idx + 1)) # 1-based
        for idx in discharge_indices:
            slot_tasks.append(self.handle_discharge_settings_by_index(idx + 1)) # 1-based

        if slot_tasks:
            await asyncio.gather(*slot_tasks, return_exceptions=True)

        # 3. Simple Attributes
        simple_tasks = []
        # Create a copy of keys to iterate safely
        simple_keys = list(self._pending_simple.keys())
        
        for key in simple_keys:
            simple_tasks.append(self._process_simple_setting(key))
        
        if simple_tasks:
            await asyncio.gather(*simple_tasks, return_exceptions=True)

        # Clear cache after processing
        self.invalidate_cache()