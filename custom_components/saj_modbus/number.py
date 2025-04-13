import logging
import asyncio
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SAJ number entities."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    async_add_entities([
        SajFirstChargeDayMaskInputEntity(hub), 
        SajFirstChargePowerPercentInputEntity(hub),
        SajDischargeDayMaskInputEntity(hub),
        SajDischargePowerPercentInputEntity(hub),
        SajExportLimitInputEntity(hub)
    ])

class SajNumberEntity(NumberEntity):
    """Base class for SAJ writable number entities."""
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub, name, unique_id, min_val, max_val, step, default, unit=None):
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = default
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self): return self._attr_native_value

    async def async_update(self): pass

class SajFirstChargeDayMaskInputEntity(SajNumberEntity):
    """Entity for First Charge Day Mask (0-127)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ First Charge Day Mask (Input)", "saj_first_charge_day_mask_input", 0, 127, 1, 127)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127: _LOGGER.error(f"Invalid Day Mask: {val}"); return
        self._attr_native_value = val
        await self._hub.set_first_charge_day_mask(val)
        self.async_write_ha_state()

class SajDischargeDayMaskInputEntity(SajNumberEntity):
    """Entity for Discharge Day Mask (0-127)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Discharge Day Mask (Input)", "saj_discharge_day_mask_input", 0, 127, 1, 127)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127: _LOGGER.error(f"Invalid Day Mask: {val}"); return
        self._attr_native_value = val
        await self._hub.set_discharging(val > 0)  # Aktiviere Entladung wenn Maske > 0
        self.async_write_ha_state()

class SajFirstChargePowerPercentInputEntity(SajNumberEntity):
    """Entity for First Charge Power Percent (0-25)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ First Charge Power Percent (Input)", "saj_first_charge_power_percent_input", 0, 25, 1, 5)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 25:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        _LOGGER.debug(f"Setting power percent to: {val}")
        self._attr_native_value = val
        await self._hub.set_first_charge_power_percent(val)
        self.async_write_ha_state()  # Für Logbuch

class SajDischargePowerPercentInputEntity(SajNumberEntity):
    """Entity for Discharge Power Percent (0-25)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Discharge Power Percent (Input)", "saj_discharge_power_percent_input", 0, 25, 1, 5)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 25:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        _LOGGER.debug(f"Setting discharge power percent to: {val}")
        self._attr_native_value = val
        await self._hub.set_discharging(val > 0)  # Aktiviere Entladung wenn Wert > 0
        self.async_write_ha_state()

class SajExportLimitInputEntity(SajNumberEntity):
    """Entity for Export Limit (0-1000 )."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Export Limit (Input)", "saj_export_limit_input", 0, 1000, 100, 0)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1000:
            _LOGGER.error(f"Invalid export limit: {val}")
            return
        _LOGGER.debug(f"Setting export limit to: {val}")
        self._attr_native_value = val
        await self._hub.set_export_limit(val)
        self.async_write_ha_state()
