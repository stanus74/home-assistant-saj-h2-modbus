import asyncio
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
        """Return true if switch is on.
        
        Uses cached derived state that checks BOTH raw register value AND AppMode (0x3647).
        This ensures the switch only shows "on" when BOTH conditions are met:
        - charging_enabled (0x3604) > 0 OR discharging_enabled (0x3605 bitmask) > 0
        - AppMode (0x3647) == 1
        
        This is a SYNCHRONOUS property and must not block - reads from cached inverter_data.
        """
        try:
            data = self._hub.inverter_data
            
            if self._switch_type == "charging":
                # Check BOTH charging_enabled (0x3604) AND AppMode (0x3647)
                charging_enabled = data.get("charging_enabled")
                app_mode = data.get("AppMode")
                
                if charging_enabled is None or app_mode is None:
                    return False
                
                return bool(charging_enabled > 0 and app_mode == 1)
                
            elif self._switch_type == "discharging":
                # Check BOTH discharging_enabled (0x3605 bitmask) AND AppMode (0x3647)
                discharging_enabled = data.get("discharging_enabled")
                app_mode = data.get("AppMode")
                
                if discharging_enabled is None or app_mode is None:
                    return False
                
                return bool(discharging_enabled > 0 and app_mode == 1)
                
        except Exception as e:
            _LOGGER.warning(f"Error getting {self._switch_type} state: {e}")
            return False
        
        # Fallback (should never reach here with current switch types)
        return False

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
        """Set the switch state with shared logic.
        
        Toggling on/off triggers pending settings processing in next update cycle.
        """
        if self.is_on == desired_state:
            _LOGGER.debug(f"{self._switch_type.capitalize()} already {'on' if desired_state else 'off'}")
            return

        if not self._allow_switch():
            return

        try:
            _LOGGER.debug(f"{self._switch_type.capitalize()} turned {'ON' if desired_state else 'OFF'}")
            
            # Set the state (charging_state or discharging_state)
            await getattr(self._hub, f"set_{self._switch_type}")(desired_state)
            
            self._last_switch_time = time.time()
            
            # Log pending value
            pending_attr = f"_pending_{self._switch_type}_state"
            pending_value = getattr(self._hub, pending_attr, None)
            _LOGGER.debug(f"Pending {pending_attr} set to: {pending_value}")
            
            # UI will show pending status via extra_state_attributes
            self.async_write_ha_state()
            _LOGGER.debug(
                f"Pending {self._switch_type} setting will be processed in next update cycle "
                     )
        except Exception as e:
            _LOGGER.error(f"Failed to set {self._switch_type} state: {e}")
            raise

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
