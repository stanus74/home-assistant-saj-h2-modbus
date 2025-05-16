import logging
import asyncio
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SAJ number entities."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    
    entities = [
        SajChargeDayMaskInputEntity(hub),
        SajChargePowerPercentInputEntity(hub),
        SajExportLimitInputEntity(hub),
        SajAppModeInputEntity(hub),
        SajDischargeTimeEnableInputEntity(hub),
        SajBatteryOnGridDischargeDepthEntity(hub),
        SajBatteryOffGridDischargeDepthEntity(hub),
        SajBatteryCapacityChargeUpperLimitEntity(hub),
        SajBatteryChargePowerLimitEntity(hub),
        SajBatteryDischargePowerLimitEntity(hub),
        SajGridMaxChargePowerEntity(hub),
        SajGridMaxDischargePowerEntity(hub)
    ]
    
    # Discharge Day Mask Entities (1-7)
    for i in range(1, 8):
        prefix = "" if i == 1 else str(i)
        entities.append(SajDischargeDayMaskInputEntity(hub, i))
        entities.append(SajDischargePowerPercentInputEntity(hub, i))
    
    async_add_entities(entities)

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
        self._last_synced_value = default

    @property
    def native_value(self): return self._attr_native_value

    async def async_update(self):
        """Updates the value of the entity and synchronizes with input_number."""
        # If the value has changed, synchronize with input_number
        if self._attr_native_value != self._last_synced_value:
            await self._sync_with_input_number()
            self._last_synced_value = self._attr_native_value

    async def _sync_with_input_number(self):
        """Synchronizes the value with the corresponding input_number entity."""
        # Find the associated input_number entity
        input_number_entity_id = None
        
        # Extract the ID from the unique_id (e.g. "saj_charge_day_mask_input" -> "saj_charge_day_mask")
        entity_id_base = self._attr_unique_id.replace("_input", "")
        input_number_entity_id = f"input_number.{entity_id_base}"
        
        if input_number_entity_id and self.hass.states.get(input_number_entity_id):
            try:
                # Update the value of the input_number entity
                await self.hass.services.async_call(
                    INPUT_NUMBER_DOMAIN,
                    "set_value",
                    {
                        "entity_id": input_number_entity_id,
                        "value": self._attr_native_value
                    },
                    blocking=False
                )
                _LOGGER.debug(f"Synchronized {input_number_entity_id} with value {self._attr_native_value}")
            except Exception as e:
                _LOGGER.error(f"Error synchronizing {input_number_entity_id}: {e}")

class SajChargeDayMaskInputEntity(SajNumberEntity):
    """Entity for Charge Day Mask (0-127)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Charge Day Mask (Input)", "saj_charge_day_mask_input", 0, 127, 1, 127)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127: _LOGGER.error(f"Invalid Day Mask: {val}"); return
        self._attr_native_value = val
        await self._hub.set_charge_day_mask(val)
        self.async_write_ha_state()

class SajDischargeDayMaskInputEntity(SajNumberEntity):
    """Entity for Discharge Day Mask (0-127)."""
    def __init__(self, hub, index=1):
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} Day Mask (Input)"
        unique_id = f"saj_discharge{prefix}_day_mask_input"
        super().__init__(hub, name, unique_id, 0, 127, 1, 127)
        self.index = index
        
        # Dynamically select the correct Hub method
        method_name = f"set_discharge{prefix}_day_mask"
        self.set_method = getattr(self._hub, method_name)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 127:
            _LOGGER.error(f"Invalid Day Mask: {val}")
            return
        self._attr_native_value = val
        # Set the Day Mask for discharge using the dynamic method
        await self.set_method(val)
        self.async_write_ha_state()

class SajChargePowerPercentInputEntity(SajNumberEntity):
    """Entity for Charge Power Percent (0-25)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Charge Power Percent (Input)", "saj_charge_power_percent_input", 0, 25, 1, 5)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 25:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        _LOGGER.debug(f"Setting power percent to: {val}")
        self._attr_native_value = val
        await self._hub.set_charge_power_percent(val)
        self.async_write_ha_state()  # For logbook

class SajDischargePowerPercentInputEntity(SajNumberEntity):
    """Entity for Discharge Power Percent (0-100)."""
    def __init__(self, hub, index=1):
        prefix = "" if index == 1 else str(index)
        name = f"SAJ Discharge{prefix} Power Percent (Input)"
        unique_id = f"saj_discharge{prefix}_power_percent_input"
        super().__init__(hub, name, unique_id, 0, 100, 1, 5)
        self.index = index
        
        # Dynamically select the correct Hub method
        method_name = f"set_discharge{prefix}_power_percent"
        self.set_method = getattr(self._hub, method_name)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 100:
            _LOGGER.error(f"Invalid percent: {val}")
            return
        _LOGGER.debug(f"Setting discharge{' ' + str(self.index) if self.index > 1 else ''} power percent to: {val}")
        self._attr_native_value = val
        # Set the Power Percent for discharge using the dynamic method
        await self.set_method(val)
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

class SajAppModeInputEntity(SajNumberEntity):
    """Entity for App Mode (0-3)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ App Mode (Input)", "saj_app_mode_input", 0, 3, 1, 0)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 3:
            _LOGGER.error(f"Invalid app mode: {val}")
            return
        _LOGGER.debug(f"Setting app mode to: {val}")
        self._attr_native_value = val
        # Use the set_app_mode method of the Hub
        await self._hub.set_app_mode(val)
        self.async_write_ha_state()

class SajDischargeTimeEnableInputEntity(SajNumberEntity):
    """Entity for Discharge Time Enable (0-127)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Discharge_time_enable (Input)", "saj_discharge_time_enable_input", 0, 127, 1, 0)

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
    def __init__(self, hub):
        super().__init__(hub, "SAJ Battery On Grid Discharge Depth (Input)", "saj_battery_on_grid_discharge_depth_input", 0, 100, 1, 20)

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
    def __init__(self, hub):
        super().__init__(hub, "SAJ Battery Off Grid Discharge Depth (Input)", "saj_battery_off_grid_discharge_depth_input", 0, 100, 1, 20)

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
    def __init__(self, hub):
        super().__init__(hub, "SAJ Battery Capacity Charge Upper Limit (Input)", "saj_battery_capacity_charge_upper_limit_input", 0, 100, 1, 100)

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
    def __init__(self, hub):
        super().__init__(hub, "SAJ Battery Charge Power Limit (Input)", "saj_battery_charge_power_limit_input", 0, 1100, 100, 1100)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid battery charge power limit: {val}")
            return
        _LOGGER.debug(f"Setting battery charge power limit to: {val}")
        self._attr_native_value = val
        await self._hub.set_battery_charge_power_limit(val)
        self.async_write_ha_state()

class SajBatteryDischargePowerLimitEntity(SajNumberEntity):
    """Entity for Battery Discharge Power Limit (0-1100)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Battery Discharge Power Limit (Input)", "saj_battery_discharge_power_limit_input", 0, 1100, 100, 1100)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid battery discharge power limit: {val}")
            return
        _LOGGER.debug(f"Setting battery discharge power limit to: {val}")
        self._attr_native_value = val
        await self._hub.set_battery_discharge_power_limit(val)
        self.async_write_ha_state()

class SajGridMaxChargePowerEntity(SajNumberEntity):
    """Entity for Grid Max Charge Power (0-1100)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Grid Max Charge Power (Input)", "saj_grid_max_charge_power_input", 0, 1100, 100, 1100)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid grid max charge power: {val}")
            return
        _LOGGER.debug(f"Setting grid max charge power to: {val}")
        self._attr_native_value = val
        await self._hub.set_grid_max_charge_power(val)
        self.async_write_ha_state()

class SajGridMaxDischargePowerEntity(SajNumberEntity):
    """Entity for Grid Max Discharge Power (0-1100)."""
    def __init__(self, hub):
        super().__init__(hub, "SAJ Grid Max Discharge Power (Input)", "saj_grid_max_discharge_power_input", 0, 1100, 100, 1100)

    async def async_set_native_value(self, value):
        val = int(value)
        if not 0 <= val <= 1100:
            _LOGGER.error(f"Invalid grid max discharge power: {val}")
            return
        _LOGGER.debug(f"Setting grid max discharge power to: {val}")
        self._attr_native_value = val
        await self._hub.set_grid_max_discharge_power(val)
        self.async_write_ha_state()
