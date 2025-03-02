import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ switches."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    async_add_entities([SajChargingSwitch(hub, hass.data[DOMAIN][entry.entry_id]["device_info"])])
    _LOGGER.info("Added SAJ switches")

class SajChargingSwitch(CoordinatorEntity, SwitchEntity):
    """SAJ battery charging switch."""
    def __init__(self, hub, device_info):
        super().__init__(hub)
        self._hub = hub
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_charging_control"
        self._attr_name = f"{hub.name} Charging Control"
        self._attr_entity_registry_enabled_default = True

    @property
    def is_on(self) -> bool:
        """Check if charging is enabled."""
        return self._hub.data.get("charging_enabled", False)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charging."""
        if self.is_on: _LOGGER.debug("Charging already on"); return
        try:
            await self._hub.set_charging(True)
            await self._hub.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Turn on failed: {e}")
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charging."""
        if not self.is_on: _LOGGER.debug("Charging already off"); return
        try:
            await self._hub.set_charging(False)
            await self._hub.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Turn off failed: {e}")
            raise

    async def _update_state(self) -> None:
        """Update switch state."""
        try:
            state = await self._hub.get_charging_state()
            _LOGGER.debug(f"Charging state: {state}")
            self._hub.data["charging_enabled"] = state
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Update failed: {e}")

    @property
    def available(self) -> bool:
        """Check entity availability."""
        return self.coordinator.last_update_success