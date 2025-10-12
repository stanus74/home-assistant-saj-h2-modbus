"""The SAJ Modbus Integration."""
import logging
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL

from .hub import SAJModbusHub
from .const import DOMAIN, ATTR_MANUFACTURER, DEFAULT_SCAN_INTERVAL, DEFAULT_PORT
from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "text"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SAJ Modbus component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a SAJ Modbus entry."""
    _LOGGER.debug("Starting async_setup_entry")
    start_time = time.monotonic()
    
    hub = await _create_hub(hass, entry)
    
    if not hub:
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "fast_coordinator": hub._fast_coordinator,
        "device_info": _create_device_info(entry)
    }

   
    # Starte nur, wenn in hub aktiviert
    if hub.fast_enabled:
        await hub.start_fast_updates()
        # Store the unsubscribe callback for proper cleanup during unload
        fast_unsub = hub._fast_coordinator.async_add_listener(lambda: None)
        entry.async_on_unload(fast_unsub)
    else:
        _LOGGER.info("Fast coordinator not started (disabled).")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    end_time = time.monotonic()
    elapsed_time = end_time - start_time
    _LOGGER.debug(f"async_setup_entry completed in {elapsed_time:.2f} seconds")
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Hub-spezifischen Unload zuerst ausführen (stoppt Fast-Coordinator, schließt Client)
    hub: SAJModbusHub | None = hass.data[DOMAIN].get(entry.entry_id, {}).get("hub")
    if hub is not None:
        try:
            await hub.async_unload_entry()
        except Exception as e:
            _LOGGER.debug("Ignoring hub unload error: %s", e)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options and restart fast updates if needed."""
    hub: SAJModbusHub | None = hass.data[DOMAIN].get(entry.entry_id, {}).get("hub")
    if hub is not None:
        await hub.update_connection_settings(
            host=_get_config_value(entry, CONF_HOST),
            port=_get_config_value(entry, CONF_PORT, DEFAULT_PORT),
            scan_interval=_get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    else:
        await hass.config_entries.async_reload(entry.entry_id)

def _get_config_value(entry: ConfigEntry, key: str, default=None):
    """Get config value with fallback from options to data."""
    return entry.options.get(key, entry.data.get(key, default))

async def _create_hub(hass: HomeAssistant, entry: ConfigEntry) -> SAJModbusHub:
    """Helper function to create the SAJ Modbus hub."""
    try:
        hub = SAJModbusHub(
            hass,
            entry.data[CONF_NAME],  # Name is always in data, not in options
            _get_config_value(entry, CONF_HOST),
            _get_config_value(entry, CONF_PORT, DEFAULT_PORT),
            _get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            # Optional: hier könnte später aus Options/Env fast_enabled eingelesen werden
            fast_enabled=None,
        )
        # Ensure the scan_interval is correctly passed to the hub
        scan_interval = _get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        _LOGGER.debug(f"Setting scan interval to {scan_interval} seconds")
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
