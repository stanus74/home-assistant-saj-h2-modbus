"""Plattform für schreibbare SAJ Modbus Uhrzeit-Entitäten."""
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
    """Richte die schreibbaren Uhrzeit-Entitäten für First Charge ein."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    entities = [
        SajFirstChargeStartTimeTextEntity(hub),
        SajFirstChargeEndTimeTextEntity(hub),
    ]
    async_add_entities(entities)

class SajFirstChargeStartTimeTextEntity(TextEntity):
    """Schreibbare Uhrzeit-Entität für den First Charge Start Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialisiere die Entität."""
        self._hub = hub
        self._attr_name = "SAJ First Charge Start Time (Time)"
        self._attr_unique_id = "saj_first_charge_start_time_time"
        self._attr_native_value = "00:00"
        # Regex, das HH:MM erzwingt: Stunden von 00 bis 23, Minuten von 00 bis 59
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update wird hier nicht genutzt, um zusätzliche Modbus-Anfragen zu vermeiden."""
        # Wir verlassen diesen Update-Block bewusst leer,
        # damit hier nicht erneut modbus-Register abgefragt werden.
        pass

    async def async_set_value(self, value) -> None:
        """Setze einen neuen Startzeitwert (Format 'HH:MM')."""
        # Falls value ein datetime.time-Objekt ist, konvertiere es
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Ungültiges Zeitformat für First Charge Start Time: %s. Erwartet HH:MM", value
            )
            return

        await self._hub.set_first_charge_start(value)
        self._attr_native_value = value
        self.async_write_ha_state()

class SajFirstChargeEndTimeTextEntity(TextEntity):
    """Schreibbare Uhrzeit-Entität für den First Charge End Time (Format HH:MM)."""

    def __init__(self, hub):
        """Initialisiere die Entität."""
        self._hub = hub
        self._attr_name = "SAJ First Charge End Time (Time)"
        self._attr_unique_id = "saj_first_charge_end_time_time"
        self._attr_native_value = "00:00"
        self._attr_pattern = r"^(0[0-9]|1[0-9]|2[0-3]):([0-5][0-9])$"
        self._attr_mode = "text"

    async def async_update(self) -> None:
        """Update wird hier nicht genutzt, um zusätzliche Modbus-Anfragen zu vermeiden."""
        pass

    async def async_set_value(self, value) -> None:
        """Setze einen neuen Endzeitwert (Format 'HH:MM')."""
        # Falls value ein datetime.time-Objekt ist, konvertiere es
        if isinstance(value, datetime.time):
            value = value.strftime("%H:%M")
        
        if not isinstance(value, str) or not re.match(self._attr_pattern, value):
            _LOGGER.error(
                "Ungültiges Zeitformat für First Charge End Time: %s. Erwartet HH:MM", value
            )
            return

        await self._hub.set_first_charge_end(value)
        self._attr_native_value = value
        self.async_write_ha_state()
