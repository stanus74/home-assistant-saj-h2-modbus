import ipaddress
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
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
