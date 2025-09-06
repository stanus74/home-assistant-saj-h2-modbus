"""SAJ Modbus Hub."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
import logging

from .const import DOMAIN, SENSOR_TYPES, SajModbusSensorEntityDescription
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

FAST_UPDATE_SENSOR_KEYS = [
    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower",
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ sensors from a config entry."""
    hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    
    entities = []
    for description in SENSOR_TYPES.values():
        # Wenn der Fast-Coordinator deaktiviert/keiner vorhanden ist,
        # binden Fast-Sensoren automatisch an den Main-Coordinator.
        if description.key in FAST_UPDATE_SENSOR_KEYS and getattr(hub, "_fast_coordinator", None) is not None:
            coordinator = hub._fast_coordinator
        else:
            coordinator = hub
        entity = SajSensor(coordinator, device_info, description)
        entities.append(entity)

    async_add_entities(entities)
    _LOGGER.info(f"Added {len(entities)} SAJ sensors")

class SajSensor(CoordinatorEntity, SensorEntity):
    """Representation of an SAJ Modbus sensor."""

    def __init__(self, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription):
        """Initialize the sensor."""
        super().__init__(coordinator=hub)
        self.entity_description = description
        self._attr_device_info = device_info
        # Stabile unique_id: unabhängig vom Coordinator-Namen
        device_name = device_info.get("name", "SAJ")
        self._attr_unique_id = f"{device_name}_{description.key}"
        # WICHTIG: Bei has_entity_name=True KEIN Gerätepräfix im Namen!
        # HA zeigt automatisch "<Gerätename> <Entitätsname>" an.
        self._attr_name = description.name
        # Empfohlener Core-Standard: Entities haben Eigennamen
        self._attr_has_entity_name = True
        self._attr_entity_registry_enabled_default = description.entity_registry_enabled_default
        self._attr_force_update = description.force_update

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            _LOGGER.debug(f"No data for sensor {self._attr_name}")
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # _LOGGER.debug(f"Sensor {self._attr_name} added to Home Assistant")
