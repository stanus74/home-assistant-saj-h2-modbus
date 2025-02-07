"""SAJ Modbus Switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging

from .const import DOMAIN
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ switches from a config entry."""
    hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    
    entities = [
        SajChargingSwitch(hub, device_info)
    ]
    
    async_add_entities(entities)
    _LOGGER.info("Added SAJ switches")

class SajChargingSwitch(CoordinatorEntity, SwitchEntity):
    """Switch for controlling SAJ battery charging."""

    def __init__(self, hub: SAJModbusHub, device_info: dict):
        """Initialize the switch."""
        super().__init__(coordinator=hub)
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_charging_control"
        self._attr_name = f"{hub.name} Charging Control"
        self._attr_entity_registry_enabled_default = True
        self._hub = hub

    @property
    def is_on(self) -> bool:
        """Return true if charging is enabled."""
        return self._hub.data.get("charging_enabled", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on charging."""
        try:
            await self._hub.set_charging(True)
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Failed to turn on charging: {e}")
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off charging."""
        try:
            await self._hub.set_charging(False)
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off charging: {e}")
            raise

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
