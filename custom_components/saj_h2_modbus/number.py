import logging
import asyncio
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SAJ number entities."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = [
        SajChargeDayMaskInputEntity(hub, device_info),
        SajChargePowerPercentInputEntity(hub, device_info),
        SajExportLimitInputEntity(hub, device_info),
        SajAppModeInputEntity(hub, device_info),
        SajDischargeTimeEnableInputEntity(hub, device_info),
        SajBatteryOnGridDischargeDepthEntity(hub, device_info),
        SajBatteryOffGridDischargeDepthEntity(hub, device_info),
        SajBatteryCapacityChargeUpperLimitEntity(hub, device_info),
        SajBatteryChargePowerLimitEntity(hub, device_info),
        SajBatteryDischargePowerLimitEntity(hub, device_info),
        SajGridMaxChargePowerEntity(hub, device_info),
        SajGridMaxDischargePowerEntity(hub, device_info)
    ]

    for i in range(1, 8):
        entities.append(SajDischargeDayMaskInputEntity(hub, i, device_info))
        entities.append(SajDischargePowerPercentInputEntity(hub, i, device_info))

    async_add_entities(entities)

class SajNumberEntity(NumberEntity):
    """Base class for SAJ writable number entities."""
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hub, name, unique_id, min_val, max_val, step, default, device_info, unit=None):
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = default
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return self._attr_native_value

class SajChargeDayMaskInputEntity(SajNumberEntity):
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Charge Day Mask (Input)", f"{hub.name}_charge_day_mask_input", 0, 127, 1, 127, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127:
            _LOGGER.error(f"Invalid Day Mask: {val}")
            return
        self._attr_native_value = val
        await self._hub.set_charge_day_mask(val)
        self.async_write_ha_state()

class SajDischargeDayMaskInputEntity(SajNumberEntity):
    def __init__(self, hub, index=1, device_info=None):
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} Day Mask (Input)"
        unique_id = f"{hub.name}_discharge{prefix}_day_mask_input"
        super().__init__(hub, name, unique_id, 0, 127, 1, 127, device_info)
        self.index = index
        method_name = f"set_discharge{prefix}_day_mask"
        self.set_method = getattr(self._hub, method_name)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127:
            _LOGGER.error(f"Invalid Day Mask: {val}")
            return
        self._attr_native_value = val
        await self.set_method(val)
        self.async_write_ha_state()

class SajChargePowerPercentInputEntity(SajNumberEntity):
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Charge Power Percent (Input)", f"{hub.name}_charge_power_percent_input", 0, 25, 1, 5, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 25:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        self._attr_native_value = val
        await self._hub.set_charge_power_percent(val)
        self.async_write_ha_state()

class SajDischargePowerPercentInputEntity(SajNumberEntity):
    def __init__(self, hub, index=1, device_info=None):
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} Power Percent (Input)"
        unique_id = f"{hub.name}_discharge{prefix}_power_percent_input"
        super().__init__(hub, name, unique_id, 0, 100, 1, 5, device_info)
        self.index = index
        method_name = f"set_discharge{prefix}_power_percent"
        self.set_method = getattr(self._hub, method_name)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 100:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        self._attr_native_value = val
        await self.set_method(val)
        self.async_write_ha_state()

class SajExportLimitInputEntity(SajNumberEntity):
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Export Limit (Input)", f"{hub.name}_export_limit_input", 0, 1100, 100, 0, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid export limit: {val}")
            return
        self._attr_native_value = val
        await self._hub.set_export_limit(val)
        self.async_write_ha_state()

class SajAppModeInputEntity(SajNumberEntity):
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ App Mode (Input)", f"{hub.name}_app_mode_input", 0, 3, 1, 0, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 3:
            _LOGGER.error(f"Invalid app mode: {val}")
            return
        self._attr_native_value = val
        await self._hub.set_app_mode(val)
        self.async_write_ha_state()

class SajDischargeTimeEnableInputEntity(SajNumberEntity):
    """Entity for Discharge Time Enable (0-127)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Discharge_time_enable (Input)", f"{hub.name}_discharge_time_enable_input", 0, 127, 1, 0, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127:
            _LOGGER.error(f"Invalid discharge time enable value: {val}")
            return
        _LOGGER.debug(f"Setting discharge time enable to: {val}")
        self._attr_native_value = val
        # Use the set_discharge_time_enable method of the Hub
        await self._hub.set_discharge_time_enable(val)
        self.async_write_ha_state()

class SajBatteryOnGridDischargeDepthEntity(SajNumberEntity):
    """Entity for Battery On Grid Discharge Depth (0-100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Battery On Grid Discharge Depth (Input)", f"{hub.name}_battery_on_grid_discharge_depth_input", 0, 100, 1, 20, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 100:
            _LOGGER.error(f"Invalid battery on grid discharge depth: {val}")
            return
        _LOGGER.debug(f"Setting battery on grid discharge depth to: {val}")
        self._attr_native_value = val
        await self._hub.set_battery_on_grid_discharge_depth(val)
        self.async_write_ha_state()

class SajBatteryOffGridDischargeDepthEntity(SajNumberEntity):
    """Entity for Battery Off Grid Discharge Depth (0-100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Battery Off Grid Discharge Depth (Input)", f"{hub.name}_battery_off_grid_discharge_depth_input", 0, 100, 1, 20, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 100:
            _LOGGER.error(f"Invalid battery off grid discharge depth: {val}")
            return
        _LOGGER.debug(f"Setting battery off grid discharge depth to: {val}")
        self._attr_native_value = val
        await self._hub.set_battery_off_grid_discharge_depth(val)
        self.async_write_ha_state()

class SajBatteryCapacityChargeUpperLimitEntity(SajNumberEntity):
    """Entity for Battery Capacity Charge Upper Limit (0-100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Battery Capacity Charge Upper Limit (Input)", f"{hub.name}_battery_capacity_charge_upper_limit_input", 0, 100, 1, 100, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 100:
            _LOGGER.error(f"Invalid battery capacity charge upper limit: {val}")
            return
        _LOGGER.debug(f"Setting battery capacity charge upper limit to: {val}")
        self._attr_native_value = val
        await self._hub.set_battery_capacity_charge_upper_limit(val)
        self.async_write_ha_state()

class SajBatteryChargePowerLimitEntity(SajNumberEntity):
    """Entity for Battery Charge Power Limit (0-1100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Battery Charge Power Limit (Input)", f"{hub.name}_battery_charge_power_limit_input", 0, 1100, 100, 1100, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid battery charge power limit: {val}")
            return
        _LOGGER.debug(f"Setting battery charge power limit to: {int(val)}")
        self._attr_native_value = val
        await self._hub.set_battery_charge_power_limit(val)
        self.async_write_ha_state()

class SajBatteryDischargePowerLimitEntity(SajNumberEntity):
    """Entity for Battery Discharge Power Limit (0-1100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Battery Discharge Power Limit (Input)", f"{hub.name}_battery_discharge_power_limit_input", 0, 1100, 100, 1100, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid battery discharge power limit: {val}")
            return
        _LOGGER.debug(f"Setting battery discharge power limit to: {int(val)}")
        self._attr_native_value = val
        await self._hub.set_battery_discharge_power_limit(val)
        self.async_write_ha_state()

class SajGridMaxChargePowerEntity(SajNumberEntity):
    """Entity for Grid Max Charge Power (0-1100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Grid Max Charge Power (Input)", f"{hub.name}_grid_max_charge_power_input", 0, 1100, 100, 1100, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid grid max charge power: {val}")
            return
        _LOGGER.debug(f"Setting grid max charge power to: {int(val)}")
        self._attr_native_value = val
        await self._hub.set_grid_max_charge_power(val)
        self.async_write_ha_state()

class SajGridMaxDischargePowerEntity(SajNumberEntity):
    """Entity for Grid Max Discharge Power (0-1100)."""
    def __init__(self, hub, device_info):
        super().__init__(hub, "SAJ Grid Max Discharge Power (Input)", f"{hub.name}_grid_max_discharge_power_input", 0, 1100, 100, 1100, device_info)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid grid max discharge power: {val}")
            return
        _LOGGER.debug(f"Setting grid max discharge power to: {int(val)}")
        self._attr_native_value = val
        await self._hub.set_grid_max_discharge_power(val)
        self.async_write_ha_state()
