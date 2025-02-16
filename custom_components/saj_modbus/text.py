"""Platform for writable SAJ Modbus time entities."""
import datetime
import re
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.text import TextEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the writable time entities for First Charge."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    entities = [
        SajFirstChargeStartTimeTextEntity(hub),
        SajFirstChargeEndTimeTextEntity(hub),
    ]
    async_add_entities(entities)

class SajFirstChargeStartTimeTextEntity(TextEntity):
    """Writable time entity for the First Charge Start Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ First Charge Start Time (Time)"
        self._attr_unique_id = "saj_first_charge_start_time_time"
        self._attr_native_value = "00:00"
        # Regex enforcing HH:MM format: hours from 00 to 23, minutes from 00 to 59
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        # We intentionally leave this update block empty,
        # so that Modbus registers are not queried again.
        pass

    async def async_set_value(self, value) -> None:
        """Set a new start time value (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Invalid time format for First Charge Start Time: %s. Expected HH:MM", value
            )
            return

        await self._hub.set_first_charge_start(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajFirstChargeEndTimeTextEntity(TextEntity):
    """Writable time entity for the First Charge End Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ First Charge End Time (Time)"
        self._attr_unique_id = "saj_first_charge_end_time_time"
        self._attr_native_value = "00:00"
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        pass

    async def async_set_value(self, value) -> None:
        """Set a new end time value (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Invalid time format for First Charge End Time: %s. Expected HH:MM", value
            )
            return

        await self._hub.set_first_charge_end(value)
        self._attr_native_value = value
        self.async_write_ha_state()
