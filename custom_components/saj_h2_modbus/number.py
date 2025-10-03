import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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

class SajGenericNumberEntity(SajNumberEntity):
    """Generic class for SAJ number entities."""
    def __init__(self, hub, name, unique_id, min_val, max_val, step, default, device_info, unit=None, set_method_name=None):
        super().__init__(hub, name, unique_id, min_val, max_val, step, default, device_info, unit)
        self.set_method = getattr(hub, set_method_name) if set_method_name else None

    async def async_set_native_value(self, value):
        val = int(value)
        if not self._attr_native_min_value <= val <= self._attr_native_max_value:
            _LOGGER.error(f"Invalid value for {self._attr_name}: {val}")
            return
        self._attr_native_value = val
        if self.set_method:
            await self.set_method(val)
        self.async_write_ha_state()

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SAJ number entities."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = [
        SajGenericNumberEntity(hub, "SAJ Charge Day Mask (Input)", f"{hub.name}_charge_day_mask_input", 0, 127, 1, 127, device_info, set_method_name="set_charge_day_mask"),
        SajGenericNumberEntity(hub, "SAJ Charge Power Percent (Input)", f"{hub.name}_charge_power_percent_input", 0, 100, 1, 5, device_info, set_method_name="set_charge_power_percent"),
        SajGenericNumberEntity(hub, "SAJ Export Limit (Input)", f"{hub.name}_export_limit_input", 0, 1100, 100, 0, device_info, set_method_name="set_export_limit"),
        SajGenericNumberEntity(hub, "SAJ App Mode (Input)", f"{hub.name}_app_mode_input", 0, 3, 1, 0, device_info, set_method_name="set_app_mode"),
        SajGenericNumberEntity(hub, "SAJ Discharge Time Enable (Input)", f"{hub.name}_discharge_time_enable_input", 0, 127, 1, 0, device_info, set_method_name="set_discharge_time_enable"),
        SajGenericNumberEntity(hub, "SAJ Battery On Grid Discharge Depth (Input)", f"{hub.name}_battery_on_grid_discharge_depth_input", 0, 100, 1, 20, device_info, set_method_name="set_battery_on_grid_discharge_depth"),
        SajGenericNumberEntity(hub, "SAJ Battery Off Grid Discharge Depth (Input)", f"{hub.name}_battery_off_grid_discharge_depth_input", 0, 100, 1, 20, device_info, set_method_name="set_battery_off_grid_discharge_depth"),
        SajGenericNumberEntity(hub, "SAJ Battery Capacity Charge Upper Limit (Input)", f"{hub.name}_battery_capacity_charge_upper_limit_input", 0, 100, 1, 100, device_info, set_method_name="set_battery_capacity_charge_upper_limit"),
        SajGenericNumberEntity(hub, "SAJ Battery Charge Power Limit (Input)", f"{hub.name}_battery_charge_power_limit_input", 0, 1100, 100, 1100, device_info, set_method_name="set_battery_charge_power_limit"),
        SajGenericNumberEntity(hub, "SAJ Battery Discharge Power Limit (Input)", f"{hub.name}_battery_discharge_power_limit_input", 0, 1100, 100, 1100, device_info, set_method_name="set_battery_discharge_power_limit"),
        SajGenericNumberEntity(hub, "SAJ Grid Max Charge Power (Input)", f"{hub.name}_grid_max_charge_power_input", 0, 1100, 100, 1100, device_info, set_method_name="set_grid_max_charge_power"),
        SajGenericNumberEntity(hub, "SAJ Grid Max Discharge Power (Input)", f"{hub.name}_grid_max_discharge_power_input", 0, 1100, 100, 1100, device_info, set_method_name="set_grid_max_discharge_power"),
        SajGenericNumberEntity(hub, "SAJ Passive Charge Enable (Input)", f"{hub.name}_passive_charge_enable_input", 0, 2, 1, 0, device_info, set_method_name="set_passive_charge_enable"),
        SajGenericNumberEntity(hub, "SAJ Passive Grid Charge Power (Input)", f"{hub.name}_passive_grid_charge_power_input", 0, 1100, 100, 0, device_info, set_method_name="set_passive_grid_charge_power"),
        SajGenericNumberEntity(hub, "SAJ Passive Grid Discharge Power (Input)", f"{hub.name}_passive_grid_discharge_power_input", 0, 1100, 100, 0, device_info, set_method_name="set_passive_grid_discharge_power"),
        SajGenericNumberEntity(hub, "SAJ Passive Battery Charge Power (Input)", f"{hub.name}_passive_bat_charge_power_input", 0, 1100, 100, 0, device_info, set_method_name="set_passive_bat_charge_power"),
        SajGenericNumberEntity(hub, "SAJ Passive Battery Discharge Power (Input)", f"{hub.name}_passive_bat_discharge_power_input", 0, 1100, 100, 0, device_info, set_method_name="set_passive_bat_discharge_power"),
    ]

    for i in range(1, 8):
        prefix = str(i)
        entities.append(SajGenericNumberEntity(
            hub,
            f"SAJ Discharge{prefix} Day Mask (Input)",
            f"{hub.name}_discharge{prefix}_day_mask_input",
            0,
            127,
            1,
            127,
            device_info,
            set_method_name=f"set_discharge{prefix}_day_mask"
        ))
        entities.append(SajGenericNumberEntity(
            hub,
            f"SAJ Discharge{prefix} Power Percent (Input)",
            f"{hub.name}_discharge{prefix}_power_percent_input",
            0,
            100,
            1,
            5,
            device_info,
            set_method_name=f"set_discharge{prefix}_power_percent"
        ))

    async_add_entities(entities)
