"""Utility functions for SAJ H2 Modbus integration."""
from typing import Any, Optional, Dict, List
from homeassistant.config_entries import ConfigEntry


def generate_slot_definitions(slot_type: str, count: int = 7) -> Dict[str, List[Dict]]:
    """Generate slot entity definitions for charge/discharge schedules.
    
    This function generates entity definitions for time slots (1-7) used in
    charge and discharge scheduling. Each slot has:
    - Number entities: day_mask and power_percent
    - Text entities: start_time and end_time
    
    Args:
        slot_type: The type of slot ('charge' or 'discharge')
        count: Number of slots to generate (default 7)
        
    Returns:
        Dictionary with 'number' and 'text' keys containing lists of entity definitions
        
    Example:
        >>> definitions = generate_slot_definitions('charge')
        >>> len(definitions['number'])
        14  # 7 slots * 2 entities (day_mask, power_percent)
        >>> len(definitions['text'])
        14  # 7 slots * 2 entities (start_time, end_time)
    """
    number_definitions = []
    text_definitions = []
    
    for i in range(1, count + 1):
        prefix = str(i)
        
        # Number entities: day_mask and power_percent
        number_definitions.extend([
            {
                "key": f"{slot_type}{prefix}_day_mask",
                "name": f"{slot_type.capitalize()}{prefix} Day Mask",
                "min": 0,
                "max": 127,
                "step": 1,
                "default": 127,
                "unit": None,
                "setter": f"set_{slot_type}{prefix}_day_mask",
            },
            {
                "key": f"{slot_type}{prefix}_power_percent",
                "name": f"{slot_type.capitalize()}{prefix} Power Percent",
                "min": 0,
                "max": 100,
                "step": 1,
                "default": 5,
                "unit": "%",
                "setter": f"set_{slot_type}{prefix}_power_percent",
            },
        ])
        
        # Text entities: start_time and end_time
        text_definitions.extend([
            {
                "key": f"{slot_type}{prefix}_start_time",
                "name": f"{slot_type.capitalize()}{prefix} Start Time",
                "unique_id_suffix": f"_{slot_type}{prefix}_start_time",
                "setter": f"set_{slot_type}{prefix}_start",
            },
            {
                "key": f"{slot_type}{prefix}_end_time",
                "name": f"{slot_type.capitalize()}{prefix} End Time",
                "unique_id_suffix": f"_{slot_type}{prefix}_end_time",
                "setter": f"set_{slot_type}{prefix}_end",
            },
        ])
    
    return {
        "number": number_definitions,
        "text": text_definitions,
    }


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
