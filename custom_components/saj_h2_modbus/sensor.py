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
    entities = [SajSensor(hub_name, hub, device_info, desc) for desc in SENSOR_TYPES.values()]
    async_add_entities(entities)

class SajSensor(CoordinatorEntity, SensorEntity):
    """Representation of an SAJ Modbus sensor."""

    def __init__(self, platform_name: str, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription):
        """Initialize the sensor."""
        self.attr_device_info = device_info
        self.entity_description = description
        super().__init__(coordinator=hub)
        self._attr_name = f"{platform_name} {description.name}"
        self._attr_unique_id = f"{platform_name}_{description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
