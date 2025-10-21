import logging
import time
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

SWITCH_DEFINITIONS = [
    {
        "key": "charging",
        "name": "Charging",
        "unique_id_suffix": "_control"
    },
    {
        "key": "discharging",
        "name": "Discharging",
        "unique_id_suffix": "_control"
    },
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ switches."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = []
    for desc in SWITCH_DEFINITIONS:
        entity = BaseSajSwitch(
            hub=hub,
            device_info=device_info,
            switch_type=desc["key"]
        )
        entities.append(entity)

    async_add_entities(entities)
    _LOGGER.info("Added SAJ switches")

class BaseSajSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, hub: SAJModbusHub, device_info, switch_type: str):
        super().__init__(hub)
        self._hub = hub
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_{switch_type}{SWITCH_DEFINITIONS[0]['unique_id_suffix'] if switch_type == 'charging' else SWITCH_DEFINITIONS[1]['unique_id_suffix']}"
        self._attr_name = f"{hub.name} {switch_type.capitalize()} Control"
        self._attr_entity_registry_enabled_default = True
        self._attr_assumed_state = True
        self._attr_should_poll = False
        self._last_switch_time = 0
        self._switch_timeout = 2
        self._switch_type = switch_type

    @property
    def is_on(self) -> bool:
        # Use coordinator.data which will fall back to inverter_data if None
        coordinator_data = self.coordinator.data
        if coordinator_data is None:
            coordinator_data = self._hub.inverter_data
        return coordinator_data.get(f"{self._switch_type}_enabled", False)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        pending = getattr(self._hub, f"_pending_{self._switch_type}_state", None)
        return {
            "pending_write": pending is not None
        }

    async def _set_state(self, desired_state: bool) -> None:
        """Set the switch state with shared logic."""
        if self.is_on == desired_state:
            _LOGGER.debug(f"{self._switch_type.capitalize()} already {'on' if desired_state else 'off'}")
            return

        if not self._allow_switch():
            return

        try:
            _LOGGER.debug(f"Calling set_{self._switch_type}({desired_state}) on hub")
            
            # First, set the switch state
            await getattr(self._hub, f"set_{self._switch_type}")(desired_state)
            
            # Then, when enabling, ensure default values are set if not already configured
            # This ensures power values are set AFTER the switch state, so they are processed together
            if desired_state:
                await self._ensure_default_values()
            
            self._last_switch_time = time.time()
            _LOGGER.debug(f"{self._switch_type.capitalize()} turned {'ON' if desired_state else 'OFF'}")
            # Check if pending value was set
            pending_attr = f"_pending_{self._switch_type}_state"
            pending_value = getattr(self._hub, pending_attr, None)
            _LOGGER.debug(f"Pending {pending_attr} set to: {pending_value}")
            
            # Update UI state to show pending write - will be processed in next 60s cycle
            self.async_write_ha_state()
            _LOGGER.debug(f"Pending {self._switch_type} setting will be processed in next 60s cycle")
        except Exception as e:
            _LOGGER.error(f"Failed to turn {'on' if desired_state else 'off'}: {e}")
            raise

    async def _ensure_default_values(self) -> None:
        """Ensure default time and power values are set when enabling."""
        if self._switch_type == "charging":
            # Set default charge times and power if not already set
            if getattr(self._hub, "_pending_charge_start", None) is None:
                await self._hub.set_charge_start("01:00")
            if getattr(self._hub, "_pending_charge_end", None) is None:
                await self._hub.set_charge_end("01:10")
            if getattr(self._hub, "_pending_charge_power_percent", None) is None:
                await self._hub.set_charge_power_percent(5)
            _LOGGER.info("Set default charging values: 01:00-01:10, 5%")
        elif self._switch_type == "discharging":
            # For discharging, set defaults for enabled slots
            time_enable = self._hub.inverter_data.get("discharge_time_enable", 0)
            if isinstance(time_enable, str):
                time_enable = int(time_enable)
            
            _LOGGER.info(f"Ensuring values for enabled discharge slots (time_enable={time_enable})")
            
            # First check if _pending_discharges is initialized
            if not hasattr(self._hub, "_pending_discharges") or self._hub._pending_discharges is None:
                _LOGGER.warning("_pending_discharges not found on hub, cannot set default values")
                return
                
            for i in range(7):
                if time_enable & (1 << i):  # Slot is enabled
                    _LOGGER.debug(f"Ensuring values for enabled slot {i+1}")
                    
                    # Check if slot dictionary exists in the pending discharges list
                    if i >= len(self._hub._pending_discharges) or not isinstance(self._hub._pending_discharges[i], dict):
                        _LOGGER.warning(f"Slot {i+1} pending data not properly initialized, skipping defaults")
                        continue
                        
                    # Check if slot has any pending values already set (from Card)
                    slot = self._hub._pending_discharges[i]
                    has_pending = any(slot.get(key) is not None for key in ["start", "end", "power_percent", "day_mask"])
                    
                    # Check current values from inverter_data
                    current_start = self._hub.inverter_data.get(f"discharge{i+1}_start", "00:00")
                    current_end = self._hub.inverter_data.get(f"discharge{i+1}_end", "00:00")
                    current_power = self._hub.inverter_data.get(f"discharge{i+1}_power_percent", 5)
                    current_mask = self._hub.inverter_data.get(f"discharge{i+1}_day_mask", 127)  # Default all days
                    
                    # If no pending values and slot is enabled, use current values or defaults
                    if not has_pending:
                        _LOGGER.info(f"No pending values for slot {i+1}, setting current values as pending")
                        
                        # Safely call setter methods with error handling
                        try:
                            # Always set at least these minimal values to ensure writing happens
                            await getattr(self._hub, f"set_discharge{i+1}_start")(current_start)
                            await getattr(self._hub, f"set_discharge{i+1}_end")(current_end)
                            await getattr(self._hub, f"set_discharge{i+1}_power_percent")(current_power)
                            await getattr(self._hub, f"set_discharge{i+1}_day_mask")(current_mask)
                            
                            _LOGGER.info(f"Set values for slot {i+1}: {current_start}-{current_end}, {current_power}%, mask={current_mask}")
                        except AttributeError as e:
                            _LOGGER.error(f"Missing setter method for slot {i+1}: {e}")
                        except Exception as e:
                            _LOGGER.error(f"Error setting default values for slot {i+1}: {e}")
                    else:
                        _LOGGER.info(f"Slot {i+1} already has pending values: {slot}")
                        
                        # Ensure at least power is set (the card's default value)
                        if slot.get("power_percent") is None:
                            try:
                                await getattr(self._hub, f"set_discharge{i+1}_power_percent")(5)
                                _LOGGER.info(f"Set default power for discharge slot {i+1}: 5%")
                            except Exception as e:
                                _LOGGER.error(f"Error setting default power for discharge slot {i+1}: {e}")

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)

    def _allow_switch(self) -> bool:
        current_time = time.time()
        elapsed = current_time - self._last_switch_time
        if elapsed < self._switch_timeout:
            remaining = round(self._switch_timeout - elapsed, 1)
            _LOGGER.warning(f"Time lock active! Wait {remaining}s before switching {self._switch_type} again.")
            return False
        return True
