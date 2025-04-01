"""The SAJ Modbus Integration."""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.typing import ConfigType

from .hub import SAJModbusHub
from .const import DOMAIN, ATTR_MANUFACTURER, DEFAULT_SCAN_INTERVAL

# This integration is config entry only, so we use the helper
CONFIG_SCHEMA = vol.Schema({DOMAIN: cv.config_entry_only_schema()}, extra=vol.ALLOW_EXTRA)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "text"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SAJ Modbus component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a SAJ Modbus entry."""
    hub = await _create_hub(hass, entry)
    
    if not hub:
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "device_info": _create_device_info(entry)
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hub = hass.data[DOMAIN][entry.entry_id]["hub"]
        if hasattr(hub, "_client") and hub._client:
            try:
                # Markiere den Hub als im Schließprozess
                hub._closing = True
                
                # Warte auf den nächsten Update-Zyklus oder schließe direkt
                from .modbus_utils import close as modbus_close
                await modbus_close(hub._client)
                
                _LOGGER.info("SAJ Modbus connection closed successfully")
            except Exception as e:
                _LOGGER.error(f"Error closing SAJ Modbus connection: {e}")
                
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def _create_hub(hass: HomeAssistant, entry: ConfigEntry) -> SAJModbusHub:
    """Helper function to create the SAJ Modbus hub."""
    try:
        # Erstelle den Hub
        hub = SAJModbusHub(
            hass,
            entry.data[CONF_NAME],
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        
        # Führe den ersten Refresh durch - dieser wird bereits versuchen,
        # eine Verbindung herzustellen und Daten abzurufen
        await hub.async_config_entry_first_refresh()
        
        # Wenn wir hier ankommen, war der erste Refresh erfolgreich
        # oder hat zumindest keine Ausnahme ausgelöst
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
