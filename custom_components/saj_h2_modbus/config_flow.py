import ipaddress
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
import logging

from .const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    CONF_FAST_ENABLED,
)

CONF_ULTRA_FAST_ENABLED = "ultra_fast_enabled"
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USER = "mqtt_user"
CONF_MQTT_PASSWORD = "mqtt_password"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=60, msg="invalid_scan_interval")),
})


ERROR_ALREADY_CONFIGURED = "already_configured"
ERROR_INVALID_HOST = "invalid_host"

def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        ip_version = ipaddress.ip_address(host).version
        return ip_version in [4, 6]
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))

@callback
def saj_modbus_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)}

class SAJModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SAJ Modbus configflow."""
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        return host in saj_modbus_entries(self.hass)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            if self._host_in_configuration_exists(host):
                errors[CONF_HOST] = ERROR_ALREADY_CONFIGURED
            elif not host_valid(host):
                errors[CONF_HOST] = ERROR_INVALID_HOST
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow to allow configuration changes after setup."""
        return SAJModbusOptionsFlowHandler(config_entry)


class SAJModbusOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    """Handle an options flow for SAJ Modbus."""

    def _get_option_default(self, key, default):
        """Get option default value from options or data."""
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            try:
                hub = self.hass.data[DOMAIN][self.config_entry.entry_id]["hub"]
                await hub.update_connection_settings(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input.get(CONF_SCAN_INTERVAL, 60),
                    user_input.get(CONF_FAST_ENABLED, False),
                    user_input.get(CONF_ULTRA_FAST_ENABLED, False),
                    user_input.get(CONF_MQTT_HOST, ""),
                    user_input.get(CONF_MQTT_PORT, 1883),
                    user_input.get(CONF_MQTT_USER, ""),
                    user_input.get(CONF_MQTT_PASSWORD, ""),
                )
            except Exception as e:
                _LOGGER.error("Error updating SAJ Modbus configuration: %s", e)
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "update_failed"}
                )

            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema()
        )

    def _get_options_schema(self):
        return vol.Schema({
            vol.Required(CONF_HOST, default=self.config_entry.options.get(CONF_HOST, self.config_entry.data.get(CONF_HOST))): str,
            vol.Required(CONF_PORT, default=self.config_entry.options.get(CONF_PORT, self.config_entry.data.get(CONF_PORT, 502))): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, 60))): int,
            vol.Optional(CONF_FAST_ENABLED, default=self.config_entry.options.get(CONF_FAST_ENABLED, False)): bool,
            vol.Optional(CONF_ULTRA_FAST_ENABLED, default=self.config_entry.options.get(CONF_ULTRA_FAST_ENABLED, False)): bool,
            vol.Optional(CONF_MQTT_HOST, default=self.config_entry.options.get(CONF_MQTT_HOST, "")): str,
            vol.Optional(CONF_MQTT_PORT, default=self.config_entry.options.get(CONF_MQTT_PORT, 1883)): int,
            vol.Optional(CONF_MQTT_USER, default=self.config_entry.options.get(CONF_MQTT_USER, "")): str,
            vol.Optional(CONF_MQTT_PASSWORD, default=self.config_entry.options.get(CONF_MQTT_PASSWORD, "")): str,
        })
