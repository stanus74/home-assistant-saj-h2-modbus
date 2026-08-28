"""The SAJ Modbus integration."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    Platform,
)

from .const import (
    DOMAIN,
    ATTR_MANUFACTURER,
    DEFAULT_SCAN_INTERVAL,
    CONF_FAST_ENABLED,
    DEFAULT_CONFIG_SCHEMA,
)
from homeassistant.helpers import config_validation as cv
from .utils import get_config_value, get_config_values

if TYPE_CHECKING:
    from .hub import SAJModbusHub, SAJConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.TEXT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the SAJ Modbus component."""
    # Per-entry state lives in entry.runtime_data; no global hass.data needed.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Set up a SAJ Modbus entry."""
    _LOGGER.debug("Starting async_setup_entry")
    start_time = time.monotonic()

    hub = await _create_hub(hass, entry)
    hub.device_info = _create_device_info(entry)
    _update_device_info_from_inverter_data(hub)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Start fast updates only after the entity platforms are set up, so the
    # first fast tick never fires before the fast listeners are registered.
    #
    # Both flags have to be checked here, exactly as update_connection_settings()
    # does: start_fast_updates() starts the 1 s ultra-fast loop from its own
    # branch, independent of fast_enabled. Checking fast_enabled alone left an
    # ultra-fast-only setup — the sensible choice for anyone consuming the live
    # data over MQTT — without any loop after every restart, while still working
    # right after saving the options.
    if hub.fast_enabled or hub.ultra_fast_enabled:
        await hub.start_fast_updates()
        _LOGGER.info(
            "Fast update loops started (fast=%s, ultra_fast=%s)",
            hub.fast_enabled,
            hub.ultra_fast_enabled,
        )
    else:
        _LOGGER.info("Fast update loops not started (both disabled).")

    end_time = time.monotonic()
    elapsed_time = end_time - start_time
    _LOGGER.debug(f"async_setup_entry completed in {elapsed_time:.2f} seconds")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms first so entities can still access a fully functional
    # hub during their own teardown, then tear down the hub itself (stops
    # fast coordinator, closes client).
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hub = getattr(entry, "runtime_data", None)
    if hub is not None:
        try:
            await hub.async_unload_entry()
        except Exception as e:
            _LOGGER.debug(f"Ignoring hub unload error: {e}")

    if not unload_ok:
        _LOGGER.warning(
            "Unload platforms failed for entry %s; hub teardown still attempted",
            entry.entry_id,
        )
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: SAJConfigEntry) -> None:
    """Update options and restart fast updates if needed."""
    hub: SAJModbusHub | None = getattr(entry, "runtime_data", None)
    if hub is not None:
        config = get_config_values(entry, DEFAULT_CONFIG_SCHEMA)
        await hub.update_connection_settings(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            scan_interval=config[CONF_SCAN_INTERVAL],
            fast_enabled=config[CONF_FAST_ENABLED],
            ultra_fast_enabled=config["ultra_fast_enabled"],
            mqtt_host=config["mqtt_host"],
            mqtt_port=config["mqtt_port"],
            mqtt_user=config["mqtt_user"],
            mqtt_password=config["mqtt_password"],
            mqtt_topic_prefix=config["mqtt_topic_prefix"],
            mqtt_publish_all=config["mqtt_publish_all"],
            use_ha_mqtt=config["use_ha_mqtt"],
        )
    else:
        # If hub doesn't exist, reload the entry to create it with new options
        await hass.config_entries.async_reload(entry.entry_id)


async def _create_hub(hass: HomeAssistant, entry: ConfigEntry) -> SAJModbusHub:
    """Helper function to create the SAJ Modbus hub."""
    try:
        # Get fast_enabled setting from config entry options or data
        fast_enabled = get_config_value(entry, CONF_FAST_ENABLED, False)

        # Ensure the scan_interval is correctly passed to the hub
        scan_interval = get_config_value(
            entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        _LOGGER.info(f"Setting scan interval to {scan_interval} seconds")
        _LOGGER.info("Starting hub with first refresh...")

        from .hub import SAJModbusHub

        hub = SAJModbusHub(
            hass,
            entry,  # Pass the full ConfigEntry object
        )
        hub.fast_enabled = fast_enabled

        await hub.async_config_entry_first_refresh()
        _LOGGER.info(
            f"Hub first refresh completed, coordinator should run every {scan_interval} seconds"
        )

        return hub
    except ConfigEntryNotReady:
        raise
    except Exception as e:
        _LOGGER.error(f"Failed to set up SAJ Modbus hub: {e}")
        raise ConfigEntryNotReady(
            f"Failed to set up SAJ Modbus hub: {e}"
        ) from e


def _create_device_info(entry: ConfigEntry) -> dict:
    """Create device info for SAJ Modbus hub."""
    return {
        "identifiers": {(DOMAIN, entry.data[CONF_NAME])},
        "name": entry.data[CONF_NAME],
        "manufacturer": ATTR_MANUFACTURER,
        "model": "SAJ H2",
    }


def _update_device_info_from_inverter_data(hub: SAJModbusHub) -> None:
    """Enrich device info with firmware/hardware data after first refresh."""
    data = hub.inverter_data
    if not data:
        return

    sw_parts = [
        data.get("dv"),
        data.get("mcv"),
        data.get("scv"),
    ]
    sw_version = ".".join(str(v) for v in sw_parts if v is not None)
    if sw_version:
        hub.device_info["sw_version"] = sw_version

    hw_parts = [
        data.get("disphwversion"),
        data.get("ctrlhwversion"),
        data.get("powerhwversion"),
    ]
    hw_version = ".".join(str(v) for v in hw_parts if v is not None)
    if hw_version:
        hub.device_info["hw_version"] = hw_version

    model = data.get("devtype")
    if model is not None:
        hub.device_info["model"] = f"SAJ H2 ({model})"
