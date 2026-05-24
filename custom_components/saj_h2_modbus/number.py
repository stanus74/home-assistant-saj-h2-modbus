"""SAJ H2 Modbus number entities."""
from __future__ import annotations
import logging
from typing import Any, TYPE_CHECKING
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .utils import generate_slot_definitions

if TYPE_CHECKING:
    from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

NUMBER_DEFINITIONS = [
    {
        "key": "charge_time_enable",
        "name": "Charge Time Enable",
        "min": 0,
        "max": 127,  # Changed from 1 to 127 - bitmask for 7 slots (bit 0-6)
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_charge_time_enable",
    },
    {
        "key": "app_mode",
        "name": "App Mode",
        "min": 0,
        "max": 12,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_app_mode",
        "allowed_values": [0, 1, 2, 3, 12],
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
        "key": "tou_outside_mode",
        "name": "TOU Outside Mode",
        "min": 0,
        "max": 1,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_tou_outside_mode",
        "allowed_values": [0, 1],
    },
    {
        "key": "time_bat_dis",
        "name": "Time-Sharing Battery Discharge Allow",
        "min": 0,
        "max": 1,
        "step": 1,
        "default": 0,
        "unit": None,
        "setter": "set_time_bat_dis",
        "allowed_values": [0, 1],
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

    def __init__(
        self,
        hub: SAJModbusHub,
        name: str,
        unique_id: str,
        min_val: float,
        max_val: float,
        step: float,
        default: float,
        device_info: dict[str, Any],
        unit: str | None = None,
    ) -> None:
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
    def native_value(self) -> float | None:
        return self._attr_native_value

class SajGenericNumberEntity(SajNumberEntity):
    """Generic class for SAJ number entities."""
    def __init__(
        self,
        hub: SAJModbusHub,
        name: str,
        unique_id: str,
        min_val: float,
        max_val: float,
        step: float,
        default: float,
        device_info: dict[str, Any],
        unit: str | None = None,
        set_method_name: str | None = None,
        allowed_values: list[int] | None = None,
    ) -> None:
        super().__init__(hub, name, unique_id, min_val, max_val, step, default, device_info, unit)
        self.set_method = getattr(hub, set_method_name) if set_method_name else None
        self._allowed_values = allowed_values

    async def async_set_native_value(self, value: float) -> None:
        val = int(value)
        if self._allowed_values is not None:
            if val not in self._allowed_values:
                _LOGGER.error("Invalid value for %s: %s (allowed: %s)", self._attr_name, val, self._allowed_values)
                return
        elif not self._attr_native_min_value <= val <= self._attr_native_max_value:
            _LOGGER.error("Invalid value for %s: %s", self._attr_name, val)
            return
        self._attr_native_value = val
        if self.set_method:
            await self.set_method(val)
        self.async_write_ha_state()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
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
            allowed_values=desc.get("allowed_values"),
        )
        entities.append(entity)

    # Add charge slot entities (1-7) using utility function
    charge_definitions = generate_slot_definitions("charge")
    for desc in charge_definitions["number"]:
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

    # Add discharge slot entities (1-7) using utility function
    discharge_definitions = generate_slot_definitions("discharge")
    for desc in discharge_definitions["number"]:
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
