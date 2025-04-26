import logging
from typing import Optional, Any, List, Dict, Tuple, Callable, Awaitable
from .modbus_utils import try_read_registers, try_write_registers

_LOGGER = logging.getLogger(__name__)

# --- Definitionen für Pending-Setter ---
PENDING_FIELDS: List[tuple[str, str]] = [
    ("charge_start", "charge_start"),
    ("charge_end", "charge_end"),
    ("charge_day_mask", "charge_day_mask"),
    ("charge_power_percent", "charge_power_percent"),
    ("discharge_start", "discharge_start"),
    ("discharge_end", "discharge_end"),
    ("discharge_day_mask", "discharge_day_mask"),
    ("discharge_power_percent", "discharge_power_percent"),
    ("export_limit", "export_limit"),
    ("charging", "charging_state"),
    ("discharging", "discharging_state"),
    ("app_mode", "app_mode"),
]

# --- Register-Definitionen ---
REGISTERS = {
    "charge": {
        "start_time": 0x3606,
        "end_time": 0x3607,
        "day_mask_power": 0x3608,
    },
    "discharge": {
        "start_time": 0x361B,
        "end_time": 0x361C,
        "day_mask_power": 0x361D,
    },
    "export_limit": 0x365A,
    "app_mode": 0x3647,
    "charging_state": 0x3604,
    "discharging_state": 0x3605,
}


def make_pending_setter(setter_name: str, attr_suffix: str):
    """
    Factory: returns an async method that sets self._pending_<attr_suffix> = value.
    """
    async def setter(self, value: Any) -> None:
        setattr(self, f"_pending_{attr_suffix}", value)
    setter.__name__ = f"set_{setter_name}"
    return setter


class ChargeSettingHandler:
    def __init__(self, hub):
        self._hub = hub

    async def handle_charge_settings(self) -> None:
        """Verarbeitet die Lade-Einstellungen"""
        await self._handle_power_settings(
            "charge",
            self._hub._pending_charge_start,
            self._hub._pending_charge_end,
            self._hub._pending_charge_day_mask,
            self._hub._pending_charge_power_percent,
            "charge"
        )

    async def handle_discharge_settings(self) -> None:
        """Verarbeitet die Entlade-Einstellungen"""
        await self._handle_power_settings(
            "discharge",
            self._hub._pending_discharge_start,
            self._hub._pending_discharge_end,
            self._hub._pending_discharge_day_mask,
            self._hub._pending_discharge_power_percent,
            "discharge"
        )

    async def _handle_power_settings(
        self, 
        mode: str, 
        start_time: Optional[str], 
        end_time: Optional[str],
        day_mask: Optional[int],
        power_percent: Optional[int],
        label: str
    ) -> None:
        """
        Gemeinsame Methode zur Verarbeitung von Lade- und Entlade-Einstellungen
        """
        try:
            registers = REGISTERS[mode]
            
            # Startzeit setzen
            if start_time is not None:
                await self._write_time_register(
                    registers["start_time"],
                    start_time,
                    f"{label} start time",
                )

            # Endzeit setzen
            if end_time is not None:
                await self._write_time_register(
                    registers["end_time"],
                    end_time,
                    f"{label} end time",
                )

            # Tagesmaske und Leistungsprozent setzen
            if day_mask is not None or power_percent is not None:
                await self._update_day_mask_and_power(
                    registers["day_mask_power"],
                    day_mask,
                    power_percent,
                    label
                )
        except Exception as e:
            _LOGGER.error(f"Error writing {label} settings: {e}")
        finally:
            # Zurücksetzen der Pending-Werte
            self._reset_pending_values(mode)

    async def _update_day_mask_and_power(
        self, 
        address: int, 
        day_mask: Optional[int], 
        power_percent: Optional[int],
        label: str
    ) -> None:
        """Aktualisiert die Tagesmaske und den Leistungsprozentsatz"""
        regs = await self._hub._read_registers(address)
        current_value = regs[0]
        current_day_mask = (current_value >> 8) & 0xFF
        current_power_percent = current_value & 0xFF

        new_day_mask = day_mask if day_mask is not None else current_day_mask
        new_power_percent = power_percent if power_percent is not None else current_power_percent

        value = (new_day_mask << 8) | new_power_percent
        success = await self._hub._write_register(address, value)
        
        if success:
            _LOGGER.info(
                f"Successfully set {label} power time: day_mask={new_day_mask}, power_percent={new_power_percent}"
            )
        else:
            _LOGGER.error(f"Failed to write {label} power time")

    def _reset_pending_values(self, mode: str) -> None:
        """Setzt die Pending-Werte zurück"""
        if mode == "charge":
            self._hub._pending_charge_start = None
            self._hub._pending_charge_end = None
            self._hub._pending_charge_day_mask = None
            self._hub._pending_charge_power_percent = None
        elif mode == "discharge":
            self._hub._pending_discharge_start = None
            self._hub._pending_discharge_end = None
            self._hub._pending_discharge_day_mask = None
            self._hub._pending_discharge_power_percent = None

    async def handle_export_limit(self) -> None:
        """Verarbeitet das Export-Limit"""
        await self._handle_simple_register(
            self._hub._pending_export_limit,
            REGISTERS["export_limit"],
            "export limit",
            lambda: setattr(self._hub, "_pending_export_limit", None)
        )
                
    async def handle_app_mode(self) -> None:
        """Verarbeitet den App-Modus"""
        await self._handle_simple_register(
            self._hub._pending_app_mode,
            REGISTERS["app_mode"],
            "app mode",
            lambda: setattr(self._hub, "_pending_app_mode", None)
        )

    async def _handle_simple_register(
        self, 
        value: Optional[Any], 
        address: int, 
        label: str,
        reset_callback: Callable[[], None]
    ) -> None:
        """Verarbeitet einfache Register-Schreibvorgänge"""
        if value is not None:
            try:
                success = await self._hub._write_register(address, value)
                if success:
                    _LOGGER.info(f"Successfully set {label} to: {value}")
                else:
                    _LOGGER.error(f"Failed to write {label}")
            except Exception as e:
                _LOGGER.error(f"Error writing {label}: {e}")
            finally:
                reset_callback()

    async def handle_pending_charging_state(self) -> None:
        """Verarbeitet den ausstehenden Ladezustand"""
        await self._handle_power_state(
            self._hub._pending_charging_state,
            self._hub.get_discharging_state,
            REGISTERS["charging_state"],
            "charging",
            lambda: setattr(self._hub, "_pending_charging_state", None)
        )

    async def handle_pending_discharging_state(self) -> None:
        """Verarbeitet den ausstehenden Entladezustand"""
        await self._handle_power_state(
            self._hub._pending_discharging_state,
            self._hub.get_charging_state,
            REGISTERS["discharging_state"],
            "discharging",
            lambda: setattr(self._hub, "_pending_discharging_state", None)
        )

    async def _handle_power_state(
        self, 
        state: Optional[bool], 
        get_other_state: Callable[[], Awaitable[bool]],
        state_register: int,
        label: str,
        reset_callback: Callable[[], None]
    ) -> None:
        """Gemeinsame Methode zur Verarbeitung von Lade- und Entladezuständen"""
        if state is not None:
            other_state = await get_other_state()
            try:
                # App-Modus-Register setzen (0x3647)
                app_mode_value = 1 if state or other_state else 0
                success_app_mode = await self._hub._write_register(REGISTERS["app_mode"], app_mode_value)
                if success_app_mode:
                    _LOGGER.info(f"Successfully set {label} (0x3647) to: {app_mode_value}")
                else:
                    _LOGGER.error(f"Failed to set {label} state (0x3647)")

                # Zustandsregister setzen
                reg_value = 1 if state else 0
                success_state = await self._hub._write_register(state_register, reg_value)
                if success_state:
                    _LOGGER.info(f"Successfully set register {hex(state_register)} to {reg_value}")
                else:
                    _LOGGER.error(f"Failed to set register {hex(state_register)}")
            except Exception as e:
                _LOGGER.error(f"Error handling pending {label} state: {e}")
            finally:
                reset_callback()

    async def _write_time_register(
        self, address: int, time_str: str, label: str
    ) -> None:
        """Schreibt ein Zeitregister im Format HH:MM"""
        parts = time_str.split(":")
        if len(parts) != 2:
            _LOGGER.error(f"Invalid time format for {label}: {time_str}")
            return

        try:
            hours, minutes = map(int, parts)
        except ValueError:
            _LOGGER.error(f"Non-integer time parts for {label}: {time_str}")
            return

        value = (hours << 8) | minutes
        success = await self._hub._write_register(address, value)
        if success:
            _LOGGER.info(f"Successfully set {label}: {time_str}")
        else:
            _LOGGER.error(f"Failed to write {label}")
