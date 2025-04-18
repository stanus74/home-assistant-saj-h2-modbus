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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ switches."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    async_add_entities([
        SajChargingSwitch(hub, hass.data[DOMAIN][entry.entry_id]["device_info"]),
        SajDischargingSwitch(hub, hass.data[DOMAIN][entry.entry_id]["device_info"])
    ])
    _LOGGER.info("Added SAJ switches")

class SajChargingSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, hub: SAJModbusHub, device_info):
        super().__init__(hub)  # This now correctly references a DataUpdateCoordinator
        self._hub = hub
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_charging_control"
        self._attr_name = f"{hub.name} Charging Control"
        self._attr_entity_registry_enabled_default = True
        self._last_switch_time = 0  # Time of last switch
        self._switch_timeout = 2  # Time lock in seconds
        self._last_state = None  # Speichert den letzten bekannten Zustand

    @property
    def is_on(self) -> bool:
        """Check if charging is enabled."""
        current_state = self._hub.data.get("charging_enabled", False)
        # Aktualisiere den letzten bekannten Zustand
        if self._last_state != current_state:
            self._last_state = current_state
        return current_state

    async def async_turn_on(self, **kwargs) -> None:
        """Enable charging."""
        if self.is_on: _LOGGER.debug("Charging already on"); return
        
        # Check if the time lock is active
        current_time = time.time()
        time_since_last_switch = current_time - self._last_switch_time
        
        if time_since_last_switch < self._switch_timeout:
            remaining_time = round(self._switch_timeout - time_since_last_switch, 1)
            _LOGGER.warning(f"Time lock active! Please wait {remaining_time} seconds before the next switching operation.")
            return
            
        try:
            await self._hub.set_charging(True)
            self._last_switch_time = time.time()  # Update time
            self._last_state = True  # Aktualisiere den letzten bekannten Zustand
            self.async_write_ha_state()  # Ensure UI updates
        except Exception as e:
            _LOGGER.error(f"Turn on failed: {e}")
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Disable charging."""
        if not self.is_on: _LOGGER.debug("Charging already off"); return
        
        # Check if the time lock is active
        current_time = time.time()
        time_since_last_switch = current_time - self._last_switch_time
        
        if time_since_last_switch < self._switch_timeout:
            remaining_time = round(self._switch_timeout - time_since_last_switch, 1)
            _LOGGER.warning(f"Time lock active! Please wait {remaining_time} seconds before the next switching operation.")
            return
            
        try:
            await self._hub.set_charging(False)
            self._last_switch_time = time.time()  # Update time
            self._last_state = False  # Aktualisiere den letzten bekannten Zustand
            self.async_write_ha_state()  # Ensure UI updates
        except Exception as e:
            _LOGGER.error(f"Turn off failed: {e}")
            raise

    @property
    def available(self) -> bool:
        """Check entity availability."""
        return self.coordinator.last_update_success


class SajDischargingSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, hub: SAJModbusHub, device_info):
        super().__init__(hub)  # This now correctly references a DataUpdateCoordinator
        self._hub = hub
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_discharging_control"
        self._attr_name = f"{hub.name} Discharging Control"
        self._attr_entity_registry_enabled_default = True
        self._last_switch_time = 0  # Time of last switch
        self._switch_timeout = 2  # Time lock in seconds
        self._last_state = None  # Speichert den letzten bekannten Zustand

    @property
    def is_on(self) -> bool:
        """Check if discharging is enabled."""
        current_state = self._hub.data.get("discharging_enabled", False)
        # Aktualisiere den letzten bekannten Zustand
        if self._last_state != current_state:
            self._last_state = current_state
        return current_state

    async def async_turn_on(self, **kwargs) -> None:
        """Enable discharging."""
        if self.is_on: _LOGGER.debug("Discharging already on"); return
        
        # Check if the time lock is active
        current_time = time.time()
        time_since_last_switch = current_time - self._last_switch_time
        
        if time_since_last_switch < self._switch_timeout:
            remaining_time = round(self._switch_timeout - time_since_last_switch, 1)
            _LOGGER.warning(f"Time lock active! Please wait {remaining_time} seconds before the next switching operation.")
            return
            
        try:
            # Use the new set_discharging method
            await self._hub.set_discharging(True)
            self._last_switch_time = time.time()  # Update time
            self._last_state = True  # Aktualisiere den letzten bekannten Zustand
            self.async_write_ha_state()  # Ensure UI updates
        except Exception as e:
            _LOGGER.error(f"Turn on failed: {e}")
            raise

    async def async_turn_off(self, **kwargs) -> None:
        """Disable discharging."""
        if not self.is_on: _LOGGER.debug("Discharging already off"); return
        
        # Check if the time lock is active
        current_time = time.time()
        time_since_last_switch = current_time - self._last_switch_time
        
        if time_since_last_switch < self._switch_timeout:
            remaining_time = round(self._switch_timeout - time_since_last_switch, 1)
            _LOGGER.warning(f"Time lock active! Please wait {remaining_time} seconds before the next switching operation.")
            return
            
        try:
            # Use the new set_discharging method
            await self._hub.set_discharging(False)
            self._last_switch_time = time.time()  # Update time
            self._last_state = False  # Aktualisiere den letzten bekannten Zustand
            self.async_write_ha_state()  # Ensure UI updates
        except Exception as e:
            _LOGGER.error(f"Turn off failed: {e}")
            raise

    @property
    def available(self) -> bool:
        """Check entity availability."""
        return self.coordinator.last_update_success
