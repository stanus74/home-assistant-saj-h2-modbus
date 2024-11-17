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
    _LOGGER.debug("Setting up SAJ sensors for entry: %s", entry.entry_id)

    try:
        hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]
        device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

        entities = []
        for description in SENSOR_TYPES.values():
            _LOGGER.debug(
                "Creating sensor: name=%s, key=%s, unit=%s",
                description.name,
                description.key,
                description.native_unit_of_measurement,
            )
            entity = SajSensor(hub, device_info, description)
            entities.append(entity)

        async_add_entities(entities)
        _LOGGER.info("Added %d SAJ sensors", len(entities))
    except KeyError as e:
        _LOGGER.error("KeyError while setting up SAJ sensors: %s", e)
    except Exception as e:
        _LOGGER.error("Unexpected error in async_setup_entry: %s", e)


class SajSensor(CoordinatorEntity, SensorEntity):
    """Representation of an SAJ Modbus sensor."""

    def __init__(self, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator=hub)
        self.entity_description = description
        self._attr_device_info = device_info
        self._attr_unique_id = f"{hub.name}_{description.key}"
        self._attr_name = description.name
        # Hinzufügen des Präfixes `saj_` vor dem key
        self.entity_id = f"sensor.saj_{description.key}"

        


    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            _LOGGER.debug("No data available for sensor: %s", self.entity_id)
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        _LOGGER.debug("Sensor %s state updated", self.entity_id)

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
        _LOGGER.debug("Sensor %s added to Home Assistant", self.entity_id)

    async def async_update(self) -> None:
        """Update the entity."""
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Sensor %s requested a data refresh", self.entity_id)
