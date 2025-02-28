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
    async_add_entities([
        SajFirstChargeDayMaskInputEntity(hub),
        SajFirstChargePowerPercentInputEntity(hub),
    ])

class SajNumberEntity(NumberEntity):
    """Basisklasse für schreibbare SAJ Number-Entitäten."""
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub, name: str, unique_id: str, min_value: int, max_value: int, step: int, default_value: int, unit: str | None = None):
        """Initialisiere die Number-Entität."""
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = default_value
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float:
        return self._attr_native_value

    async def async_update(self) -> None:
        pass  # Keine zusätzlichen Anfragen erforderlich

class SajFirstChargeDayMaskInputEntity(SajNumberEntity):
    """Schreibbare Entität für den First Charge Day Mask Wert (als Bitmaske 0-127)."""
    def __init__(self, hub):
        super().__init__(
            hub,
            name="SAJ First Charge Day Mask (Input)",
            unique_id="saj_first_charge_day_mask_input",
            min_value=0,
            max_value=127,
            step=1,
            default_value=127
        )

    async def async_set_native_value(self, value: float) -> None:
        """Setze einen neuen Day Mask Wert mit Validierung."""
        value = int(value)
        if not 0 <= value <= 127:
            _LOGGER.error(f"Ungültiger Day Mask Wert: {value}. Wert muss zwischen 0 und 127 liegen.")
            return
        self._attr_native_value = value
        await self._hub.set_first_charge_day_mask(value)
        self.async_write_ha_state()

class SajFirstChargePowerPercentInputEntity(SajNumberEntity):
    """Schreibbare Entität für den First Charge Power Percent Wert (in %)."""
    def __init__(self, hub):
        super().__init__(
            hub,
            name="SAJ First Charge Power Percent (Input)",
            unique_id="saj_first_charge_power_percent_input",
            min_value=0,
            max_value=25,
            step=1,
            default_value=5,
            unit="%"
        )

    async def async_set_native_value(self, value: float) -> None:
        """Setze einen neuen Prozentwert mit Validierung."""
        value = int(value)
        if not 0 <= value <= 25:
            _LOGGER.error(f"Ungültiger Prozentwert: {value}. Wert muss zwischen 0 und 25 liegen.")
            return
        self._attr_native_value = value
        await self._hub.set_first_charge_power_percent(value)
        self.async_write_ha_state()