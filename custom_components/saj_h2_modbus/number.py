import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NUMBER_DEFINITIONS = [
    {
        "key": "charge_day_mask",
        "name": "Charge Day Mask",
        "min": 0,
        "max": 127,
        "step": 1,
        "default": 127,
        "unit": None,
        "setter": "set_charge_day_mask",
    },
    {
        "key": "charge_power_percent",
        "name": "Charge Power Percent",
        "min": 0,
        "max": 100,
        "step": 1,
        "default": 5,
        "unit": "%",
        "setter": "set_charge_power_percent",
    },
    {
        "key": "export_limit",
        "name": "Export Limit",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 0,
        "unit": None,
        "setter": "set_export_limit",
    },
    {
        "key": "app_mode",
        "name": "App Mode",
        "min": 0,
        "max": 3,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_app_mode",
    },
    {
        "key": "discharge_time_enable",
        "name": "Discharge Time Enable",
        "min": 0,
        "max": 127,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_discharge_time_enable",
    },
    {
        "key": "battery_on_grid_discharge_depth",
        "name": "Battery On Grid Discharge Depth",
        "min": 0,
        "max": 100,
        "step": 1,
        "default": 20,
        "unit": "%",
        "setter": "set_battery_on_grid_discharge_depth",
    },
    {
        "key": "battery_off_grid_discharge_depth",
        "name": "Battery Off Grid Discharge Depth",
        "min": 0,
        "max": 100,
        "step": 1,
        "default": 20,
        "unit": "%",
        "setter": "set_battery_off_grid_discharge_depth",
    },
    {
        "key": "battery_capacity_charge_upper_limit",
        "name": "Battery Capacity Charge Upper Limit",
        "min": 0,
        "max": 100,
        "step": 1,
        "default": 100,
        "unit": "%",
        "setter": "set_battery_capacity_charge_upper_limit",
    },
    {
        "key": "battery_charge_power_limit",
        "name": "Battery Charge Power Limit",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 1100,
        "unit": None,
        "setter": "set_battery_charge_power_limit",
    },
    {
        "key": "battery_discharge_power_limit",
        "name": "Battery Discharge Power Limit",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 1100,
        "unit": None,
        "setter": "set_battery_discharge_power_limit",
    },
    {
        "key": "grid_max_charge_power",
        "name": "Grid Max Charge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 1100,
        "unit": None,
        "setter": "set_grid_max_charge_power",
    },
    {
        "key": "grid_max_discharge_power",
        "name": "Grid Max Discharge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 1100,
        "unit": None,
        "setter": "set_grid_max_discharge_power",
    },
    {
        "key": "passive_charge_enable",
        "name": "Passive Charge Enable",
        "min": 0,
        "max": 2,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_passive_charge_enable",
    },
    {
        "key": "passive_grid_charge_power",
        "name": "Passive Grid Charge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 0,
        "unit": None,
        "setter": "set_passive_grid_charge_power",
    },
    {
        "key": "passive_grid_discharge_power",
        "name": "Passive Grid Discharge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 0,
        "unit": None,
        "setter": "set_passive_grid_discharge_power",
    },
    {
        "key": "passive_bat_charge_power",
        "name": "Passive Battery Charge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 0,
        "unit": None,
        "setter": "set_passive_bat_charge_power",
    },
    {
        "key": "passive_bat_discharge_power",
        "name": "Passive Battery Discharge Power",
        "min": 0,
        "max": 1100,
        "step": 100,
        "default": 0,
        "unit": None,
        "setter": "set_passive_bat_discharge_power",
    },
]

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

    entities = []

    for desc in NUMBER_DEFINITIONS:
        entity = SajGenericNumberEntity(
            hub=hub,
            name=f"SAJ {desc['name']} (Input)",
            unique_id=f"{hub.name}_{desc['key']}_input",
            min_val=desc["min"],
            max_val=desc["max"],
            step=desc["step"],
            default=desc["default"],
            unit=desc["unit"],
            set_method_name=desc["setter"],
            device_info=device_info,
        )
        entities.append(entity)

    # Add discharge entities for indices 1-7
    for i in range(1, 8):
        prefix = str(i)
        for desc in [
            {
                "key": f"discharge{prefix}_day_mask",
                "name": f"Discharge{prefix} Day Mask",
                "min": 0,
                "max": 127,
                "step": 1,
                "default": 127,
                "unit": None,
                "setter": f"set_discharge{prefix}_day_mask",
            },
            {
                "key": f"discharge{prefix}_power_percent",
                "name": f"Discharge{prefix} Power Percent",
                "min": 0,
                "max": 100,
                "step": 1,
                "default": 5,
                "unit": "%",
                "setter": f"set_discharge{prefix}_power_percent",
            },
        ]:
            entity = SajGenericNumberEntity(
                hub=hub,
                name=f"SAJ {desc['name']} (Input)",
                unique_id=f"{hub.name}_{desc['key']}_input",
                min_val=desc["min"],
                max_val=desc["max"],
                step=desc["step"],
                default=desc["default"],
                unit=desc["unit"],
                set_method_name=desc["setter"],
                device_info=device_info,
            )
            entities.append(entity)

    async_add_entities(entities)
