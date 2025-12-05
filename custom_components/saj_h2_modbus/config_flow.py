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
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"
CONF_MQTT_PUBLISH_ALL = "mqtt_publish_all"

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

    def _get_topic_prefix_default(self) -> str:
        """Prefer non-empty option prefix, fallback to data, then 'saj'."""
        opt = (self.config_entry.options.get(CONF_MQTT_TOPIC_PREFIX) or "").strip()
        if opt:
            return opt
        data_val = (self.config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "") or "").strip()
        return data_val or "saj"

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            merged = dict(user_input)
            merged.setdefault(CONF_SCAN_INTERVAL, self._get_option_default(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            merged.setdefault(CONF_FAST_ENABLED, self._get_option_default(CONF_FAST_ENABLED, False))
            merged.setdefault(CONF_ULTRA_FAST_ENABLED, self._get_option_default(CONF_ULTRA_FAST_ENABLED, False))
            # Enforce fast poll when ultra-fast is active
            if merged.get(CONF_ULTRA_FAST_ENABLED):
                merged[CONF_FAST_ENABLED] = True
            merged.setdefault(CONF_MQTT_HOST, self._get_option_default(CONF_MQTT_HOST, ""))
            merged.setdefault(CONF_MQTT_PORT, self._get_option_default(CONF_MQTT_PORT, 1883))
            merged.setdefault(CONF_MQTT_USER, self._get_option_default(CONF_MQTT_USER, ""))
            merged.setdefault(CONF_MQTT_PASSWORD, self._get_option_default(CONF_MQTT_PASSWORD, ""))
            topic_prefix_default = self._get_topic_prefix_default()
            topic_prefix = (merged.get(CONF_MQTT_TOPIC_PREFIX, topic_prefix_default) or "").strip()
            merged[CONF_MQTT_TOPIC_PREFIX] = topic_prefix or topic_prefix_default
            merged[CONF_MQTT_PUBLISH_ALL] = merged.get(
                CONF_MQTT_PUBLISH_ALL,
                self._get_option_default(CONF_MQTT_PUBLISH_ALL, False),
            )
            try:
                hub = self.hass.data[DOMAIN][self.config_entry.entry_id]["hub"]
                await hub.update_connection_settings(
                    merged[CONF_HOST],
                    merged[CONF_PORT],
                    merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    merged.get(CONF_FAST_ENABLED, False),
                    merged.get(CONF_ULTRA_FAST_ENABLED, False),
                    merged.get(CONF_MQTT_HOST, ""),
                    merged.get(CONF_MQTT_PORT, 1883),
                    merged.get(CONF_MQTT_USER, ""),
                    merged.get(CONF_MQTT_PASSWORD, ""),
                    merged[CONF_MQTT_TOPIC_PREFIX],
                    merged[CONF_MQTT_PUBLISH_ALL],
                )
            except Exception as e:
                _LOGGER.error("Error updating SAJ Modbus configuration: %s", e)
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "update_failed"}
                )

            updated_data = dict(self.config_entry.data)
            for key in (
                CONF_HOST,
                CONF_PORT,
                CONF_SCAN_INTERVAL,
                CONF_FAST_ENABLED,
                CONF_ULTRA_FAST_ENABLED,
                CONF_MQTT_HOST,
                CONF_MQTT_PORT,
                CONF_MQTT_USER,
                CONF_MQTT_PASSWORD,
                CONF_MQTT_TOPIC_PREFIX,
                CONF_MQTT_PUBLISH_ALL,
            ):
                if key == CONF_MQTT_TOPIC_PREFIX:
                    updated_data[key] = merged[CONF_MQTT_TOPIC_PREFIX] or updated_data.get(key, "saj")
                elif key == CONF_FAST_ENABLED and merged.get(CONF_ULTRA_FAST_ENABLED):
                    updated_data[key] = True
                else:
                    updated_data[key] = merged.get(key, updated_data.get(key))
            self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)
            return self.async_create_entry(title="", data=merged)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema()
        )

    def _get_options_schema(self):
        host_default = self._get_option_default(CONF_HOST, self.config_entry.data.get(CONF_HOST))
        port_default = self._get_option_default(CONF_PORT, self.config_entry.data.get(CONF_PORT, DEFAULT_PORT))
        scan_default = self._get_option_default(CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        fast_default = self._get_option_default(CONF_FAST_ENABLED, False)
        ultra_fast_default = self._get_option_default(CONF_ULTRA_FAST_ENABLED, False)
        mqtt_host_default = self._get_option_default(CONF_MQTT_HOST, "")
        mqtt_port_default = self._get_option_default(CONF_MQTT_PORT, 1883)
        mqtt_user_default = self._get_option_default(CONF_MQTT_USER, "")
        mqtt_password_default = self._get_option_default(CONF_MQTT_PASSWORD, "")
        mqtt_prefix_default = self._get_topic_prefix_default()
        mqtt_publish_all_default = self._get_option_default(CONF_MQTT_PUBLISH_ALL, False)
        return vol.Schema({
            vol.Required(CONF_HOST, default=host_default): str,
            vol.Required(CONF_PORT, default=port_default): int,
            vol.Optional(CONF_SCAN_INTERVAL, default=scan_default): int,
            vol.Optional(CONF_FAST_ENABLED, default=fast_default): bool,
            vol.Optional(
                CONF_ULTRA_FAST_ENABLED,
                default=ultra_fast_default,
                description={"name": "Ultra Fast (1s over MQTT)"},
            ): bool,
            vol.Optional(CONF_MQTT_HOST, default=mqtt_host_default): str,
            vol.Optional(CONF_MQTT_PORT, default=mqtt_port_default): int,
            vol.Optional(CONF_MQTT_USER, default=mqtt_user_default): str,
            vol.Optional(CONF_MQTT_PASSWORD, default=mqtt_password_default): str,
            vol.Optional(CONF_MQTT_TOPIC_PREFIX, default=mqtt_prefix_default): str,
            vol.Optional(CONF_MQTT_PUBLISH_ALL, default=mqtt_publish_all_default): bool,
        })
