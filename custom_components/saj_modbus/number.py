"""Plattform für schreibbare SAJ Modbus Number-Entitäten."""
import logging
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Richte die schreibbaren Number-Entitäten für First Charge ein."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    entities = [
        SajFirstChargeDayMaskInputEntity(hub),
        SajFirstChargePowerPercentInputEntity(hub),
    ]
    async_add_entities(entities)


class SajFirstChargeDayMaskInputEntity(NumberEntity):
    """Schreibbare Entität für den First Charge Day Mask Wert (als Bitmaske 0-127)."""

    def __init__(self, hub):
        """Initialize the number entity."""
        self._hub = hub
        self._attr_name = "SAJ First Charge Day Mask (Input)"
        self._attr_unique_id = "saj_first_charge_day_mask_input"
        self._attr_native_unit_of_measurement = None
        self._attr_native_min_value = 0
        self._attr_native_max_value = 127
        self._attr_native_step = 1
        self._attr_native_value = 127
        self._attr_mode = NumberMode.BOX
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        return self._attr_native_value

    async def async_update(self) -> None:
        # Entferne den Aufruf von read_first_charge_data, um zusätzliche Anfragen zu vermeiden.
        pass

    async def async_set_native_value(self, value: float) -> None:
        """Setze einen neuen Day Mask Wert mit strikter Validierung."""
        value = int(value)  # Konvertiere zu Integer
        if not 0 <= value <= 127:
            _LOGGER.error(f"Ungültiger Day Mask Wert: {value}. Wert muss zwischen 0 und 127 liegen.")
            return
            
        self._attr_native_value = value
        await self._hub.set_first_charge_day_mask(value)
        self.async_write_ha_state()


class SajFirstChargePowerPercentInputEntity(NumberEntity):
    """Schreibbare Entität für den First Charge Power Percent Wert (in %)."""

    def __init__(self, hub):
        """Initialize the number entity."""
        self._hub = hub
        self._attr_name = "SAJ First Charge Power Percent (Input)"
        self._attr_unique_id = "saj_first_charge_power_percent_input"
        self._attr_native_unit_of_measurement = "%"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 25
        self._attr_native_step = 1
        self._attr_native_value = 5
        self._attr_mode = NumberMode.BOX
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        return self._attr_native_value

    async def async_update(self) -> None:
        # Entferne den Aufruf von read_first_charge_data, um zusätzliche Anfragen zu vermeiden.
        pass

    async def async_set_native_value(self, value: float) -> None:
        """Setze einen neuen Prozentwert mit strikter Validierung."""
        value = int(value)  # Konvertiere zu Integer
        if not 0 <= value <= 25:
            _LOGGER.error(f"Ungültiger Prozentwert: {value}. Wert muss zwischen 0 und 25 liegen.")
            return
            
        self._attr_native_value = value
        await self._hub.set_first_charge_power_percent(value)
        self.async_write_ha_state()
