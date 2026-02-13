"""Utility functions for SAJ H2 Modbus integration."""
from typing import Any, Optional
from homeassistant.config_entries import ConfigEntry


def get_config_value(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    """Get config value with fallback: options -> data -> default.

    This function retrieves configuration values from a ConfigEntry,
    checking first in options (user-customized values), then in data
    (initial configuration), and finally returning a default if neither exists.

    Args:
        entry: The ConfigEntry to retrieve the value from.
        key: The configuration key to look up.
        default: The default value to return if key is not found. Defaults to None.

    Returns:
        The configuration value or the default if not found.

    Example:
        >>> get_config_value(entry, "scan_interval", 60)
        60
    """
    return entry.options.get(key, entry.data.get(key, default))
