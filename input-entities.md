# SAJ H2 Modbus - Input Entities

This list contains all writable entities created by `number.py` and `text.py`.
Assumed Device Name: `SAJ` (default).

## Text Entities (Time Settings)

These entities allow setting start and end times for charge/discharge slots (Format: HH:MM).

| Name | Entity ID |
| :--- | :--- |
| Charge Start Time | `text.saj_charge_start_time` |
| Charge End Time | `text.saj_charge_end_time` |
| Charge 2 Start Time | `text.saj_charge_2_start_time` |
| Charge 2 End Time | `text.saj_charge_2_end_time` |
| Charge 3 Start Time | `text.saj_charge_3_start_time` |
| Charge 3 End Time | `text.saj_charge_3_end_time` |
| Charge 4 Start Time | `text.saj_charge_4_start_time` |
| Charge 4 End Time | `text.saj_charge_4_end_time` |
| Charge 5 Start Time | `text.saj_charge_5_start_time` |
| Charge 5 End Time | `text.saj_charge_5_end_time` |
| Charge 6 Start Time | `text.saj_charge_6_start_time` |
| Charge 6 End Time | `text.saj_charge_6_end_time` |
| Charge 7 Start Time | `text.saj_charge_7_start_time` |
| Charge 7 End Time | `text.saj_charge_7_end_time` |
| Discharge Start Time | `text.saj_discharge_start_time` |
| Discharge End Time | `text.saj_discharge_end_time` |
| Discharge 2 Start Time | `text.saj_discharge_2_start_time` |
| Discharge 2 End Time | `text.saj_discharge_2_end_time` |
| Discharge 3 Start Time | `text.saj_discharge_3_start_time` |
| Discharge 3 End Time | `text.saj_discharge_3_end_time` |
| Discharge 4 Start Time | `text.saj_discharge_4_start_time` |
| Discharge 4 End Time | `text.saj_discharge_4_end_time` |
| Discharge 5 Start Time | `text.saj_discharge_5_start_time` |
| Discharge 5 End Time | `text.saj_discharge_5_end_time` |
| Discharge 6 Start Time | `text.saj_discharge_6_start_time` |
| Discharge 6 End Time | `text.saj_discharge_6_end_time` |
| Discharge 7 Start Time | `text.saj_discharge_7_start_time` |
| Discharge 7 End Time | `text.saj_discharge_7_end_time` |

## Number Entities (Settings & Limits)

These entities allow configuring power limits, percentages, and other numeric values.

### Charge/Discharge Configuration
| Name | Entity ID |
| :--- | :--- |
| Charge Day Mask | `number.saj_charge_day_mask` |
| Charge Power Percent | `number.saj_charge_power_percent` |
| Charge 2 Day Mask | `number.saj_charge_2_day_mask` |
| Charge 2 Power Percent | `number.saj_charge_2_power_percent` |
| Charge 3 Day Mask | `number.saj_charge_3_day_mask` |
| Charge 3 Power Percent | `number.saj_charge_3_power_percent` |
| Charge 4 Day Mask | `number.saj_charge_4_day_mask` |
| Charge 4 Power Percent | `number.saj_charge_4_power_percent` |
| Charge 5 Day Mask | `number.saj_charge_5_day_mask` |
| Charge 5 Power Percent | `number.saj_charge_5_power_percent` |
| Charge 6 Day Mask | `number.saj_charge_6_day_mask` |
| Charge 6 Power Percent | `number.saj_charge_6_power_percent` |
| Charge 7 Day Mask | `number.saj_charge_7_day_mask` |
| Charge 7 Power Percent | `number.saj_charge_7_power_percent` |
| Discharge Day Mask | `number.saj_discharge_day_mask` |
| Discharge Power Percent | `number.saj_discharge_power_percent` |
| Discharge 2 Day Mask | `number.saj_discharge_2_day_mask` |
| Discharge 2 Power Percent | `number.saj_discharge_2_power_percent` |
| Discharge 3 Day Mask | `number.saj_discharge_3_day_mask` |
| Discharge 3 Power Percent | `number.saj_discharge_3_power_percent` |
| Discharge 4 Day Mask | `number.saj_discharge_4_day_mask` |
| Discharge 4 Power Percent | `number.saj_discharge_4_power_percent` |
| Discharge 5 Day Mask | `number.saj_discharge_5_day_mask` |
| Discharge 5 Power Percent | `number.saj_discharge_5_power_percent` |
| Discharge 6 Day Mask | `number.saj_discharge_6_day_mask` |
| Discharge 6 Power Percent | `number.saj_discharge_6_power_percent` |
| Discharge 7 Day Mask | `number.saj_discharge_7_day_mask` |
| Discharge 7 Power Percent | `number.saj_discharge_7_power_percent` |
| Charge Time Enable Bitmask | `number.saj_charge_time_enable_bitmask` |
| Discharge Time Enable Bitmask | `number.saj_discharge_time_enable_bitmask` |

### Passive Mode Settings
| Name | Entity ID |
| :--- | :--- |
| Passive Charge Enable | `number.saj_passive_charge_enable` |
| Passive Grid Charge Power | `number.saj_passive_grid_charge_power` |
| Passive Grid Discharge Power | `number.saj_passive_grid_discharge_power` |
| Passive Battery Charge Power | `number.saj_passive_battery_charge_power` |
| Passive Battery Discharge Power | `number.saj_passive_battery_discharge_power` |

### Battery & Grid Limits
| Name | Entity ID |
| :--- | :--- |
| Battery on grid discharge depth | `number.saj_battery_on_grid_discharge_depth` |
| Battery offgrid discharge depth | `number.saj_battery_offgrid_discharge_depth` |
| Battery charge depth | `number.saj_battery_charge_depth` |
| Battery Charge Power Limit | `number.saj_battery_charge_power_limit` |
| Battery Discharge Power Limit | `number.saj_battery_discharge_power_limit` |
| Grid Charge Power Limit | `number.saj_grid_charge_power_limit` |
| Grid Discharge Power Limit | `number.saj_grid_discharge_power_limit` |

### Anti-Reflux (Export Control)
| Name | Entity ID |
| :--- | :--- |
| Anti-Reflux Power Limit | `number.saj_anti_reflux_power_limit` |
| Anti-Reflux Current Limit | `number.saj_anti_reflux_current_limit` |
| Anti-Reflux Current Mode | `number.saj_anti_reflux_current_mode` |