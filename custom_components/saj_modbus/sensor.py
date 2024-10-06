"""SAJ Modbus Hub."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
import logging

from .const import ATTR_MANUFACTURER, DOMAIN, SENSOR_TYPES, SajModbusSensorEntityDescription
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up SAJ sensors from a config entry."""
    hub_name = entry.data[CONF_NAME]
    hub: SAJModbusHub = hass.data[DOMAIN][hub_name]["hub"]
    device_info = {"identifiers": {(DOMAIN, hub_name)}, "name": hub_name, "manufacturer": ATTR_MANUFACTURER}
    
    entities = []
    for desc in SENSOR_TYPES.values():
        try:
            entity = SajSensor(hub_name, hub, device_info, desc)
            entities.append(entity)
        except Exception as e:
            _LOGGER.error(f"Error creating sensor {desc.name}: {str(e)}")
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"Added {len(entities)} SAJ sensors")
    else:
        _LOGGER.warning("No SAJ sensors were added")

class SajSensor(CoordinatorEntity, SensorEntity):
    """Representation of an SAJ Modbus sensor."""

    def __init__(self, platform_name: str, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription):
        """Initialize the sensor."""
        self.attr_device_info = device_info
        self.entity_description = description
        super().__init__(coordinator=hub)
        self._attr_name = f"{platform_name} {description.name}"
        self._attr_unique_id = f"{platform_name}_{description.key}"
        _LOGGER.debug(f"Initialized sensor: {self._attr_name}")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            _LOGGER.warning(f"No data for sensor {self._attr_name}")
        return value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.native_value is not None

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()
        _LOGGER.info(f"Sensor {self._attr_name} added to Home Assistant and refresh triggered.")

        
    async def async_will_remove_from_hass(self):
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        _LOGGER.info(f"Sensor {self._attr_name} removed from Home Assistant")

    def force_update(self):
        """Force update of the sensor."""
        self.async_write_ha_state()
        _LOGGER.debug(f"Forced update of sensor {self._attr_name}")
