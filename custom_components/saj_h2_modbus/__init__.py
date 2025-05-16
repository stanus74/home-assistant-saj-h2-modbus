"""The SAJ Modbus Integration."""
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL, CONF_ICON
from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import config_validation as cv

from .hub import SAJModbusHub
from .const import DOMAIN, ATTR_MANUFACTURER, DEFAULT_SCAN_INTERVAL

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "text"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SAJ Modbus component."""
    hass.data.setdefault(DOMAIN, {})
    return True

# Definitions of input_number entities
INPUT_NUMBERS = [
    {
        "name": "SAJ Charge Day Mask",
        "id": "saj_charge_day_mask",
        "min": 0,
        "max": 127,
        "step": 1,
        "mode": "box",
        "initial": 127,
        "icon": "mdi:calendar",
        "entity_id": "number.saj_charge_day_mask_input"
    },
    {
        "name": "SAJ Charge Power Percent",
        "id": "saj_charge_power_percent",
        "min": 0,
        "max": 25,
        "step": 1,
        "mode": "box",
        "initial": 5,
        "icon": "mdi:flash",
        "entity_id": "number.saj_charge_power_percent_input"
    },
    {
        "name": "SAJ Discharge Day Mask",
        "id": "saj_discharge_day_mask",
        "min": 0,
        "max": 127,
        "step": 1,
        "mode": "box",
        "initial": 127,
        "icon": "mdi:calendar",
        "entity_id": "number.saj_discharge_day_mask_input"
    },
    {
        "name": "SAJ Discharge Power Percent",
        "id": "saj_discharge_power_percent",
        "min": 0,
        "max": 100,
        "step": 1,
        "mode": "box",
        "initial": 5,
        "icon": "mdi:flash",
        "entity_id": "number.saj_discharge_power_percent_input"
    },
    {
        "name": "SAJ Export Limit",
        "id": "saj_export_limit",
        "min": 0,
        "max": 1000,
        "step": 100,
        "mode": "box",
        "initial": 0,
        "icon": "mdi:flash-outline",
        "entity_id": "number.saj_export_limit_input"
    },
    {
        "name": "SAJ App Mode",
        "id": "saj_app_mode",
        "min": 0,
        "max": 3,
        "step": 1,
        "mode": "box",
        "initial": 0,
        "icon": "mdi:information-outline",
        "entity_id": "number.saj_app_mode_input"
    }
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a SAJ Modbus entry."""
    hub = await _create_hub(hass, entry)
    
    if not hub:
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "device_info": _create_device_info(entry),
        "input_number_mapping": {}
    }

    # Create input_number entities
    await _create_input_numbers(hass, entry, hub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def _create_input_numbers(hass, entry, hub):
    """Registers event listeners for input_number entities."""
    
    # Store the mapping between input_number and NumberEntity
    for input_def in INPUT_NUMBERS:
        input_number_entity_id = f"input_number.{input_def['id']}"
        hass.data[DOMAIN][entry.entry_id]["input_number_mapping"][input_number_entity_id] = input_def["entity_id"]
        
        # Check if the entity exists and set the initial value
        if hass.states.get(input_number_entity_id):
            _LOGGER.info(f"Found input_number entity: {input_number_entity_id}")
            
            # Get the current value of the NumberEntity
            number_entity = hass.states.get(input_def["entity_id"])
            if number_entity:
                # Set the value of the input_number entity
                try:
                    await hass.services.async_call(
                        INPUT_NUMBER_DOMAIN,
                        "set_value",
                        {
                            "entity_id": input_number_entity_id,
                            "value": float(number_entity.state)
                        },
                        blocking=False
                    )
                    _LOGGER.info(f"Set initial value for {input_number_entity_id} to {number_entity.state}")
                except Exception as e:
                    _LOGGER.error(f"Error setting initial value for {input_number_entity_id}: {e}")
        else:
            _LOGGER.warning(f"Input number entity not found: {input_number_entity_id}")
            _LOGGER.warning(f"Please add the following to your configuration.yaml:")
            _LOGGER.warning(f"""
input_number:
  {input_def['id']}:
    name: {input_def['name']}
    min: {input_def['min']}
    max: {input_def['max']}
    step: {input_def['step']}
    mode: {input_def['mode']}
    icon: {input_def['icon']}
""")
    
    # Register listeners for changes to input_number entities
    @callback
    def handle_input_number_change(event):
        """Handles changes to input_number entities."""
        entity_id = event.data.get("entity_id")
        value = event.data.get("value")
        
        _LOGGER.debug(f"Input number change event: {entity_id} = {value}")
        
        # Check if the entity belongs to our integration
        mapping = hass.data[DOMAIN][entry.entry_id].get("input_number_mapping", {})
        if entity_id in mapping:
            number_entity_id = mapping[entity_id]
            _LOGGER.info(f"Handling input_number change: {entity_id} -> {number_entity_id} = {value}")
            
            # Call the corresponding method in the hub
            try:
            # Use a thread-safe approach
            # Create a function to be executed in the event loop
                async def update_entity():
                    # Call the corresponding method in the hub
                    if "charge_day_mask" in entity_id:
                        await hub.set_charge_day_mask(int(value))
                    elif "charge_power_percent" in entity_id:
                        await hub.set_charge_power_percent(int(value))
                    elif "discharge_day_mask" in entity_id:
                        await hub.set_discharge_day_mask(int(value))
                    elif "discharge_power_percent" in entity_id:
                        await hub.set_discharge_power_percent(int(value))
                    elif "export_limit" in entity_id:
                        await hub.set_export_limit(int(value))
                    elif "app_mode" in entity_id:
                        await hub.set_app_mode(int(value))
                    
                    # Also update the NumberEntity
                    number_entity = hass.states.get(number_entity_id)
                    if number_entity:
                        # Find the entity in the Entity Registry
                        entity_registry = er.async_get(hass)
                        entity = entity_registry.async_get(number_entity_id)
                        if entity and entity.platform == DOMAIN:
                            # Set the value of the NumberEntity
                            for component in hass.data.get("entity_components", {}).values():
                                for entity_obj in component.entities:
                                    if entity_obj.entity_id == number_entity_id:
                                        _LOGGER.info(f"Setting {number_entity_id} to {value}")
                                        entity_obj._attr_native_value = float(value)
                                        entity_obj.async_write_ha_state()
                                        break
                
                # Schedule execution in the event loop
                hass.loop.call_soon_threadsafe(
                    lambda: hass.create_task(update_entity())
                )
            except Exception as e:
                _LOGGER.error(f"Error handling input_number change: {e}")
    
    # Store the event handler in hass.data
    hass.data[DOMAIN][entry.entry_id]["handle_input_number_change"] = handle_input_number_change
    
    # Register the event listener for various possible event names
    hass.bus.async_listen("state_changed", lambda event: _handle_state_changed(event, hass, entry, hub))
    hass.bus.async_listen(f"{INPUT_NUMBER_DOMAIN}.change", handle_input_number_change)

# Helper function for handling state_changed events
def _handle_state_changed(event, hass, entry, hub):
    """Handles state_changed events for input_number entities."""
    entity_id = event.data.get("entity_id")
    if not entity_id or not entity_id.startswith("input_number.saj_"):
        return
    
    old_state = event.data.get("old_state")
    new_state = event.data.get("new_state")
    
    if not old_state or not new_state or old_state.state == new_state.state:
        return
    
    _LOGGER.debug(f"State changed for {entity_id}: {old_state.state} -> {new_state.state}")
    
    # Create an Event object for the input_number.change handler
    class EventData:
        def __init__(self, entity_id, value):
            self.data = {"entity_id": entity_id, "value": value}
    
    # Call the input_number.change handler
    handle_input_number_change = hass.data[DOMAIN][entry.entry_id].get("handle_input_number_change")
    if handle_input_number_change:
        handle_input_number_change(EventData(entity_id, float(new_state.state)))
    else:
        _LOGGER.error(f"handle_input_number_change not found for {entity_id}")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def _create_hub(hass: HomeAssistant, entry: ConfigEntry) -> SAJModbusHub:
    """Helper function to create the SAJ Modbus hub."""
    try:
        hub = SAJModbusHub(
            hass,
            entry.data[CONF_NAME],
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await hub.async_config_entry_first_refresh()
        return hub
    except Exception as e:
        _LOGGER.error(f"Failed to set up SAJ Modbus hub: {e}")
        return None

def _create_device_info(entry: ConfigEntry) -> dict:
    """Create the device info for SAJ Modbus hub."""
    return {
        "identifiers": {(DOMAIN, entry.data[CONF_NAME])},
        "name": entry.data[CONF_NAME],
        "manufacturer": ATTR_MANUFACTURER
    }
