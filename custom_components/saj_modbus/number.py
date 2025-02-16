"""Platform for writable SAJ Modbus Number entities."""
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
    """Set up the writable Number entities for First Charge."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    entities = [
        SajFirstChargeDayMaskInputEntity(hub),
        SajFirstChargePowerPercentInputEntity(hub),
    ]
    async_add_entities(entities)


class SajFirstChargeDayMaskInputEntity(NumberEntity):
    """Writable entity for the First Charge Day Mask value (as bitmask 0-127)."""

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
        # Remove the call to read_first_charge_data to avoid additional requests.
        pass

    async def async_set_native_value(self, value: float) -> None:
        """Set a new Day Mask value with strict validation."""
        value = int(value)  # Convert to Integer
        if not 0 <= value <= 127:
            _LOGGER.error(f"Invalid Day Mask value: {value}. Value must be between 0 and 127.")
            return
            
        self._attr_native_value = value
        await self._hub.set_first_charge_day_mask(value)
        self.async_write_ha_state()


class SajFirstChargePowerPercentInputEntity(NumberEntity):
    """Writable entity for the First Charge Power Percent value (in %)."""

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
        # Remove the call to read_first_charge_data to avoid additional requests.
        pass

    async def async_set_native_value(self, value: float) -> None:
        """Set a new percentage value with strict validation."""
        value = int(value)  # Convert to Integer
        if not 0 <= value <= 25:
            _LOGGER.error(f"Invalid percentage value: {value}. Value must be between 0 and 25.")
            return
            
        self._attr_native_value = value
        await self._hub.set_first_charge_power_percent(value)
        self.async_write_ha_state()
