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
    """Set up the writable time entities for Charge and Discharge."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    entities = [
        SajChargeStartTimeTextEntity(hub),
        SajChargeEndTimeTextEntity(hub),
        SajDischargeStartTimeTextEntity(hub),
        SajDischargeEndTimeTextEntity(hub),
    ]
    async_add_entities(entities)

class SajChargeStartTimeTextEntity(TextEntity):
    """Writable time entity for Charge Start Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ Charge Start Time (Time)"
        self._attr_unique_id = "saj_charge_start_time"
        self._attr_native_value = "00:00"
        # Regex that enforces HH:MM: Hours from 00 to 23, minutes from 00 to 59
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        # We intentionally leave this update block empty,
        # so that modbus registers are not queried again here.
        pass

    async def async_set_value(self, value) -> None:
        """Set a new start time value (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Invalid time format for Charge Start Time: %s. Expected HH:MM", value
            )
            return

        await self._hub.set_charge_start(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajChargeEndTimeTextEntity(TextEntity):
    """Writable time entity for Charge End Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ Charge End Time (Time)"
        self._attr_unique_id = "saj_charge_end_time"
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
                "Invalid time format for Charge End Time: %s. Expected HH:MM", value
            )
            return

        await self._hub.set_charge_end(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajDischargeStartTimeTextEntity(TextEntity):
    """Writable time entity for Discharge Start Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ Discharge Start Time (Time)"
        self._attr_unique_id = "saj_discharge_start_time"
        self._attr_native_value = "00:00"
        # Regex that enforces HH:MM: Hours from 00 to 23, minutes from 00 to 59
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        pass

    async def async_set_value(self, value) -> None:
        """Set a new start time value for discharge (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Invalid time format for Discharge Start Time: %s. Expected HH:MM", value
            )
            return

        # Set the start time for discharge
        await self._hub.set_discharge_start(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajDischargeEndTimeTextEntity(TextEntity):
    """Writable time entity for Discharge End Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = "SAJ Discharge End Time (Time)"
        self._attr_unique_id = "saj_discharge_end_time"
        self._attr_native_value = "00:00"
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        pass

    async def async_set_value(self, value) -> None:
        """Set a new end time value for discharge (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Invalid time format for Discharge End Time: %s. Expected HH:MM", value
            )
            return

        # Set the end time for discharge
        await self._hub.set_discharge_end(value)
        self._attr_native_value = value
        self.async_write_ha_state()
