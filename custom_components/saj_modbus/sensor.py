"""SAJ Modbus Hub."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

from .const import DOMAIN, SENSOR_TYPES, SajModbusSensorEntityDescription
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ sensors from a config entry."""
    hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    
    entities = []
    for description in SENSOR_TYPES.values():
        try:
            entity = SajSensor(hub, device_info, description)
            entities.append(entity)
        except Exception as e:
            _LOGGER.error(f"Error creating sensor {description.name}: {str(e)}")

    async_add_entities(entities)
    _LOGGER.info(f"Added {len(entities)} SAJ sensors")

class SajSensor(CoordinatorEntity, SensorEntity):
    """Representation of an SAJ Modbus sensor."""

    def __init__(self, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator=hub)
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_{description.key}"
        self._attr_name = f"{hub.name} {description.name}"
        _LOGGER.debug(f"Initialized sensor: {self._attr_name}")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        try:
            value = self.coordinator.data.get(self.entity_description.key)
            if value is not None:
                _LOGGER.debug(f"Sensor {self._attr_name} updated with value: {value}")
            else:
                _LOGGER.warning(f"No data for sensor {self._attr_name}")
            return value
        except Exception as e:
            _LOGGER.error(f"Error getting native value for {self._attr_name}: {str(e)}")
            return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        is_available = self.coordinator.last_update_success and self.native_value is not None
        _LOGGER.debug(f"Sensor {self._attr_name} availability: {is_available}")
        return is_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        _LOGGER.debug(f"Sensor {self._attr_name} state updated")

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug(f"Sensor {self._attr_name} added to Home Assistant")

    async def async_update(self) -> None:
        """Update the entity."""
        await self.coordinator.async_request_refresh()
        if self.native_value is None:
            _LOGGER.warning(f"Sensor {self._attr_name} failed to update")
        else:
            _LOGGER.debug(f"Sensor {self._attr_name} updated successfully")

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        _LOGGER.debug(f"Sensor {self._attr_name} removed from Home Assistant")
