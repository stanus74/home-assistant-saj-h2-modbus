"""The SAJ Modbus Integration."""
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .hub import SAJModbusHub
from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ATTR_MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SAJ Modbus component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a SAJ Modbus entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("Setting up %s.%s", DOMAIN, name)

    hub = SAJModbusHub(hass, name, host, port, scan_interval)
    await hub.async_config_entry_first_refresh()

    device_info = {"identifiers": {(DOMAIN, name)}, "name": name, "manufacturer": ATTR_MANUFACTURER}

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "device_info": device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hub = hass.data[DOMAIN][entry.entry_id]["hub"]
        await hub.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an update to the config entry."""
    hub: SAJModbusHub = hass.data[DOMAIN][entry.entry_id]["hub"]

    new_host = entry.data[CONF_HOST]
    new_port = entry.data[CONF_PORT]
    new_scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.info(f"Updating SAJ Modbus hub configuration for {entry.title}...")

    await hub.update_connection_settings(new_host, new_port, new_scan_interval)

    _LOGGER.info(f"SAJ Modbus hub configuration updated for {entry.title}.")

    await hass.config_entries.async_reload(entry.entry_id)
