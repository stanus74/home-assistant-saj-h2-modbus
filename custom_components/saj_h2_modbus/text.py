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
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]
    
    entities = [
        SajChargeStartTimeTextEntity(hub, device_info),
        SajChargeEndTimeTextEntity(hub, device_info),
    ]
    
    # Discharge Start/End Time Entities (1-7)
    for i in range(1, 8):
        entities.append(SajDischargeStartTimeTextEntity(hub, i, device_info))
        entities.append(SajDischargeEndTimeTextEntity(hub, i, device_info))
    
    async_add_entities(entities)

class SajTimeTextEntity(TextEntity):
    """Base class for SAJ writable time entities."""

    def __init__(self, hub, name, unique_id, set_method, device_info):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_value = "00:00"
        # Regex that enforces HH:MM: Hours from 00 to 23, minutes from 00 to 59
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"
        self.set_method = set_method
        self._attr_device_info = device_info

    async def async_update(self) -> None:
        """Update is not used here to avoid additional Modbus requests."""
        # We intentionally leave this update block empty,
        # so that modbus registers are not queried again here.
        pass

    async def async_set_value(self, value) -> None:
        """Set a new time value (Format 'HH:MM')."""
        # If value is a datetime.time object, convert it
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                f"Invalid time format for {self._attr_name}: {value}. Expected HH:MM"
            )
            return

        await self.set_method(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajChargeStartTimeTextEntity(SajTimeTextEntity):
    """Writable time entity for Charge Start Time (Format HH:MM)."""

    def __init__(self, hub, device_info):
        """Initialize the entity."""
        super().__init__(
            hub, 
            "SAJ Charge Start Time (Time)", 
            f"{hub.name}_charge_start_time", 
            hub.set_charge_start,
            device_info
        )

class SajChargeEndTimeTextEntity(SajTimeTextEntity):
    """Writable time entity for Charge End Time (Format HH:MM)."""

    def __init__(self, hub, device_info):
        """Initialize the entity."""
        super().__init__(
            hub, 
            "SAJ Charge End Time (Time)", 
            f"{hub.name}_charge_end_time", 
            hub.set_charge_end,
            device_info
        )

class SajDischargeStartTimeTextEntity(SajTimeTextEntity):
    """Writable time entity for Discharge Start Time (Format HH:MM)."""

    def __init__(self, hub, index=1, device_info=None):
        """Initialize the entity."""
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} Start Time (Time)"
        unique_id = f"{hub.name}_discharge{prefix}_start_time"
        
        # Dynamically select the correct Hub method
        method_name = f"set_discharge{prefix}_start"
        set_method = getattr(hub, method_name)
        
        super().__init__(hub, name, unique_id, set_method, device_info)

class SajDischargeEndTimeTextEntity(SajTimeTextEntity):
    """Writable time entity for Discharge End Time (Format HH:MM)."""

    def __init__(self, hub, index=1, device_info=None):
        """Initialize the entity."""
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} End Time (Time)"
        unique_id = f"{hub.name}_discharge{prefix}_end_time"
        
        # Dynamically select the correct Hub method
        method_name = f"set_discharge{prefix}_end"
        set_method = getattr(hub, method_name)
        
        super().__init__(hub, name, unique_id, set_method, device_info)
