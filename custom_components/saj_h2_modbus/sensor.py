"""SAJ Modbus Hub."""
from typing import Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

from .const import DOMAIN, SENSOR_TYPES, SajModbusSensorEntityDescription
from .hub import SAJModbusHub, FAST_POLL_SENSORS, ADVANCED_LOGGING

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up SAJ sensors from a config entry."""
    hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    
    entities = []
    for description in SENSOR_TYPES.values():
        if description.key in FAST_POLL_SENSORS:
            # Create BOTH entities for fast-poll sensors:
            # 1. Normal entity (60s, with DB recording)
            # 2. Fast entity (10s, no DB recording) with "fast_" prefix
            entities.append(SajSensor(hub, device_info, description, is_fast_variant=False))
            entities.append(FastPollSensor(hub, device_info, description, is_fast_variant=True))
        else:
            # Regular sensors only have one entity (60s, with DB)
            entities.append(SajSensor(hub, device_info, description, is_fast_variant=False))

    async_add_entities(entities)
    fast_count = sum(1 for e in entities if isinstance(e, FastPollSensor))
    normal_count = len(entities) - fast_count
    _LOGGER.info("Added SAJ sensors (%d normal, %d fast-variants)", normal_count, fast_count)

class SajSensor(CoordinatorEntity, SensorEntity):
    """Base class for SAJ Modbus sensors."""

    def __init__(self, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription, is_fast_variant: bool = False):
        """Initialize the sensor."""
        super().__init__(coordinator=hub)
        
        self.entity_description = description
        self._attr_device_info = device_info
        self._hub = hub
        self._is_fast_variant = is_fast_variant
        
        # Stable unique_id: independent of coordinator name
        device_name = device_info.get("name", "SAJ")
        
        if is_fast_variant:
            # Fast variant has "fast_" prefix
            self._attr_unique_id = f"{device_name}_fast_{description.key}"
            self._attr_name = f"Fast {description.name}"
        else:
            self._attr_unique_id = f"{device_name}_{description.key}"
            self._attr_name = description.name
        
        self._attr_has_entity_name = True
        self._attr_entity_registry_enabled_default = description.entity_registry_enabled_default
        self._attr_force_update = description.force_update
        
        # Determine if this is a fast-poll sensor using FAST_POLL_SENSORS from hub
        # Only fast variants should register for fast updates
        self._is_fast_sensor = (description.key in FAST_POLL_SENSORS) and is_fast_variant
        self._remove_fast_listener = None
        self._on_remove_cleanup_registered = False
        self._last_value = None  # Cache last value for change detection
        # Flag to prevent race conditions during entity removal
        self._is_removed = False

        if ADVANCED_LOGGING and self._is_fast_sensor:
            _LOGGER.debug("Sensor %s (key: %s) marked as fast-poll sensor", self._attr_name, description.key)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self._hub.inverter_data.get(self.entity_description.key)
        if value is None and ADVANCED_LOGGING:
            _LOGGER.debug(
                "No data available for sensor type: %s", self.entity_description.key
            )
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        if not self._on_remove_cleanup_registered:
            self.async_on_remove(self._cleanup_fast_listener)
            self._on_remove_cleanup_registered = True

        # Initial registration check
        self._update_fast_listener_registration()

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        self._cleanup_fast_listener()

        await super().async_will_remove_from_hass()
        _LOGGER.debug("Sensor %s fully removed from hass", self._attr_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the main coordinator."""
        # Check if fast listener registration needs to change (e.g. config changed)
        self._update_fast_listener_registration()

        # Update cached value and write state
        # For fast sensors, this runs at normal interval (e.g., 60s)
        # For regular sensors, this is their only update mechanism
        self._last_value = self.native_value
        self.async_write_ha_state()

    @callback
    def _update_fast_listener_registration(self) -> None:
        """Register or unregister fast listener based on current hub config."""
        if not self._is_fast_sensor:
            return

        should_listen = self._hub.fast_enabled
        is_listening = self._remove_fast_listener is not None

        if should_listen and not is_listening:
            self._remove_fast_listener = self._hub.async_add_fast_listener(
                self._handle_fast_update
            )
            if ADVANCED_LOGGING:
                _LOGGER.debug("Sensor %s registered for fast updates (10s)", self._attr_name)
        elif not should_listen and is_listening:
            if self._remove_fast_listener:
                try:
                    self._remove_fast_listener()
                    if ADVANCED_LOGGING:
                        _LOGGER.debug("Sensor %s unregistered from fast updates", self._attr_name)
                except Exception as e:
                    _LOGGER.warning("Error unregistering fast listener for %s: %s", self._attr_name, e)
                finally:
                    self._remove_fast_listener = None

    @callback
    def _handle_fast_update(self) -> None:
        """Handle fast update notification (10s interval)."""
        # Prevent processing if the entity has been removed or is disabled
        is_enabled = True
        if self.registry_entry is not None:
            is_enabled = not self.registry_entry.disabled

        if self._is_removed or not is_enabled:
            _LOGGER.debug(
                "Skipping fast update for %s (removed=%s, enabled=%s)",
                self._attr_name,
                self._is_removed,
                is_enabled,
            )
            return

        # This is ONLY called for sensors registered in FAST_POLL_SENSORS
        new_value = self._hub.inverter_data.get(self.entity_description.key)

        # Update if value changed OR force_update is enabled
        force_update = bool(self._attr_force_update)
        if new_value != self._last_value or force_update:
            self._last_value = new_value
            self.async_write_ha_state()

            if ADVANCED_LOGGING:
                _LOGGER.debug("Fast update for %s: %s -> %s", self._attr_name, self._last_value, new_value)

    @callback
    def _cleanup_fast_listener(self) -> None:
        """Ensure fast listener is removed exactly once when entity is torn down."""
        if self._is_removed:
            return

        self._is_removed = True

        if self._remove_fast_listener is not None:
            try:
                self._remove_fast_listener()
                if ADVANCED_LOGGING:
                    _LOGGER.debug("Sensor %s unregistered from fast updates", self._attr_name)
            except Exception as e:
                _LOGGER.warning("Error unregistering fast listener for %s: %s", self._attr_name, e)
            finally:
                self._remove_fast_listener = None


class FastPollSensor(SajSensor):
    """Sensor for fast-polling (10s) - NO state_class to prevent DB logging.
    
    These sensors update every 10 seconds but are NOT recorded in the database
    to prevent excessive database growth. They still show live updates in the UI.
    
    Note: Only fast variants (is_fast_variant=True) should use this class.
    """
    
    _attr_state_class = None  # No DB recording for fast-poll sensors
    
    def __init__(self, hub: SAJModbusHub, device_info: dict, description: SajModbusSensorEntityDescription, is_fast_variant: bool = True):
        """Initialize the fast-poll sensor."""
        super().__init__(hub, device_info, description, is_fast_variant=True)
        # Fast variants are always enabled by default for live monitoring
        self._attr_entity_registry_enabled_default = True
