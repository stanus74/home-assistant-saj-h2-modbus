"""The SAJ Modbus integration."""
import logging
import time
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL, Platform

from .hub import SAJModbusHub
from .const import (
    DOMAIN, 
    ATTR_MANUFACTURER, 
    DEFAULT_SCAN_INTERVAL, 
    DEFAULT_PORT, 
    CONF_FAST_ENABLED, 
)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.TEXT]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


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
        "device_info": _create_device_info(entry)
    }

    # Start the main coordinator scheduling
    await hub.start_main_coordinator()
    _LOGGER.info("Main coordinator scheduling started")

    # Start fast updates only if enabled in hub
    if hub.fast_enabled:
        await hub.start_fast_updates()
        _LOGGER.info("Fast coordinator started (10s interval)")
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
    # Perform hub-specific unload first (stops fast coordinator, closes client)
    hub: SAJModbusHub | None = hass.data[DOMAIN].get(entry.entry_id, {}).get("hub")
    if hub is not None:
        try:
            await hub.async_unload_entry()
        except Exception as e:
            _LOGGER.debug(f"Ignoring hub unload error: {e}")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    else:
        _LOGGER.warning("Unload platforms failed for entry %s; Hub remains registered in hass.data", entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options and restart fast updates if needed."""
    hub: SAJModbusHub | None = hass.data[DOMAIN].get(entry.entry_id, {}).get("hub")
    if hub is not None:
        await hub.update_connection_settings(
            host=_get_config_value(entry, CONF_HOST),
            port=_get_config_value(entry, CONF_PORT, DEFAULT_PORT),
            scan_interval=_get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            fast_enabled=_get_config_value(entry, CONF_FAST_ENABLED, False),
            ultra_fast_enabled=_get_config_value(entry, "ultra_fast_enabled", False),
            mqtt_host=_get_config_value(entry, "mqtt_host", ""),
            mqtt_port=_get_config_value(entry, "mqtt_port", 1883),
            mqtt_user=_get_config_value(entry, "mqtt_user", ""),
            mqtt_password=_get_config_value(entry, "mqtt_password", ""),
            mqtt_topic_prefix=_get_config_value(entry, "mqtt_topic_prefix", "saj"),
            mqtt_publish_all=_get_config_value(entry, "mqtt_publish_all", False),
            use_ha_mqtt=_get_config_value(entry, "use_ha_mqtt", False),
        )
    else:
        # If hub doesn't exist, reload the entry to create it with new options
        await hass.config_entries.async_reload(entry.entry_id)


def _get_config_value(entry: ConfigEntry, key: str, default=None):
    """Get config value with fallback from options to data."""
    # Import CONF_FAST_ENABLED from const.py
    from .const import CONF_FAST_ENABLED
    return entry.options.get(key, entry.data.get(key, default))


async def _create_hub(hass: HomeAssistant, entry: ConfigEntry) -> SAJModbusHub:
    """Helper function to create the SAJ Modbus hub."""
    try:
        # Get fast_enabled setting from config entry options or data
        fast_enabled = _get_config_value(entry, CONF_FAST_ENABLED, False)
        
        # Ensure the scan_interval is correctly passed to the hub
        scan_interval = _get_config_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        _LOGGER.info(f"Setting scan interval to {scan_interval} seconds")
        _LOGGER.info("Starting hub with first refresh...")

        hub = SAJModbusHub(
            hass,
            entry,  # <-- Das gesamte ConfigEntry-Objekt übergeben
        )
        hub.fast_enabled = fast_enabled
        
        await hub.async_config_entry_first_refresh()
        _LOGGER.info(f"Hub first refresh completed, coordinator should run every {scan_interval} seconds")
        
        return hub
    except Exception as e:
        _LOGGER.error(f"Failed to set up SAJ Modbus hub: {e}")
        return None


def _create_device_info(entry: ConfigEntry) -> dict:
    """Create device info for SAJ Modbus hub."""
    return {
        "identifiers": {(DOMAIN, entry.data[CONF_NAME])},
        "name": entry.data[CONF_NAME],
        "manufacturer": ATTR_MANUFACTURER
    }