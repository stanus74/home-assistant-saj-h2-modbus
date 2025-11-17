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

# Removed old TEXT_DEFINITIONS - now handled dynamically

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the writable time entities for Charge and Discharge."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = []

    # Add charge entities for indices 1-7
    for i in range(1, 8):
        prefix = str(i)
        for desc in [
            {
                "key": f"charge{prefix}_start_time",
                "name": f"Charge{prefix} Start Time",
                "unique_id_suffix": f"_charge{prefix}_start_time",
                "setter": f"set_charge{prefix}_start",
            },
            {
                "key": f"charge{prefix}_end_time",
                "name": f"Charge{prefix} End Time",
                "unique_id_suffix": f"_charge{prefix}_end_time",
                "setter": f"set_charge{prefix}_end",
            },
        ]:
            entity = SajTimeTextEntity(
                hub=hub,
                name=f"SAJ {desc['name']} (Time)",
                unique_id=f"{hub.name}{desc['unique_id_suffix']}",
                set_method=getattr(hub, desc["setter"]),
                device_info=device_info
            )
            entities.append(entity)

    # Discharge Start/End Time Entities (1-7)
    for i in range(1, 8):
        prefix = str(i)
        for desc in [
            {
                "key": f"discharge{prefix}_start_time",
                "name": f"Discharge{prefix} Start Time",
                "unique_id_suffix": f"_discharge{prefix}_start_time",
                "setter": f"set_discharge{prefix}_start",
            },
            {
                "key": f"discharge{prefix}_end_time",
                "name": f"Discharge{prefix} End Time",
                "unique_id_suffix": f"_discharge{prefix}_end_time",
                "setter": f"set_discharge{prefix}_end",
            },
        ]:
            entity = SajTimeTextEntity(
                hub=hub,
                name=f"SAJ {desc['name']} (Time)",
                unique_id=f"{hub.name}{desc['unique_id_suffix']}",
                set_method=getattr(hub, desc["setter"]),
                device_info=device_info
            )
            entities.append(entity)

    async_add_entities(entities)

class SajTimeTextEntity(TextEntity):
    """Base class for SAJ writable time entities."""

    def __init__(self, hub, name, unique_id, set_method, device_info):
        """Initialize the entity."""
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        # Set default times:
        # - Charging: 01:00 for start, 01:10 for end
        # - Discharging: 02:00 for start, 02:10 for end
        if "discharge" in name.lower():
            # Discharge slots use 02:00-02:10
            if "start" in name.lower():
                self._attr_native_value = "02:00"
            elif "end" in name.lower():
                self._attr_native_value = "02:10"
            else:
                self._attr_native_value = "02:00"  # Fallback
        else:
            # Charge slots use 01:00-01:10
            if "start" in name.lower():
                self._attr_native_value = "01:00"
            elif "end" in name.lower():
                self._attr_native_value = "01:10"
            else:
                self._attr_native_value = "01:00"  # Fallback
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
