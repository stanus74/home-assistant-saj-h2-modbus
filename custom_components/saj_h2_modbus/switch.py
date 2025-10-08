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
        return self._hub.data.get(f"{self._switch_type}_enabled", False)

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
            await getattr(self._hub, f"set_{self._switch_type}")(desired_state)
            self._last_switch_time = time.time()
            _LOGGER.debug(f"{self._switch_type.capitalize()} turned {'ON' if desired_state else 'OFF'}")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn {'on' if desired_state else 'off'}: {e}")
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
