# SAJ H2 Modbus Registers – Integration Sensor Overview

This table lists **only** the Modbus registers that are actually read by the Home Assistant integration (`custom_components/saj_h2_modbus`), together with the corresponding sensor entity and the name shown in Home Assistant.

Source of the register addresses: `modbus_readers.py` (decode maps), cross-checked with `const.py` (`SENSOR_TYPES`).

**Mode:** `R` = read-only (all registers listed here are only read; for write registers / `number.*` entities see the section at the end).

**Display name in HA:** Composed of the device name (default: `SAJ`, configurable when setting up the integration) and the sensor name (`_attr_has_entity_name = True` in `sensor.py`). If the device is renamed, the `SAJ` prefix changes accordingly.

Note: Some registers (e.g. schedule registers with day mask + percentage value, or combined status texts such as `mpvstatus`/`faultmsg`) provide data for **multiple** sensor entities from the same physical register.

| Register | Sensor entity | Mode | Display name in HA |
|---|---|---|---|
| `3604H` | `sensor.saj_charge_time_enable_bitmask` | R | SAJ Charge Time Enable Bitmask |
| `3605H` | `sensor.saj_discharge_time_enable_bitmask` | R | SAJ Discharge Time Enable Bitmask |
| `3606H` | `sensor.saj_charge_start_time` | R | SAJ Charge Start Time |
| `3607H` | `sensor.saj_charge_end_time` | R | SAJ Charge End Time |
| `3608H` | `sensor.saj_charge_day_mask` | R | SAJ Charge Day Mask |
| `3608H` | `sensor.saj_charge_power_percent` | R | SAJ Charge Power Percent |
| `3609H` | `sensor.saj_charge_2_start_time` | R | SAJ Charge 2 Start Time |
| `360AH` | `sensor.saj_charge_2_end_time` | R | SAJ Charge 2 End Time |
| `360BH` | `sensor.saj_charge_2_day_mask` | R | SAJ Charge 2 Day Mask |
| `360BH` | `sensor.saj_charge_2_power_percent` | R | SAJ Charge 2 Power Percent |
| `360CH` | `sensor.saj_charge_3_start_time` | R | SAJ Charge 3 Start Time |
| `360DH` | `sensor.saj_charge_3_end_time` | R | SAJ Charge 3 End Time |
| `360EH` | `sensor.saj_charge_3_day_mask` | R | SAJ Charge 3 Day Mask |
| `360EH` | `sensor.saj_charge_3_power_percent` | R | SAJ Charge 3 Power Percent |
| `360FH` | `sensor.saj_charge_4_start_time` | R | SAJ Charge 4 Start Time |
| `3610H` | `sensor.saj_charge_4_end_time` | R | SAJ Charge 4 End Time |
| `3611H` | `sensor.saj_charge_4_day_mask` | R | SAJ Charge 4 Day Mask |
| `3611H` | `sensor.saj_charge_4_power_percent` | R | SAJ Charge 4 Power Percent |
| `3612H` | `sensor.saj_charge_5_start_time` | R | SAJ Charge 5 Start Time |
| `3613H` | `sensor.saj_charge_5_end_time` | R | SAJ Charge 5 End Time |
| `3614H` | `sensor.saj_charge_5_day_mask` | R | SAJ Charge 5 Day Mask |
| `3614H` | `sensor.saj_charge_5_power_percent` | R | SAJ Charge 5 Power Percent |
| `3615H` | `sensor.saj_charge_6_start_time` | R | SAJ Charge 6 Start Time |
| `3616H` | `sensor.saj_charge_6_end_time` | R | SAJ Charge 6 End Time |
| `3617H` | `sensor.saj_charge_6_day_mask` | R | SAJ Charge 6 Day Mask |
| `3617H` | `sensor.saj_charge_6_power_percent` | R | SAJ Charge 6 Power Percent |
| `3618H` | `sensor.saj_charge_7_start_time` | R | SAJ Charge 7 Start Time |
| `3619H` | `sensor.saj_charge_7_end_time` | R | SAJ Charge 7 End Time |
| `361AH` | `sensor.saj_charge_7_day_mask` | R | SAJ Charge 7 Day Mask |
| `361AH` | `sensor.saj_charge_7_power_percent` | R | SAJ Charge 7 Power Percent |
| `361BH` | `sensor.saj_discharge_start_time` | R | SAJ Discharge Start Time |
| `361CH` | `sensor.saj_discharge_end_time` | R | SAJ Discharge End Time |
| `361DH` | `sensor.saj_discharge_day_mask` | R | SAJ Discharge Day Mask |
| `361DH` | `sensor.saj_discharge_power_percent` | R | SAJ Discharge Power Percent |
| `361EH` | `sensor.saj_discharge_2_start_time` | R | SAJ Discharge 2 Start Time |
| `361FH` | `sensor.saj_discharge_2_end_time` | R | SAJ Discharge 2 End Time |
| `3620H` | `sensor.saj_discharge_2_day_mask` | R | SAJ Discharge 2 Day Mask |
| `3620H` | `sensor.saj_discharge_2_power_percent` | R | SAJ Discharge 2 Power Percent |
| `3621H` | `sensor.saj_discharge_3_start_time` | R | SAJ Discharge 3 Start Time |
| `3622H` | `sensor.saj_discharge_3_end_time` | R | SAJ Discharge 3 End Time |
| `3623H` | `sensor.saj_discharge_3_day_mask` | R | SAJ Discharge 3 Day Mask |
| `3623H` | `sensor.saj_discharge_3_power_percent` | R | SAJ Discharge 3 Power Percent |
| `3624H` | `sensor.saj_discharge_4_start_time` | R | SAJ Discharge 4 Start Time |
| `3625H` | `sensor.saj_discharge_4_end_time` | R | SAJ Discharge 4 End Time |
| `3626H` | `sensor.saj_discharge_4_day_mask` | R | SAJ Discharge 4 Day Mask |
| `3626H` | `sensor.saj_discharge_4_power_percent` | R | SAJ Discharge 4 Power Percent |
| `3627H` | `sensor.saj_discharge_5_start_time` | R | SAJ Discharge 5 Start Time |
| `3628H` | `sensor.saj_discharge_5_end_time` | R | SAJ Discharge 5 End Time |
| `3629H` | `sensor.saj_discharge_5_day_mask` | R | SAJ Discharge 5 Day Mask |
| `3629H` | `sensor.saj_discharge_5_power_percent` | R | SAJ Discharge 5 Power Percent |
| `362AH` | `sensor.saj_discharge_6_start_time` | R | SAJ Discharge 6 Start Time |
| `362BH` | `sensor.saj_discharge_6_end_time` | R | SAJ Discharge 6 End Time |
| `362CH` | `sensor.saj_discharge_6_day_mask` | R | SAJ Discharge 6 Day Mask |
| `362CH` | `sensor.saj_discharge_6_power_percent` | R | SAJ Discharge 6 Power Percent |
| `362DH` | `sensor.saj_discharge_7_start_time` | R | SAJ Discharge 7 Start Time |
| `362EH` | `sensor.saj_discharge_7_end_time` | R | SAJ Discharge 7 End Time |
| `362FH` | `sensor.saj_discharge_7_day_mask` | R | SAJ Discharge 7 Day Mask |
| `362FH` | `sensor.saj_discharge_7_power_percent` | R | SAJ Discharge 7 Power Percent |
| `3636H` | `sensor.saj_passive_charge_enable` | R | SAJ Passive Charge Enable |
| `3637H` | `sensor.saj_passive_grid_charge_power` | R | SAJ Passive Grid Charge Power |
| `3638H` | `sensor.saj_passive_grid_discharge_power` | R | SAJ Passive Grid Discharge Power |
| `3639H` | `sensor.saj_passive_battery_charge_power` | R | SAJ Passive Battery Charge Power |
| `363AH` | `sensor.saj_passive_battery_discharge_power` | R | SAJ Passive Battery Discharge Power |
| `3644H` | `sensor.saj_battery_on_grid_discharge_depth` | R | SAJ Battery on grid discharge depth |
| `3645H` | `sensor.saj_battery_offgrid_discharge_depth` | R | SAJ Battery offgrid discharge depth |
| `3646H` | `sensor.saj_battery_charge_depth` | R | SAJ Battery charge depth |
| `3647H` | `sensor.saj_app_mode` | R | SAJ App Mode |
| `364DH` | `sensor.saj_battery_charge_power_limit` | R | SAJ Battery Charge Power Limit |
| `364EH` | `sensor.saj_battery_discharge_power_limit` | R | SAJ Battery Discharge Power Limit |
| `364FH` | `sensor.saj_grid_charge_power_limit` | R | SAJ Grid Charge Power Limit |
| `3650H` | `sensor.saj_grid_discharge_power_limit` | R | SAJ Grid Discharge Power Limit |
| `365AH` | `sensor.saj_anti_reflux_power_limit` | R | SAJ Anti-Reflux Power Limit |
| `365BH` | `sensor.saj_anti_reflux_current_limit` | R | SAJ Anti-Reflux Current Limit |
| `365CH` | `sensor.saj_anti_reflux_current_mode` | R | SAJ Anti-Reflux Current Mode |
| `365FH` | `sensor.saj_tou_outside_mode` | R | SAJ TOU Outside Mode |
| `3660H` | `sensor.saj_time_sharing_battery_discharge_allow` | R | SAJ Time-Sharing Battery Discharge Allow |
| `4004H` | `sensor.saj_inverter_working_mode` | R | SAJ Inverter Working Mode |
| `4004H` | `sensor.saj_inverter_status` | R | SAJ Inverter Status |
| `4005H` | `sensor.saj_inverter_error_message` | R | SAJ Inverter Error Message |
| `4010H` | `sensor.saj_inverter_temperature` | R | SAJ Inverter Temperature |
| `4011H` | `sensor.saj_environment_temperature` | R | SAJ Environment Temperature |
| `4012H` | `sensor.saj_gfci` | R | SAJ GFCI |
| `4013H` | `sensor.saj_pv1_isolation_resistance` | R | SAJ PV1+ Isolation Resistance |
| `4014H` | `sensor.saj_pv2_isolation_resistance` | R | SAJ PV2+ Isolation Resistance |
| `4015H` | `sensor.saj_pv3_isolation_resistance` | R | SAJ PV3+ Isolation Resistance |
| `4016H` | `sensor.saj_pv4_isolation_resistance` | R | SAJ PV4+ Isolation Resistance |
| `4023H` | `sensor.saj_inverter_discharge_power_set` | R | SAJ Inverter Discharge Power Set |
| `4024H` | `sensor.saj_inverter_charge_power_set` | R | SAJ Inverter Charge Power Set |
| `4025H` | `sensor.saj_battery_discharge_current_set` | R | SAJ Battery Discharge Current Set |
| `4026H` | `sensor.saj_battery_charge_current_set` | R | SAJ Battery Charge Current Set |
| `4027H` | `sensor.saj_battery_status_display` | R | SAJ Battery Status Display |
| `4028H` | `sensor.saj_battery_protocol_set` | R | SAJ Battery Protocol Set |
| `4029H` | `sensor.saj_battery_charge_soc_upper_limit` | R | SAJ Battery Charge SOC Upper Limit |
| `402AH` | `sensor.saj_battery_discharge_soc_lower_limit` | R | SAJ Battery Discharge SOC Lower Limit |
| `402BH` | `sensor.saj_battery_dod_set` | R | SAJ Battery DOD Set |
| `402CH` | `sensor.saj_battery_reserved_soc` | R | SAJ Battery Reserved SOC |
| `4030H` | `sensor.saj_meter_mode_set` | R | SAJ Meter Mode Set |
| `4031H` | `sensor.saj_r_phase_grid_voltage` | R | SAJ R-Phase Grid Voltage |
| `4032H` | `sensor.saj_r_phase_grid_current` | R | SAJ R-Phase Grid Current |
| `4033H` | `sensor.saj_r_phase_grid_frequency` | R | SAJ R-Phase Grid Frequency |
| `4034H` | `sensor.saj_r_phase_grid_dc_component` | R | SAJ R-Phase Grid DC Component |
| `4035H` | `sensor.saj_r_phase_grid_power_watt` | R | SAJ R-Phase Grid Power Watt |
| `4036H` | `sensor.saj_r_phase_grid_power_va` | R | SAJ R-Phase Grid Power VA |
| `4037H` | `sensor.saj_r_phase_grid_power_factor` | R | SAJ R-Phase Grid Power Factor |
| `4038H` | `sensor.saj_s_phase_grid_voltage` | R | SAJ S-Phase Grid Voltage |
| `4039H` | `sensor.saj_s_phase_grid_current` | R | SAJ S-Phase Grid Current |
| `403AH` | `sensor.saj_s_phase_grid_frequency` | R | SAJ S-Phase Grid Frequency |
| `403BH` | `sensor.saj_s_phase_grid_dc_component` | R | SAJ S-Phase Grid DC Component |
| `403CH` | `sensor.saj_s_phase_grid_power_watt` | R | SAJ S-Phase Grid Power Watt |
| `403DH` | `sensor.saj_s_phase_grid_power_va` | R | SAJ S-Phase Grid Power VA |
| `403EH` | `sensor.saj_s_phase_grid_power_factor` | R | SAJ S-Phase Grid Power Factor |
| `403FH` | `sensor.saj_t_phase_grid_voltage` | R | SAJ T-Phase Grid Voltage |
| `4040H` | `sensor.saj_t_phase_grid_current` | R | SAJ T-Phase Grid Current |
| `4041H` | `sensor.saj_t_phase_grid_frequency` | R | SAJ T-Phase Grid Frequency |
| `4042H` | `sensor.saj_t_phase_grid_dc_component` | R | SAJ T-Phase Grid DC Component |
| `4043H` | `sensor.saj_t_phase_grid_power_watt` | R | SAJ T-Phase Grid Power Watt |
| `4044H` | `sensor.saj_t_phase_grid_power_va` | R | SAJ T-Phase Grid Power VA |
| `4045H` | `sensor.saj_t_phase_grid_power_factor` | R | SAJ T-Phase Grid Power Factor |
| `4046H` | `sensor.saj_r_phase_inverter_voltage` | R | SAJ R-Phase Inverter Voltage |
| `4047H` | `sensor.saj_r_phase_inverter_current` | R | SAJ R-Phase Inverter Current |
| `4048H` | `sensor.saj_r_phase_inverter_frequency` | R | SAJ R-Phase Inverter Frequency |
| `4049H` | `sensor.saj_r_phase_inverter_power_watt` | R | SAJ R-Phase Inverter Power Watt |
| `404AH` | `sensor.saj_r_phase_inverter_power_va` | R | SAJ R-Phase Inverter Power VA |
| `404BH` | `sensor.saj_s_phase_inverter_voltage` | R | SAJ S-Phase Inverter Voltage |
| `404CH` | `sensor.saj_s_phase_inverter_current` | R | SAJ S-Phase Inverter Current |
| `404DH` | `sensor.saj_s_phase_inverter_frequency` | R | SAJ S-Phase Inverter Frequency |
| `404EH` | `sensor.saj_s_phase_inverter_power_watt` | R | SAJ S-Phase Inverter Power Watt |
| `404FH` | `sensor.saj_s_phase_inverter_power_va` | R | SAJ S-Phase Inverter Power VA |
| `4050H` | `sensor.saj_t_phase_inverter_voltage` | R | SAJ T-Phase Inverter Voltage |
| `4051H` | `sensor.saj_t_phase_inverter_current` | R | SAJ T-Phase Inverter Current |
| `4052H` | `sensor.saj_t_phase_inverter_frequency` | R | SAJ T-Phase Inverter Frequency |
| `4053H` | `sensor.saj_t_phase_inverter_power_watt` | R | SAJ T-Phase Inverter Power Watt |
| `4054H` | `sensor.saj_t_phase_inverter_power_va` | R | SAJ T-Phase Inverter Power VA |
| `4055H` | `sensor.saj_r_phase_off_grid_voltage` | R | SAJ R-Phase Off-Grid Voltage |
| `4056H` | `sensor.saj_r_phase_off_grid_current` | R | SAJ R-Phase Off-Grid Current |
| `4057H` | `sensor.saj_r_phase_off_grid_frequency` | R | SAJ R-Phase Off-Grid Frequency |
| `4058H` | `sensor.saj_r_phase_off_grid_dvi` | R | SAJ R-Phase Off-Grid DVI |
| `4059H` | `sensor.saj_r_phase_off_grid_power_watt` | R | SAJ R-Phase Off-Grid Power Watt |
| `405AH` | `sensor.saj_r_phase_off_grid_power_va` | R | SAJ R-Phase Off-Grid Power VA |
| `405BH` | `sensor.saj_s_phase_off_grid_voltage` | R | SAJ S-Phase Off-Grid Voltage |
| `405CH` | `sensor.saj_s_phase_off_grid_current` | R | SAJ S-Phase Off-Grid Current |
| `405DH` | `sensor.saj_s_phase_off_grid_frequency` | R | SAJ S-Phase Off-Grid Frequency |
| `405EH` | `sensor.saj_s_phase_off_grid_dvi` | R | SAJ S-Phase Off-Grid DVI |
| `405FH` | `sensor.saj_s_phase_off_grid_power_watt` | R | SAJ S-Phase Off-Grid Power Watt |
| `4060H` | `sensor.saj_s_phase_off_grid_power_va` | R | SAJ S-Phase Off-Grid Power VA |
| `4061H` | `sensor.saj_t_phase_off_grid_voltage` | R | SAJ T-Phase Off-Grid Voltage |
| `4062H` | `sensor.saj_t_phase_off_grid_current` | R | SAJ T-Phase Off-Grid Current |
| `4063H` | `sensor.saj_t_phase_off_grid_frequency` | R | SAJ T-Phase Off-Grid Frequency |
| `4064H` | `sensor.saj_t_phase_off_grid_dvi` | R | SAJ T-Phase Off-Grid DVI |
| `4065H` | `sensor.saj_t_phase_off_grid_power_watt` | R | SAJ T-Phase Off-Grid Power Watt |
| `4066H` | `sensor.saj_t_phase_off_grid_power_va` | R | SAJ T-Phase Off-Grid Power VA |
| `406EH` | `sensor.saj_battery_temperature` | R | SAJ Battery Temperature |
| `406FH` | `sensor.saj_battery_energy_percent` | R | SAJ Battery Energy Percent |
| `4071H` | `sensor.saj_pv1_voltage` | R | SAJ PV1 Voltage |
| `4072H` | `sensor.saj_pv1_total_current` | R | SAJ PV1 Total Current |
| `4073H` | `sensor.saj_pv1_power` | R | SAJ PV1 Power |
| `4074H` | `sensor.saj_pv2_voltage` | R | SAJ PV2 Voltage |
| `4075H` | `sensor.saj_pv2_total_current` | R | SAJ PV2 Total Current |
| `4076H` | `sensor.saj_pv2_power` | R | SAJ PV2 Power |
| `4077H` | `sensor.saj_pv3_voltage` | R | SAJ PV3 Voltage |
| `4078H` | `sensor.saj_pv3_total_current` | R | SAJ PV3 Total Current |
| `4079H` | `sensor.saj_pv3_power` | R | SAJ PV3 Power |
| `407AH` | `sensor.saj_pv4_voltage` | R | SAJ PV4 Voltage |
| `407BH` | `sensor.saj_pv4_total_current` | R | SAJ PV4 Total Current |
| `407CH` | `sensor.saj_pv4_power` | R | SAJ PV4 Power |
| `408DH` | `sensor.saj_r_phase_on_grid_output_voltage` | R | SAJ R-Phase On-Grid Output Voltage |
| `408EH` | `sensor.saj_r_phase_on_grid_output_current` | R | SAJ R-Phase On-Grid Output Current |
| `408FH` | `sensor.saj_r_phase_on_grid_output_frequency` | R | SAJ R-Phase On-Grid Output Frequency |
| `4090H` | `sensor.saj_r_phase_on_grid_output_power_watt` | R | SAJ R-Phase On-Grid Output Power Watt |
| `4091H` | `sensor.saj_s_phase_on_grid_output_voltage` | R | SAJ S-Phase On-Grid Output Voltage |
| `4092H` | `sensor.saj_s_phase_on_grid_output_power_watt` | R | SAJ S-Phase On-Grid Output Power Watt |
| `4093H` | `sensor.saj_t_phase_on_grid_output_voltage` | R | SAJ T-Phase On-Grid Output Voltage |
| `4094H` | `sensor.saj_t_phase_on_grid_output_power_watt` | R | SAJ T-Phase On-Grid Output Power Watt |
| `4095H` | `sensor.saj_direction_pv` | R | SAJ Direction PV |
| `4096H` | `sensor.saj_direction_battery` | R | SAJ Direction Battery |
| `4097H` | `sensor.saj_direction_grid` | R | SAJ Direction Grid |
| `4098H` | `sensor.saj_direction_ouput` | R | SAJ Direction Ouput |
| `40A0H` | `sensor.saj_total_load_power` | R | SAJ Total Load Power |
| `40A1H` | `sensor.saj_ct_grid_power_watt` | R | SAJ CT Grid Power Watt |
| `40A2H` | `sensor.saj_ct_grid_power_va` | R | SAJ CT Grid Power VA |
| `40A3H` | `sensor.saj_ct_pv_power_watt` | R | SAJ CT PV Power Watt |
| `40A4H` | `sensor.saj_ct_pv_power_va` | R | SAJ CT PV Power VA |
| `40A5H` | `sensor.saj_pv_power` | R | SAJ PV Power |
| `40A6H` | `sensor.saj_battery_power` | R | SAJ Battery Power |
| `40A7H` | `sensor.saj_total_grid_power` | R | SAJ Total Grid Power |
| `40A8H` | `sensor.saj_total_grid_power_va` | R | SAJ Total Grid Power VA |
| `40A9H` | `sensor.saj_inverter_power` | R | SAJ Inverter Power |
| `40AAH` | `sensor.saj_total_inverter_power_va` | R | SAJ Total Inverter Power VA |
| `40ABH` | `sensor.saj_backup_total_load_power_watt` | R | SAJ Backup Total Load Power Watt |
| `40ACH` | `sensor.saj_backup_total_load_power_va` | R | SAJ Backup Total Load Power VA |
| `40ADH` | `sensor.saj_grid_load_power` | R | SAJ Grid Load Power |
| `40BFH` | `sensor.saj_power_current_day` | R | SAJ Power current day |
| `40C1H` | `sensor.saj_power_current_month` | R | SAJ Power current month |
| `40C3H` | `sensor.saj_power_current_year` | R | SAJ Power current year |
| `40C5H` | `sensor.saj_total_power_generation` | R | SAJ Total power generation |
| `40C7H` | `sensor.saj_battery_today_charge` | R | SAJ Battery Today Charge |
| `40C9H` | `sensor.saj_battery_month_charge` | R | SAJ Battery Month Charge |
| `40CBH` | `sensor.saj_battery_year_charge` | R | SAJ Battery Year Charge |
| `40CDH` | `sensor.saj_battery_total_charge` | R | SAJ Battery Total Charge |
| `40CFH` | `sensor.saj_battery_today_discharge` | R | SAJ Battery Today Discharge |
| `40D1H` | `sensor.saj_battery_month_discharge` | R | SAJ Battery Month Discharge |
| `40D3H` | `sensor.saj_battery_year_discharge` | R | SAJ Battery Year Discharge |
| `40D5H` | `sensor.saj_battery_total_discharge` | R | SAJ Battery Total Discharge |
| `40D7H` | `sensor.saj_inverter_today_generation` | R | SAJ Inverter Today Generation |
| `40D9H` | `sensor.saj_inverter_month_generation` | R | SAJ Inverter Month Generation |
| `40DBH` | `sensor.saj_inverter_year_generation` | R | SAJ Inverter Year Generation |
| `40DDH` | `sensor.saj_inverter_total_generation` | R | SAJ Inverter Total Generation |
| `40DFH` | `sensor.saj_total_today_load` | R | SAJ Total Today Load |
| `40E1H` | `sensor.saj_total_month_load` | R | SAJ Total Month Load |
| `40E3H` | `sensor.saj_total_year_load` | R | SAJ Total Year Load |
| `40E5H` | `sensor.saj_total_load` | R | SAJ Total Load |
| `40E7H` | `sensor.saj_backup_today_load` | R | SAJ Backup Today Load |
| `40E9H` | `sensor.saj_backup_month_load` | R | SAJ Backup Month Load |
| `40EBH` | `sensor.saj_backup_year_load` | R | SAJ Backup Year Load |
| `40EDH` | `sensor.saj_backup_total_load` | R | SAJ Backup Total Load |
| `40EFH` | `sensor.saj_sell_today_energy` | R | SAJ Sell Today Energy |
| `40F1H` | `sensor.saj_sell_month_energy` | R | SAJ Sell Month Energy |
| `40F3H` | `sensor.saj_sell_year_energy` | R | SAJ Sell Year Energy |
| `40F5H` | `sensor.saj_sell_total_energy` | R | SAJ Sell Total Energy |
| `40F7H` | `sensor.saj_feed_in_today_energy` | R | SAJ Feed-in Today Energy |
| `40F9H` | `sensor.saj_feed_in_month_energy` | R | SAJ Feed-in Month Energy |
| `40FBH` | `sensor.saj_feed_in_year_energy` | R | SAJ Feed-in Year Energy |
| `40FDH` | `sensor.saj_feed_in_total_energy` | R | SAJ Feed-in Total Energy |
| `4137H` | `sensor.saj_today_pv_energy_2` | R | SAJ Today PV Energy 2 |
| `4139H` | `sensor.saj_month_pv_energy_2` | R | SAJ Month PV Energy 2 |
| `413BH` | `sensor.saj_year_pv_energy_2` | R | SAJ Year PV Energy 2 |
| `413DH` | `sensor.saj_total_pv_energy_2` | R | SAJ Total PV Energy 2 |
| `413FH` | `sensor.saj_today_pv_energy_3` | R | SAJ Today PV Energy 3 |
| `4141H` | `sensor.saj_month_pv_energy_3` | R | SAJ Month PV Energy 3 |
| `4143H` | `sensor.saj_year_pv_energy_3` | R | SAJ Year PV Energy 3 |
| `4145H` | `sensor.saj_total_pv_energy_3` | R | SAJ Total PV Energy 3 |
| `4147H` | `sensor.saj_sell_today_energy_2` | R | SAJ Sell Today Energy 2 |
| `4149H` | `sensor.saj_sell_month_energy_2` | R | SAJ Sell Month Energy 2 |
| `414BH` | `sensor.saj_sell_year_energy_2` | R | SAJ Sell Year Energy 2 |
| `414DH` | `sensor.saj_sell_total_energy_2` | R | SAJ Sell Total Energy 2 |
| `414FH` | `sensor.saj_sell_today_energy_3` | R | SAJ Sell Today Energy 3 |
| `4151H` | `sensor.saj_sell_month_energy_3` | R | SAJ Sell Month Energy 3 |
| `4153H` | `sensor.saj_sell_year_energy_3` | R | SAJ Sell Year Energy 3 |
| `4155H` | `sensor.saj_sell_total_energy_3` | R | SAJ Sell Total Energy 3 |
| `4157H` | `sensor.saj_feed_in_today_energy_2` | R | SAJ Feed-In Today Energy 2 |
| `4159H` | `sensor.saj_feed_in_month_energy_2` | R | SAJ Feed-In Month Energy 2 |
| `415BH` | `sensor.saj_feed_in_year_energy_2` | R | SAJ Feed-In Year Energy 2 |
| `415DH` | `sensor.saj_feed_in_total_energy_2` | R | SAJ Feed-In Total Energy 2 |
| `415FH` | `sensor.saj_feed_in_today_energy_3` | R | SAJ Feed-In Today Energy 3 |
| `4161H` | `sensor.saj_feed_in_month_energy_3` | R | SAJ Feed-In Month Energy 3 |
| `4163H` | `sensor.saj_feed_in_year_energy_3` | R | SAJ Feed-In Year Energy 3 |
| `4165H` | `sensor.saj_feed_in_total_energy_3` | R | SAJ Feed-In Total Energy 3 |
| `4167H` | `sensor.saj_sum_all_phases_feed_in_today` | R | SAJ Sum All Phases Feed-In Today |
| `4169H` | `sensor.saj_sum_all_phases_feed_in_month` | R | SAJ Sum All Phases Feed-In Month |
| `416BH` | `sensor.saj_sum_all_phases_feed_in_year` | R | SAJ Sum All Phases Feed-In Year |
| `416DH` | `sensor.saj_sum_all_phases_feed_in_total` | R | SAJ Sum All Phases Feed-In Total |
| `416FH` | `sensor.saj_sum_all_phases_sell_today` | R | SAJ Sum All Phases Sell Today |
| `4171H` | `sensor.saj_sum_all_phases_sell_month` | R | SAJ Sum All Phases Sell Month |
| `4173H` | `sensor.saj_sum_all_phases_sell_year` | R | SAJ Sum All Phases Sell Year |
| `4175H` | `sensor.saj_sum_all_phases_sell_total` | R | SAJ Sum All Phases Sell Total |
| `8F00H` | `sensor.saj_device_type` | R | SAJ Device Type |
| `8F01H` | `sensor.saj_sub_type` | R | SAJ Sub Type |
| `8F02H` | `sensor.saj_comms_protocol_version` | R | SAJ Comms Protocol Version |
| `8F03H` | `sensor.saj_serial_number` | R | SAJ Serial Number |
| `8F0DH` | `sensor.saj_product_code` | R | SAJ Product Code |
| `8F17H` | `sensor.saj_display_software_version` | R | SAJ Display Software Version |
| `8F18H` | `sensor.saj_master_ctrl_software_version` | R | SAJ Master Ctrl Software Version |
| `8F19H` | `sensor.saj_slave_ctrl_software_version` | R | SAJ Slave Ctrl Software Version |
| `8F1AH` | `sensor.saj_display_board_hardware_version` | R | SAJ Display Board Hardware Version |
| `8F1BH` | `sensor.saj_control_board_hardware_version` | R | SAJ Control Board Hardware Version |
| `8F1CH` | `sensor.saj_power_board_hardware_version` | R | SAJ Power Board Hardware Version |
| `A000H` | `sensor.saj_battery_number` | R | SAJ Battery Number |
| `A001H` | `sensor.saj_battery_capacity` | R | SAJ Battery Capacity |
| `A002H` | `sensor.saj_battery_1_fault` | R | SAJ Battery 1 Fault |
| `A003H` | `sensor.saj_battery_1_warning` | R | SAJ Battery 1 Warning |
| `A004H` | `sensor.saj_battery_2_fault` | R | SAJ Battery 2 Fault |
| `A005H` | `sensor.saj_battery_2_warning` | R | SAJ Battery 2 Warning |
| `A006H` | `sensor.saj_battery_3_fault` | R | SAJ Battery 3 Fault |
| `A007H` | `sensor.saj_battery_3_warning` | R | SAJ Battery 3 Warning |
| `A008H` | `sensor.saj_battery_4_fault` | R | SAJ Battery 4 Fault |
| `A009H` | `sensor.saj_battery_4_warning` | R | SAJ Battery 4 Warning |
| `A00AH` | `sensor.saj_battery_user_capacity` | R | SAJ Battery User Capacity |
| `A00BH` | `sensor.saj_battery_online` | R | SAJ Battery Online |
| `A00CH` | `sensor.saj_battery_1_soc` | R | SAJ Battery 1 SOC |
| `A00DH` | `sensor.saj_battery_1_soh` | R | SAJ Battery 1 SOH |
| `A00EH` | `sensor.saj_battery_1_voltage` | R | SAJ Battery 1 Voltage |
| `A00FH` | `sensor.saj_battery_1_current` | R | SAJ Battery 1 Current |
| `A010H` | `sensor.saj_battery_1_temperature` | R | SAJ Battery 1 Temperature |
| `A011H` | `sensor.saj_battery_1_cycle_count` | R | SAJ Battery 1 Cycle Count |
| `A012H` | `sensor.saj_battery_2_soc` | R | SAJ Battery 2 SOC |
| `A013H` | `sensor.saj_battery_2_soh` | R | SAJ Battery 2 SOH |
| `A014H` | `sensor.saj_battery_2_voltage` | R | SAJ Battery 2 Voltage |
| `A015H` | `sensor.saj_battery_2_current` | R | SAJ Battery 2 Current |
| `A016H` | `sensor.saj_battery_2_temperature` | R | SAJ Battery 2 Temperature |
| `A017H` | `sensor.saj_battery_2_cycle_count` | R | SAJ Battery 2 Cycle Count |
| `A018H` | `sensor.saj_battery_3_soc` | R | SAJ Battery 3 SOC |
| `A019H` | `sensor.saj_battery_3_soh` | R | SAJ Battery 3 SOH |
| `A01AH` | `sensor.saj_battery_3_voltage` | R | SAJ Battery 3 Voltage |
| `A01BH` | `sensor.saj_battery_3_current` | R | SAJ Battery 3 Current |
| `A01CH` | `sensor.saj_battery_3_temperature` | R | SAJ Battery 3 Temperature |
| `A01DH` | `sensor.saj_battery_3_cycle_count` | R | SAJ Battery 3 Cycle Count |
| `A01EH` | `sensor.saj_battery_4_soc` | R | SAJ Battery 4 SOC |
| `A01FH` | `sensor.saj_battery_4_soh` | R | SAJ Battery 4 SOH |
| `A020H` | `sensor.saj_battery_4_voltage` | R | SAJ Battery 4 Voltage |
| `A021H` | `sensor.saj_battery_4_current` | R | SAJ Battery 4 Current |
| `A022H` | `sensor.saj_battery_4_temperature` | R | SAJ Battery 4 Temperature |
| `A023H` | `sensor.saj_battery_4_cycle_count` | R | SAJ Battery 4 Cycle Count |
| `A02AH` | `sensor.saj_battery_pack_1_discharge` | R | SAJ Battery Pack 1 Discharge |
| `A02CH` | `sensor.saj_battery_pack_2_discharge` | R | SAJ Battery Pack 2 Discharge |
| `A02EH` | `sensor.saj_battery_pack_3_discharge` | R | SAJ Battery Pack 3 Discharge |
| `A030H` | `sensor.saj_battery_pack_4_discharge` | R | SAJ Battery Pack 4 Discharge |
| `A032H` | `sensor.saj_battery_voltage_high_protection` | R | SAJ Battery Voltage High Protection |
| `A033H` | `sensor.saj_battery_voltage_low_warning` | R | SAJ Battery Voltage Low Warning |
| `A034H` | `sensor.saj_battery_charge_voltage` | R | SAJ Battery Charge Voltage |
| `A035H` | `sensor.saj_battery_discharge_cut_off_voltage` | R | SAJ Battery Discharge Cut-off Voltage |
| `A036H` | `sensor.saj_battery_discharge_current_limit` | R | SAJ Battery Discharge Current Limit |
| `A037H` | `sensor.saj_battery_charge_current_limit` | R | SAJ Battery Charge Current Limit |
| `A03DH` | `sensor.saj_meter_a_voltage_1` | R | SAJ Meter A Voltage 1 |
| `A03DH` | `sensor.saj_ct_grid_power_total` | R | SAJ CT Grid Power Total |
| `A03EH` | `sensor.saj_meter_a_current_1` | R | SAJ Meter A Current 1 |
| `A03FH` | `sensor.saj_meter_a_real_power_1` | R | SAJ Meter A Real Power 1 |
| `A040H` | `sensor.saj_meter_a_apparent_power_1` | R | SAJ Meter A Apparent Power 1 |
| `A041H` | `sensor.saj_meter_a_power_factor_1` | R | SAJ Meter A Power Factor 1 |
| `A042H` | `sensor.saj_meter_a_frequency_1` | R | SAJ Meter A Frequency 1 |
| `A043H` | `sensor.saj_meter_a_voltage_2` | R | SAJ Meter A Voltage 2 |
| `A044H` | `sensor.saj_meter_a_current_2` | R | SAJ Meter A Current 2 |
| `A045H` | `sensor.saj_meter_a_real_power_2` | R | SAJ Meter A Real Power 2 |
| `A046H` | `sensor.saj_meter_a_apparent_power_2` | R | SAJ Meter A Apparent Power 2 |
| `A047H` | `sensor.saj_meter_a_power_factor_2` | R | SAJ Meter A Power Factor 2 |
| `A048H` | `sensor.saj_meter_a_frequency_2` | R | SAJ Meter A Frequency 2 |
| `A049H` | `sensor.saj_meter_a_voltage_3` | R | SAJ Meter A Voltage 3 |
| `A04AH` | `sensor.saj_meter_a_current_3` | R | SAJ Meter A Current 3 |
| `A04BH` | `sensor.saj_meter_a_real_power_3` | R | SAJ Meter A Real Power 3 |
| `A04CH` | `sensor.saj_meter_a_apparent_power_3` | R | SAJ Meter A Apparent Power 3 |
| `A04DH` | `sensor.saj_meter_a_power_factor_3` | R | SAJ Meter A Power Factor 3 |
| `A04EH` | `sensor.saj_meter_a_frequency_3` | R | SAJ Meter A Frequency 3 |

### Inverter status codes (`4004H`)

Register `4004H` provides two sensors: `sensor.saj_inverter_working_mode` returns
the raw numeric mode (`mpvmode`), and `sensor.saj_inverter_status` returns the
decoded text below (`mpvmode` → text via `DEVICE_STATUSSES` in `const.py`;
decoded in `modbus_readers.py`). Unknown values are shown as `Unknown`.

This is also the sensor that distinguishes **on-grid vs off-grid** operation:
value **3** = off-grid, value **4** = on-grid.

| Value | `sensor.saj_inverter_status` text |
|---|---|
| 0 | Initialization |
| 1 | Waiting |
| 2 | Running |
| 3 | Offnet mode, used for energy storage *(off-grid)* |
| 4 | Grid on-load mode, used for energy storage *(on-grid)* |
| 5 | Fault |
| 6 | Update |
| 7 | Test |
| 8 | Self-checking |
| 9 | Reset |

## Writable input entities (`number.*`)

These registers are written via `number` entities (see `number.py` / `charge_control.py`). They are read/write (`R/W`).

**Values are raw register values.** Inputs and their matching sensors show exactly the number stored in the register, without scaling. The power settings (`3637H`–`363AH`, `364DH`–`3650H`, `365AH`) are in 0.1 % of rated power: `500` = 50 %, `1100` = 110 %. On an 8 kW inverter `500` is 4000 W, so watts = value / 1000 × rated power. They accept 0–1100 in steps of 10 (1 %). The battery limits `3644H`/`3645H` accept 5–100 %, `3646H` (maximum SOC the battery is charged to) 20–100 %, as specified by the protocol.

*Entity IDs are those of a new installation. Installations that predate a rename keep their old IDs, e.g. `sensor.saj_battary_on_grid_discharge_depth`.*

| Register | Entity | Mode | Description |
|---|---|---|---|
| `3604H` | `number.saj_charge_time_enable_input` | R/W | Charge time enable control |
| `3605H` | `number.saj_discharge_time_enable_input` | R/W | Discharge time enable control |
| `3636H` | `number.saj_passive_charge_enable_input` | R/W | Passive charge and discharge Enabled (Effective when 0x3647 is in Passive Mode) 0: Standby 1: Discharge 2: Charge |
| `3637H` | `number.saj_passive_grid_charge_power_input` | R/W | Passive grid charge power |
| `3638H` | `number.saj_passive_grid_discharge_power_input` | R/W | Passive discharge power grid (the |
| `3639H` | `number.saj_passive_battery_charge_power_input` | R/W | Passive battery power (the percentage of setting values for rated power systems, such as the system rated power is 5000 w, expected to set the discharge power of 2500 w, (2500/5000) * 1000 = 500) |
| `363AH` | `number.saj_passive_battery_discharge_power_input` | R/W | Passive battery Discharge power |
| `3644H` | `number.saj_battery_on_grid_discharge_depth_input` | R/W | Battery grid discharge limit (maximum charging battery capacity > battery grid discharge limit + 5) |
| `3645H` | `number.saj_battery_off_grid_discharge_depth_input` | R/W | Off-grid battery discharge threshold (battery discharge grid floor > battery off-grid discharge limit + 5) |
| `3646H` | `number.saj_battery_capacity_charge_upper_limit_input` | R/W | Battery charging capacity limit (maximum charging battery capacity > backup reserve value maximum charging battery capacity > battery SOC grid discharge limit + 5) |
| `3647H` | `number.saj_app_mode_input` | R/W | Inverter application mode 0x00 Self-use_mode 0x01 time_mode 0x02 backup_mode 0x03 passive_mode 0x0E aging mode |
| `364DH` | `number.saj_battery_charge_power_limit_input` | R/W | Battery power limit (set values for the system of the percentage of the rated power, rated power is 5000 w, such as the system expected to set the discharge power of 2500 w, (2500/5000) * 1000 = 500) |
| `364EH` | `number.saj_battery_discharge_power_limit_input` | R/W | Battery discharge power limit |
| `364FH` | `number.saj_grid_max_charge_power_input` | R/W | Biggest buy electric power grid (system allows from the grid into the maximum power of inverter, the percentage of setting values for rated power systems, such as the system rated power is 5000 w, expected to set the discharge power of 2500 w, (2500/5000) * 1000 = 500) |
| `3650H` | `number.saj_grid_max_discharge_power_input` | R/W | The electrical grid biggest selling (system allows maximum power from inverter power grid, set the value for the system of the percentage of the rated power, rated power is 5000 w, such as the system expected to set the discharge power of 2500 w, (2500/5000) * 1000 = 500) |
| `365AH` | `number.saj_export_limit_input` | R/W | Prevent reverse flow limit power (0x365C register for 1 or 3 effect: when 0x365C is 1: the register is total power anti-reflux; when 0x365C is 3: the register is phase power anti-reflux value) |
| `365FH` | `number.saj_tou_outside_mode_input` | R/W | The charging and discharging period is not available in time-sharing mode |
| `3660H` | `number.saj_time_sharing_battery_discharge_allow_input` | R/W | The charging and discharging period is available in time-sharing mode |
| `3608H` | `number.saj_charge1_day_mask_input` | R/W | First date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3608H` | `number.saj_charge1_power_percent_input` | R/W | First date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `360BH` | `number.saj_charge2_day_mask_input` | R/W | The second date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. |
| `360BH` | `number.saj_charge2_power_percent_input` | R/W | The second date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. |
| `360EH` | `number.saj_charge3_day_mask_input` | R/W | Wire 3 date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `360EH` | `number.saj_charge3_power_percent_input` | R/W | Wire 3 date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3611H` | `number.saj_charge4_day_mask_input` | R/W | Wire 4 date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3611H` | `number.saj_charge4_power_percent_input` | R/W | Wire 4 date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3614H` | `number.saj_charge5_day_mask_input` | R/W | Wire 5 of the date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3614H` | `number.saj_charge5_power_percent_input` | R/W | Wire 5 of the date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3617H` | `number.saj_charge6_day_mask_input` | R/W | Wire 6. The date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3617H` | `number.saj_charge6_power_percent_input` | R/W | Wire 6. The date of charging and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `361AH` | `number.saj_charge7_day_mask_input` | R/W | Wire 7 date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the |
| `361AH` | `number.saj_charge7_power_percent_input` | R/W | Wire 7 date and charging power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the |
| `361DH` | `number.saj_discharge1_day_mask_input` | R/W | The first date of discharge and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `361DH` | `number.saj_discharge1_power_percent_input` | R/W | The first date of discharge and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3620H` | `number.saj_discharge2_day_mask_input` | R/W | Wire 2 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3620H` | `number.saj_discharge2_power_percent_input` | R/W | Wire 2 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3623H` | `number.saj_discharge3_day_mask_input` | R/W | Wire 3 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of |
| `3623H` | `number.saj_discharge3_power_percent_input` | R/W | Wire 3 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of |
| `3626H` | `number.saj_discharge4_day_mask_input` | R/W | Wire 4 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3626H` | `number.saj_discharge4_power_percent_input` | R/W | Wire 4 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `3629H` | `number.saj_discharge5_day_mask_input` | R/W | Wire 5 of the discharge date and power (high byte |
| `3629H` | `number.saj_discharge5_power_percent_input` | R/W | Wire 5 of the discharge date and power (high byte |
| `362CH` | `number.saj_discharge6_day_mask_input` | R/W | Wire 6 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `362CH` | `number.saj_discharge6_power_percent_input` | R/W | Wire 6 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `362FH` | `number.saj_discharge7_day_mask_input` | R/W | Wire 7 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |
| `362FH` | `number.saj_discharge7_power_percent_input` | R/W | Wire 7 the discharge date and power (high byte said Thursday, each position can make, such as 0 b0100 said Wednesday. The lower position indicates the power. For example, 1 indicates 1 percent of the standard power of the model. |

> ⚠️ **Important note:** These `number.*` entities are used solely to write a value **into** the respective register. They are **not** synchronized with or read back from the actual value in the inverter. To monitor the value actually stored in the device, use the corresponding `sensor.*` entity from the table above.

## Writable time entities (`text.*`)

Start/end times of the 7 charge and 7 discharge slots are written via `text` entities in `HH:MM` format (see `text.py` / `utils.generate_slot_definitions`). They are read/write (`R/W`) and write to the same registers that are also read back as `sensor.*` (see the main table above).

| Register | Entity | Mode | Description |
|---|---|---|---|
| `3606H` | `text.saj_charge1_start_time_time` | R/W | The first charging starting time (high byte for hours, low byte for minutes; hh: mm) |
| `3607H` | `text.saj_charge1_end_time_time` | R/W | The first charge over time (high byte for hours, low byte for minutes; hh : mm) |
| `3609H` | `text.saj_charge2_start_time_time` | R/W | Wire 2 the charging starting time (high byte for hours, low byte for minutes; hh : mm) |
| `360AH` | `text.saj_charge2_end_time_time` | R/W | Wire 2 the charging end time (high byte for hours, low byte for minutes; hh : mm) |
| `360CH` | `text.saj_charge3_start_time_time` | R/W | Wire 3 the charging starting time (high byte for hours, low byte for minutes; hh : mm) |
| `360DH` | `text.saj_charge3_end_time_time` | R/W | Wire 3 the charging end time (high byte for hours, low byte for minutes; hh : mm) |
| `360FH` | `text.saj_charge4_start_time_time` | R/W | Wire 4 the charging starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3610H` | `text.saj_charge4_end_time_time` | R/W | Wire 4 the charging end time (high byte for hours, low byte for minutes; hh : |
| `3612H` | `text.saj_charge5_start_time_time` | R/W | Wire 5 the charging starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3613H` | `text.saj_charge5_end_time_time` | R/W | Wire 5 the charging end time (high byte for hours, low byte for minutes; hh : mm) |
| `3615H` | `text.saj_charge6_start_time_time` | R/W | Wire 6 the charging starting |
| `3616H` | `text.saj_charge6_end_time_time` | R/W | Wire 6 the charging end time (high byte for hours, low byte for minutes; hh : mm) |
| `3618H` | `text.saj_charge7_start_time_time` | R/W | Wire 7 the charging starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3619H` | `text.saj_charge7_end_time_time` | R/W | Wire 7 the charging end time (high byte for hours, low byte for minutes; hh : mm) |
| `361BH` | `text.saj_discharge1_start_time_time` | R/W | The first discharge starting time (high byte for hours, low byte for minutes; hh : mm) |
| `361CH` | `text.saj_discharge1_end_time_time` | R/W | The first discharge end time (high byte for hours, low byte for minutes; hh : mm) |
| `361EH` | `text.saj_discharge2_start_time_time` | R/W | The second discharge starting time (high byte for hours, low byte for minutes; hh : mm) |
| `361FH` | `text.saj_discharge2_end_time_time` | R/W | Wire 2 the discharge end time (high byte for hours, low byte |
| `3621H` | `text.saj_discharge3_start_time_time` | R/W | Wire 3 the discharge starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3622H` | `text.saj_discharge3_end_time_time` | R/W | Wire 3 the discharge end time (high byte for hours, low byte for minutes; hh : mm) |
| `3624H` | `text.saj_discharge4_start_time_time` | R/W | Wire 4 the discharge starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3625H` | `text.saj_discharge4_end_time_time` | R/W | Wire 4 the discharge end time (high byte for hours, low byte for minutes; hh : mm) |
| `3627H` | `text.saj_discharge5_start_time_time` | R/W | Wire 5 the discharge starting time (high byte for hours, low byte for minutes; hh : mm) |
| `3628H` | `text.saj_discharge5_end_time_time` | R/W | Wire 5 of the discharge end time (high byte for hours, and the low byte for minutes; hh : mm) |
| `362AH` | `text.saj_discharge6_start_time_time` | R/W | Wire 6 the initial discharge time (high byte for hours, low byte for minutes; hh : mm) |
| `362BH` | `text.saj_discharge6_end_time_time` | R/W | Wire 6 the end of the discharge time (high byte for hours, the low byte for minutes; hh : mm) |
| `362DH` | `text.saj_discharge7_start_time_time` | R/W | Wire 7 the discharge starting time (high byte for hours, low byte |
| `362EH` | `text.saj_discharge7_end_time_time` | R/W | Wire 7 the end of the discharge time (high byte for hours, low byte for minutes; hh : mm) |
## Switchable control entities (`switch.*`)

These switches do not set a fixed register value but write different values into the respective register depending on their state (see `switch.py`). They are read/write (`R/W`).

| Register | Entity | Mode | Description |
|---|---|---|---|
| `3604H` | `switch.saj_charging_control` | R/W | Turns the charge time-window bitmask register (`Chg_time_enable_control`) on/off. Also requires `AppMode` (`0x3647`) = 1 (time mode) to actually charge. |
| `3605H` | `switch.saj_discharging_control` | R/W | Turns the discharge time-window bitmask register (`Dchg_time_enable_control`) on/off. Also requires `AppMode` (`0x3647`) = 1 (time mode). |
| `3636H` | `switch.saj_passive_charge_control` | R/W | Sets `Passive_charge_enable` to `2` (charge), provided `AppMode` is in passive mode; turning it off writes `0` (standby). |
| `3636H` | `switch.saj_passive_discharge_control` | R/W | Sets `Passive_charge_enable` to `1` (discharge), provided `AppMode` is in passive mode; turning it off writes `0` (standby). |

> ⚠️ **Important note:** These `switch.*` entities also only write to the respective register and are not synchronized with the actual device state. The current state is instead derived from the cached read data (e.g. `charging_enabled`/`discharging_enabled`, `passive_charge_enable`, `AppMode`) – to monitor the actual value, use the corresponding `sensor.*` entities.