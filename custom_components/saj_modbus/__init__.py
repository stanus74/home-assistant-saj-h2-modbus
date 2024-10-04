"""The SAJ Modbus Integration."""
import asyncio
import logging
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

# Importiere config_flow und andere relevante Module am Anfang der Datei
from .config_flow import SAJModbusConfigFlow  # Statischer Import, um Laufzeitprobleme zu vermeiden
from .hub import SAJModbusHub  # Statischer Import des Hubs

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,  # Stelle sicher, dass DEFAULT_PORT korrekt importiert wird
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Schema für manuelle Konfiguration in YAML
SAJ_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,  # cv.port für Integer-Ports
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: SAJ_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["sensor"]

async def async_setup(hass, config):
    """Set up the SAJ Modbus component."""
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a SAJ Modbus entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.debug("Setting up %s.%s", DOMAIN, name)

    # Initialisiere den Hub mit den konfigurierten Werten
    hub = SAJModbusHub(hass, name, host, port, scan_interval)
    await hub.async_config_entry_first_refresh()

    # Registriere den Hub in hass.data, um darauf zugreifen zu können
    hass.data[DOMAIN][name] = {"hub": hub}

    # Leite die Einrichtung der Sensorplattform weiter
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listener für Änderungen der Optionen (OptionsFlow)
    entry.async_on_unload(
        entry.add_update_listener(async_update_entry)
    )

    return True

async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle an update to the config entry (e.g. new IP, port, or scan interval)."""
    name = entry.data[CONF_NAME]
    hub: SAJModbusHub = hass.data[DOMAIN][name]["hub"]

    new_host = entry.data[CONF_HOST]
    new_port = entry.data[CONF_PORT]
    new_scan_interval = entry.data[CONF_SCAN_INTERVAL]

    _LOGGER.info(f"Updating SAJ Modbus hub configuration for {name}...")

    # Update der Hub-Einstellungen (neue IP, neuer Port, neues Scan-Intervall)
    await hub.update_connection_settings(new_host, new_port, new_scan_interval)

    _LOGGER.info(f"SAJ Modbus hub configuration updated for {name}.")
