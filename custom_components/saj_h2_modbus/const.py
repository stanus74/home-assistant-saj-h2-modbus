from typing import Optional, Literal
from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    UnitOfApparentPower,  # Replace the import for the deprecated constant
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

from typing import Dict, NamedTuple, Any


DOMAIN = "saj_h2_modbus"
DEFAULT_NAME = "SAJ"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_PORT = 502
CONF_SAJ_HUB = "saj_hub"
ATTR_MANUFACTURER = "SAJ Electric"


@dataclass
class SensorGroup:
    unit_of_measurement: Optional[str] = None
    icon: str = ""  # Optional
    device_class: Optional[str] = None
    state_class: Optional[str] = None
    force_update: bool = False  # New attribute for the group

@dataclass
class SajModbusSensorEntityDescription(SensorEntityDescription):
    """A class that describes SAJ H2 sensor entities."""
    reset_period: Optional[Literal["daily", "monthly", "yearly"]] = None
    native_precision: Optional[int] = None
    suggested_display_precision: Optional[int] = None


power_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfPower.WATT,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:solar-power",
    force_update=True  # enable force_update for the entire group

)

apparent_power_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
    device_class=SensorDeviceClass.APPARENT_POWER,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:flash-outline",
)

voltage_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfElectricPotential.VOLT,
    device_class=SensorDeviceClass.VOLTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:sine-wave",
)

current_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:current-dc",
)

# New group for sensors with milliampere as unit
milliampere_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:current-dc",
)

temperature_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:thermometer",
)

# Existing group for total increasing energy sensors
energy_sensors_total_increasing_group = SensorGroup(
    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    icon="mdi:chart-line", # Changed icon to better reflect total increasing
)

# New group for energy sensors that reset periodically
energy_sensors_periodic_reset_group = SensorGroup(
    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL, # Correct state_class for resetting counters
    icon="mdi:counter", # Icon indicating a counter
)

information_sensors_group = SensorGroup(
    icon="mdi:information-outline"
)

iso_resistance_sensors_group = SensorGroup(
    unit_of_measurement="kΩ",
    icon="mdi:omega"
)

battery_sensors_group = SensorGroup(
    unit_of_measurement='%',
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:battery"
)

frequency_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfFrequency.HERTZ,  # Unit in Hertz
    device_class=SensorDeviceClass.FREQUENCY,  # Classification as frequency
    state_class=SensorStateClass.MEASUREMENT,  # State is measured
    icon="mdi:sine-wave"  # Suitable icon for frequency
)

power_factor_sensors_group = SensorGroup(
    unit_of_measurement=None,  # Power Factor has no unit
    device_class=None,  # There is no specific device_class for Power Factor
    state_class=SensorStateClass.MEASUREMENT,  # Important for chart display
    icon="mdi:power-plug",
)

schedule_sensors_group = SensorGroup(
    unit_of_measurement=None,
    icon="mdi:clock-outline",
    device_class=None,
    state_class=None,
)

def create_sensor_descriptions(group: SensorGroup, sensors: list) -> dict:
    descriptions = {}
    for sensor in sensors:

        icon = sensor.get("icon", group.icon)
        if icon and not icon.startswith("mdi:"):
            icon = f"mdi:{icon}"


        enable = sensor.get("enable", True)
        native_unit = sensor.get("unit_of_measurement", group.unit_of_measurement)

        # Bestimme reset_period basierend auf dem Sensor-Namen und Key
        reset_period = None
        if group.state_class == SensorStateClass.TOTAL:
            key = sensor["key"]
            name = sensor["name"].lower()
            if "_today_" in key or key.startswith("today") or key.endswith("_today") or "current day" in name or "today " in name:
                reset_period = "daily"
            elif "_month_" in key or key.startswith("month") or key.endswith("_month") or "current month" in name:
                reset_period = "monthly"
            elif "_year_" in key or key.startswith("year") or key.endswith("_year") or "current year" in name:
                reset_period = "yearly"

        descriptions[sensor["key"]] = SajModbusSensorEntityDescription(
            name=sensor["name"],
            key=sensor["key"],
            native_unit_of_measurement=native_unit,
            icon=icon,
            device_class=group.device_class,
            state_class=group.state_class,
            entity_registry_enabled_default=enable,
            force_update=group.force_update,
            reset_period=reset_period,
            native_precision=sensor.get("native_precision", None),
            suggested_display_precision=sensor.get("suggested_display_precision", None)
        )
    return descriptions


power_sensors = [
    {"name": "Total Load Power", "key": "TotalLoadPower", "icon": "transmission-tower"},
    {"name": "Grid Load Power", "key": "gridPower", "icon": "power-socket"},
    {"name": "Total Grid Power", "key": "totalgridPower", "icon": "power-socket"},
    {"name": "PV Power", "key": "pvPower", "icon": "solar-power"},
    {"name": "Battery Power", "key": "batteryPower", "icon": "battery-charging-100"},
    {"name": "Inverter Power", "key": "inverterPower", "icon": "power-socket"},
    {"name": "PV1 Power", "key": "pv1Power", "icon": "flash"},
    {"name": "PV2 Power", "key": "pv2Power", "icon": "flash"},
    {"name": "PV3 Power", "key": "pv3Power", "icon": "flash", "enable": False},
    {"name": "PV4 Power", "key": "pv4Power", "icon": "flash", "enable": False},

    {"name": "CT Grid Power Watt", "key": "CT_GridPowerWatt", "icon": "flash", "enable": False},
    {"name": "CT PV Power Watt", "key": "CT_PVPowerWatt", "icon": "flash", "enable": False},
    {"name": "Backup Total Load Power Watt", "key": "BackupTotalLoadPowerWatt", "icon": "home-lightning-bolt", "enable": False},
    {"name": "R-Phase Grid Power Watt", "key": "RGridPowerWatt", "icon": "flash", "enable": False},
    {"name": "S-Phase Grid Power Watt", "key": "SGridPowerWatt", "icon": "flash", "enable": False},
    {"name": "T-Phase Grid Power Watt", "key": "TGridPowerWatt", "icon": "flash", "enable": False},
    {"name": "Meter A Real Power 1", "key": "Meter_A_PowerW", "icon": "flash", "enable": False},
    {"name": "Meter A Real Power 2", "key": "Meter_A_PowerW_2", "icon": "flash", "enable": False},
    {"name": "Meter A Real Power 3", "key": "Meter_A_PowerW_3", "icon": "flash", "enable": False},
    {"name": "R-Phase Inverter Power Watt", "key": "RInvPowerWatt", "icon": "flash", "enable": True},
    {"name": "S-Phase Inverter Power Watt", "key": "SInvPowerWatt", "icon": "flash", "enable": True},
    {"name": "T-Phase Inverter Power Watt", "key": "TInvPowerWatt", "icon": "flash", "enable": True},
    {"name": "R-Phase Off-Grid Power Watt", "key": "ROutPowerWatt", "icon": "flash", "enable": True},
    {"name": "S-Phase Off-Grid Power Watt", "key": "SOutPowerWatt", "icon": "flash", "enable": True},
    {"name": "T-Phase Off-Grid Power Watt", "key": "TOutPowerWatt", "icon": "flash", "enable": True},
    {"name": "R-Phase On-Grid Output Power Watt", "key": "ROnGridOutPowerWatt", "icon": "flash", "enable": True},
    {"name": "S-Phase On-Grid Output Power Watt", "key": "SOnGridOutPowerWatt", "icon": "flash", "enable": True},
    {"name": "T-Phase On-Grid Output Power Watt", "key": "TOnGridOutPowerWatt", "icon": "flash", "enable": True},
]

apparent_power_sensors = [
    {"name": "CT Grid Power VA", "key": "CT_GridPowerVA", "enable": False},
    {"name": "CT PV Power VA", "key": "CT_PVPowerVA", "enable": False},
    {"name": "Total Inverter Power VA", "key": "TotalInvPowerVA", "enable": False},
    {"name": "Backup Total Load Power VA", "key": "BackupTotalLoadPowerVA", "enable": False},
    {"name": "R-Phase Grid Power VA", "key": "RGridPowerVA", "enable": False},
    {"name": "S-Phase Grid Power VA", "key": "SGridPowerVA", "enable": False},
    {"name": "T-Phase Grid Power VA", "key": "TGridPowerVA", "enable": False},
    {"name": "Meter A Apparent Power 1", "key": "Meter_A_PowerV", "enable": False},
    {"name": "Meter A Apparent Power 2", "key": "Meter_A_PowerV_2", "enable": False},
    {"name": "Meter A Apparent Power 3", "key": "Meter_A_PowerV_3", "enable": False},
    {"name": "R-Phase Inverter Power VA", "key": "RInvPowerVA", "enable": True},
    {"name": "S-Phase Inverter Power VA", "key": "SInvPowerVA", "enable": True},
    {"name": "T-Phase Inverter Power VA", "key": "TInvPowerVA", "enable": True},
    {"name": "R-Phase Off-Grid Power VA", "key": "ROutPowerVA", "enable": True},
    {"name": "S-Phase Off-Grid Power VA", "key": "SOutPowerVA", "enable": True},
    {"name": "T-Phase Off-Grid Power VA", "key": "TOutPowerVA", "enable": True},
]

voltage_sensors = [
    {"name": "PV1 Voltage", "key": "pv1Voltage", "icon": "sine-wave"},
    {"name": "PV2 Voltage", "key": "pv2Voltage", "icon": "sine-wave"},
    {"name": "PV3 Voltage", "key": "pv3Voltage", "icon": "sine-wave", "enable": False},
    {"name": "PV4 Voltage", "key": "pv4Voltage", "icon": "sine-wave", "enable": False},

    {"name": "R-Phase Grid Voltage", "key": "RGridVolt", "icon": "sine-wave", "enable": False},
    {"name": "S-Phase Grid Voltage", "key": "SGridVolt", "icon": "sine-wave", "enable": False},
    {"name": "T-Phase Grid Voltage", "key": "TGridVolt", "icon": "sine-wave", "enable": False},

    {"name": "Battery 1 Voltage", "key": "Bat1Voltage", "icon": "flash", "enable": True},
    {"name": "Battery 2 Voltage", "key": "Bat2Voltage", "icon": "flash", "enable": False},
    {"name": "Battery 3 Voltage", "key": "Bat3Voltage", "icon": "flash", "enable": False},
    {"name": "Battery 4 Voltage", "key": "Bat4Voltage", "icon": "flash", "enable": False},
    {"name": "Battery Voltage High Protection", "key": "BatProtHigh", "icon": "alert", "enable": False},
    {"name": "Battery Voltage Low Warning", "key": "BatProtLow", "icon": "alert", "enable": False},
    {"name": "Battery Charge Voltage", "key": "Bat_Chargevoltage", "icon": "battery-charging", "enable": False},
    {"name": "Battery Discharge Cut-off Voltage", "key": "Bat_DisCutOffVolt", "icon": "battery", "enable": False},
    {"name": "Meter A Voltage 1", "key": "Meter_A_Volt1", "icon": "sine-wave", "enable": False},
    {"name": "Meter A Voltage 2", "key": "Meter_A_Volt2", "icon": "sine-wave", "enable": False},
    {"name": "Meter A Voltage 3", "key": "Meter_A_Volt3", "icon": "sine-wave", "enable": False},
    {"name": "R-Phase Inverter Voltage", "key": "RInvVolt", "icon": "sine-wave", "enable": True},
    {"name": "S-Phase Inverter Voltage", "key": "SInvVolt", "icon": "sine-wave", "enable": True},
    {"name": "T-Phase Inverter Voltage", "key": "TInvVolt", "icon": "sine-wave", "enable": True},
    {"name": "R-Phase Off-Grid Voltage", "key": "ROutVolt", "icon": "sine-wave", "enable": True},
    {"name": "S-Phase Off-Grid Voltage", "key": "SOutVolt", "icon": "sine-wave", "enable": True},
    {"name": "T-Phase Off-Grid Voltage", "key": "TOutVolt", "icon": "sine-wave", "enable": True},
    {"name": "R-Phase On-Grid Output Voltage", "key": "ROnGridOutVolt", "icon": "sine-wave", "enable": True},
    {"name": "S-Phase On-Grid Output Voltage", "key": "SOnGridOutVolt", "icon": "sine-wave", "enable": True},
    {"name": "T-Phase On-Grid Output Voltage", "key": "TOnGridOutVolt", "icon": "sine-wave", "enable": True},
]

frequency_sensors = [
    {"name": "R-Phase Grid Frequency", "key": "RGridFreq", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "S-Phase Grid Frequency", "key": "SGridFreq", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "T-Phase Grid Frequency", "key": "TGridFreq", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "Meter A Frequency 1", "key": "Meter_A_Freq1", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "Meter A Frequency 2", "key": "Meter_A_Freq2", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "Meter A Frequency 3", "key": "Meter_A_Freq3", "icon": "sine-wave", "enable": False, "suggested_display_precision": 2},
    {"name": "R-Phase Inverter Frequency", "key": "RInvFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "S-Phase Inverter Frequency", "key": "SInvFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "T-Phase Inverter Frequency", "key": "TInvFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "R-Phase Off-Grid Frequency", "key": "ROutFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "S-Phase Off-Grid Frequency", "key": "SOutFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "T-Phase Off-Grid Frequency", "key": "TOutFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
    {"name": "R-Phase On-Grid Output Frequency", "key": "ROnGridOutFreq", "icon": "sine-wave", "enable": True, "suggested_display_precision": 2},
]

current_sensors = [
    {"name": "PV1 Total Current", "key": "pv1TotalCurrent", "icon": "current-dc"},
    {"name": "PV2 Total Current", "key": "pv2TotalCurrent", "icon": "current-dc"},
    {"name": "PV3 Total Current", "key": "pv3TotalCurrent", "icon": "current-dc", "enable": False},
    {"name": "PV4 Total Current", "key": "pv4TotalCurrent", "icon": "current-dc", "enable": False},

    {"name": "R-Phase Grid Current", "key": "RGridCurr", "icon": "current-dc", "enable": False},
    {"name": "S-Phase Grid Current", "key": "SGridCurr", "icon": "current-dc", "enable": False},
    {"name": "T-Phase Grid Current", "key": "TGridCurr", "icon": "current-dc", "enable": False},

    {"name": "Battery 1 Current", "key": "Bat1Current", "icon": "current-dc", "enable": True},
    {"name": "Battery 2 Current", "key": "Bat2Current", "icon": "current-dc", "enable": False},
    {"name": "Battery 3 Current", "key": "Bat3Current", "icon": "current-dc", "enable": False},
    {"name": "Battery 4 Current", "key": "Bat4Current", "icon": "current-dc", "enable": False},
    {"name": "Battery Discharge Current Limit", "key": "BatDisCurrLimit", "icon": "battery", "enable": True},
    {"name": "Battery Charge Current Limit", "key": "BatChaCurrLimit", "icon": "battery-charging", "enable": True},
    {"name": "Meter A Current 1", "key": "Meter_A_Curr1", "icon": "current-dc", "enable": False},
    {"name": "Meter A Current 2", "key": "Meter_A_Curr2", "icon": "current-dc", "enable": False},
    {"name": "Meter A Current 3", "key": "Meter_A_Curr3", "icon": "current-dc", "enable": False},
    {"name": "R-Phase Inverter Current", "key": "RInvCurr", "icon": "current-dc", "enable": True},
    {"name": "S-Phase Inverter Current", "key": "SInvCurr", "icon": "current-dc", "enable": True},
    {"name": "T-Phase Inverter Current", "key": "TInvCurr", "icon": "current-dc", "enable": True},
    {"name": "R-Phase Off-Grid Current", "key": "ROutCurr", "icon": "current-dc", "enable": True},
    {"name": "S-Phase Off-Grid Current", "key": "SOutCurr", "icon": "current-dc", "enable": True},
    {"name": "T-Phase Off-Grid Current", "key": "TOutCurr", "icon": "current-dc", "enable": True},
    {"name": "R-Phase On-Grid Output Current", "key": "ROnGridOutCurr", "icon": "current-dc", "enable": True},
]

milliampere_sensors = [
    {"name": "R-Phase Grid DC Component", "key": "RGridDCI", "icon": "current-dc", "enable": False},
    {"name": "S-Phase Grid DC Component", "key": "SGridDCI", "icon": "current-dc", "enable": False},
    {"name": "T-Phase Grid DC Component", "key": "TGridDCI", "icon": "current-dc", "enable": False},
    {"name": "GFCI", "key": "gfci", "icon": "current-dc", "enable": False},
    {"name": "R-Phase Off-Grid DVI", "key": "ROutDVI", "icon": "current-dc", "enable": True},
    {"name": "S-Phase Off-Grid DVI", "key": "SOutDVI", "icon": "current-dc", "enable": True},
    {"name": "T-Phase Off-Grid DVI", "key": "TOutDVI", "icon": "current-dc", "enable": True},
]

battery_sensors = [
    {"name": "Battery Energy Percent", "key": "batEnergyPercent", "icon": "battery-charging-100", "enable": True},
    {"name": "Battery 1 SOC", "key": "Bat1SOC", "icon": "battery", "enable": True},
    {"name": "Battery 1 SOH", "key": "Bat1SOH", "icon": "battery", "enable": True},
    {"name": "Battery 2 SOC", "key": "Bat2SOC", "icon": "battery", "enable": False},
    {"name": "Battery 2 SOH", "key": "Bat2SOH", "icon": "battery", "enable": False},
    {"name": "Battery 3 SOC", "key": "Bat3SOC", "icon": "battery", "enable": False},
    {"name": "Battery 3 SOH", "key": "Bat3SOH", "icon": "battery", "enable": False},
    {"name": "Battery 4 SOC", "key": "Bat4SOC", "icon": "battery", "enable": False},
    {"name": "Battery 4 SOH", "key": "Bat4SOH", "icon": "battery", "enable": False},
    {"name": "Battary on grid discharge depth", "key": "BatOnGridDisDepth", "enable": True},
    {"name": "Battery offgrid discharge depth", "key": "BatOffGridDisDepth", "enable": True},
    {"name": "Battery charge depth", "key": "BatcharDepth", "enable": True},
    {"name": "Battery Charge Power Limit", "key": "BatChargePower", "icon": "battery-charging", "enable": True},
    {"name": "Battery Discharge Power Limit", "key": "BatDischargePower", "icon": "battery", "enable": True},
    {"name": "Grid Charge Power Limit", "key": "GridChargePower", "icon": "transmission-tower", "enable": True},
    {"name": "Grid Discharge Power Limit", "key": "GridDischargePower", "icon": "transmission-tower", "enable": True},
]

temperature_sensors = [
    {"name": "Inverter Temperature", "key": "SinkTemp", "icon": "thermometer"},
    {"name": "Environment Temperature", "key": "AmbTemp", "icon": "thermometer-lines"},
    {"name": "Battery Temperature", "key": "BatTemp", "icon": "battery-thermometer"},

    {"name": "Battery 1 Temperature", "key": "Bat1Temperature", "icon": "thermometer", "enable": True},
    {"name": "Battery 2 Temperature", "key": "Bat2Temperature", "icon": "thermometer", "enable": False},
    {"name": "Battery 3 Temperature", "key": "Bat3Temperature", "icon": "thermometer", "enable": False},
    {"name": "Battery 4 Temperature", "key": "Bat4Temperature", "icon": "thermometer", "enable": False},
]

iso_resistance_sensors = [
    {"name": "PV1+ Isolation Resistance", "key": "iso1", "icon": "omega"},
    {"name": "PV2+ Isolation Resistance", "key": "iso2", "icon": "omega"},
    {"name": "PV3+ Isolation Resistance", "key": "iso3", "icon": "omega", "enable": False},
    {"name": "PV4+ Isolation Resistance", "key": "iso4", "icon": "omega", "enable": False},
]

power_factor_sensors = [
    {"name": "R-Phase Grid Power Factor", "key": "RGridPowerPF", "icon": "power-plug", "enable": True},
    {"name": "S-Phase Grid Power Factor", "key": "SGridPowerPF", "icon": "power-plug", "enable": True},
    {"name": "T-Phase Grid Power Factor", "key": "TGridPowerPF", "icon": "power-plug", "enable": True},
    {"name": "Meter A Power Factor 1", "key": "Meter_A_PowerFa", "icon": "power-plug", "enable": False},
    {"name": "Meter A Power Factor 2", "key": "Meter_A_PowerFa_2", "icon": "power-plug", "enable": False},
    {"name": "Meter A Power Factor 3", "key": "Meter_A_PowerFa_3", "icon": "power-plug", "enable": False},
]

information_sensors = [
    {"name": "Device Type", "key": "devtype", "icon": "information-outline", "enable": False},
    {"name": "Sub Type", "key": "subtype", "icon": "information-outline", "enable": False},
    {"name": "Comms Protocol Version", "key": "commver", "icon": "information-outline", "enable": False},
    {"name": "Serial Number", "key": "sn", "icon": "information-outline", "enable": False},
    {"name": "Product Code", "key": "pc", "icon": "information-outline", "enable": False},
    {"name": "Display Software Version", "key": "dv", "icon": "information-outline", "enable": False},
    {"name": "Master Ctrl Software Version", "key": "mcv", "icon": "information-outline", "enable": False},
    {"name": "Slave Ctrl Software Version", "key": "scv", "icon": "information-outline", "enable": False},
    {"name": "Display Board Hardware Version", "key": "disphwversion", "icon": "information-outline", "enable": False},
    {"name": "Control Board Hardware Version", "key": "ctrlhwversion", "icon": "information-outline", "enable": False},
    {"name": "Power Board Hardware Version", "key": "powerhwversion", "icon": "information-outline", "enable": False},
    {"name": "Inverter Status", "key": "mpvstatus", "icon": "information-outline"},
    {"name": "Inverter Working Mode", "key": "mpvmode", "icon": "information-outline"},
    {"name": "Inverter Error Message", "key": "faultmsg", "icon": "message-alert-outline", "enable": True},
    {"name": "Direction PV", "key": "directionPV", "icon": "arrow-all"},
    {"name": "Direction Battery", "key": "directionBattery", "icon": "arrow-all"},
    {"name": "Direction Grid", "key": "directionGrid", "icon": "arrow-all"},
    {"name": "Direction Ouput", "key": "directionOutput", "icon": "arrow-all"},

    {"name": "Battery Number", "key": "BatNum", "icon": "numeric", "enable": True},
    {"name": "Battery Capacity", "key": "BatCapcity", "icon": "battery", "enable": True},
    {"name": "Battery User Capacity", "key": "BatUserCap", "icon": "battery", "enable": True},
    {"name": "Battery Online", "key": "BatOnline", "icon": "cloud", "enable": True},
    {"name": "Battery 1 Cycle Count", "key": "Bat1CycleNum", "icon": "counter", "enable": True},
    {"name": "Battery 2 Cycle Count", "key": "Bat2CycleNum", "icon": "counter", "enable": False},
    {"name": "Battery 3 Cycle Count", "key": "Bat3CycleNum", "icon": "counter", "enable": False},
    {"name": "Battery 4 Cycle Count", "key": "Bat4CycleNum", "icon": "counter", "enable": False},

    {"name": "Battery 1 Fault", "key": "Bat1FaultMSG", "icon": "alert", "enable": True},
    {"name": "Battery 1 Warning", "key": "Bat1WarnMSG", "icon": "alert", "enable": True},
    {"name": "Battery 2 Fault", "key": "Bat2FaultMSG", "icon": "alert", "enable": False},
    {"name": "Battery 2 Warning", "key": "Bat2WarnMSG", "icon": "alert", "enable": False},
    {"name": "Battery 3 Fault", "key": "Bat3FaultMSG", "icon": "alert", "enable": False},
    {"name": "Battery 3 Warning", "key": "Bat3WarnMSG", "icon": "alert", "enable": False},
    {"name": "Battery 4 Fault", "key": "Bat4FaultMSG", "icon": "alert", "enable": False},
    {"name": "Battery 4 Warning", "key": "Bat4WarnMSG", "icon": "alert", "enable": False},
    {"name": "App Mode", "key": "AppMode", "icon": "information-outline", "enable": True},
]

# Sensors that are always increasing (lifetime totals)
total_increasing_energy_sensors = [
    {"name": "Total power generation", "key": "totalenergy", "enable": False, "icon": "solar-power"},
    {"name": "Battery Total Charge", "key": "bat_total_charge", "enable": False, "icon": "battery-charging-100"},
    {"name": "Battery Total Discharge", "key": "bat_total_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Inverter Total Generation", "key": "inv_total_gen", "enable": False, "icon": "solar-power"},
    {"name": "Total Load", "key": "total_total_load", "enable": True, "icon": "home-import-outline"},
    {"name": "Sell Total Energy", "key": "sell_total_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Total Energy 2", "key": "sell_total_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Total Energy 3", "key": "sell_total_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Feed-in Total Energy", "key": "feedin_total_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Total Energy 2", "key": "feedin_total_energy_2", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Total Energy 3", "key": "feedin_total_energy_3", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Total", "key": "sum_feed_in_total", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Sell Total", "key": "sum_sell_total", "enable": False, "icon": "currency-usd"},
    {"name": "Backup Total Load", "key": "backup_total_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Battery Pack 1 Discharge", "key": "Bat1DischarCap", "icon": "battery", "enable": True},
    {"name": "Battery Pack 2 Discharge", "key": "Bat2DischarCap", "icon": "battery", "enable": False},
    {"name": "Battery Pack 3 Discharge", "key": "Bat3DischarCap", "icon": "battery", "enable": False},
    {"name": "Battery Pack 4 Discharge", "key": "Bat4DischarCap", "icon": "battery", "enable": False},
    {"name": "Total PV Energy 2", "key": "total_pv_energy2", "enable": False, "icon": "solar-power"},
    {"name": "Total PV Energy 3", "key": "total_pv_energy3", "enable": False, "icon": "solar-power"},
]

# Sensors that reset periodically (daily, monthly, yearly)
periodic_reset_energy_sensors = [
    {"name": "Power current day", "key": "todayenergy", "enable": True, "icon": "solar-power"},
    {"name": "Power current month", "key": "monthenergy", "enable": False, "icon": "solar-power"},
    {"name": "Power current year", "key": "yearenergy", "enable": False, "icon": "solar-power"},
    {"name": "Battery Today Charge", "key": "bat_today_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Month Charge", "key": "bat_month_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Year Charge", "key": "bat_year_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Today Discharge", "key": "bat_today_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Battery Month Discharge", "key": "bat_month_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Battery Year Discharge", "key": "bat_year_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Inverter Today Generation", "key": "inv_today_gen", "enable": False, "icon": "solar-power"},
    {"name": "Inverter Month Generation", "key": "inv_month_gen", "enable": False, "icon": "solar-power"},
    {"name": "Inverter Year Generation", "key": "inv_year_gen", "enable": False, "icon": "solar-power"},
    {"name": "Total Today Load", "key": "total_today_load", "enable": True, "icon": "home-import-outline"},
    {"name": "Total Month Load", "key": "total_month_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Total Year Load", "key": "total_year_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Sell Today Energy", "key": "sell_today_energy", "enable": True, "icon": "solar-power"}, # Enabled this as per user's log
    {"name": "Sell Month Energy", "key": "sell_month_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy", "key": "sell_year_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Today Energy 2", "key": "sell_today_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Month Energy 2", "key": "sell_month_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy 2", "key": "sell_year_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Today Energy 3", "key": "sell_today_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Sell Month Energy 3", "key": "sell_month_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy 3", "key": "sell_year_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Feed-in Today Energy", "key": "feedin_today_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-in Month Energy", "key": "feedin_month_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-in Year Energy", "key": "feedin_year_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Today Energy 2", "key": "feedin_today_energy_2", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Month Energy 2", "key": "feedin_month_energy_2", "enable": False, "icon": "calendar-month"},
    {"name": "Feed-In Year Energy 2", "key": "feedin_year_energy_2", "enable": False, "icon": "calendar"},
    {"name": "Feed-In Today Energy 3", "key": "feedin_today_energy_3", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Month Energy 3", "key": "feedin_month_energy_3", "enable": False, "icon": "calendar-month"},
    {"name": "Feed-In Year Energy 3", "key": "feedin_year_energy_3", "enable": False, "icon": "calendar"},
    {"name": "Sum All Phases Feed-In Today", "key": "sum_feed_in_today", "enable": True, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Month", "key": "sum_feed_in_month", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Year", "key": "sum_feed_in_year", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Sell Today", "key": "sum_sell_today", "enable": True, "icon": "currency-usd"},
    {"name": "Sum All Phases Sell Month", "key": "sum_sell_month", "enable": False, "icon": "currency-usd"},
    {"name": "Sum All Phases Sell Year", "key": "sum_sell_year", "enable": False, "icon": "currency-usd"},
    {"name": "Backup Today Load", "key": "backup_today_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Backup Month Load", "key": "backup_month_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Backup Year Load", "key": "backup_year_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Today PV Energy 2", "key": "today_pv_energy2", "enable": False, "icon": "solar-power"},
    {"name": "Month PV Energy 2", "key": "month_pv_energy2", "enable": False, "icon": "solar-power"},
    {"name": "Year PV Energy 2", "key": "year_pv_energy2", "enable": False, "icon": "solar-power"},
    {"name": "Today PV Energy 3", "key": "today_pv_energy3", "enable": False, "icon": "solar-power"},
    {"name": "Month PV Energy 3", "key": "month_pv_energy3", "enable": False, "icon": "solar-power"},
    {"name": "Year PV Energy 3", "key": "year_pv_energy3", "enable": False, "icon": "solar-power"},
]

battery_schedule_sensors = [
    {"name": "Charge Start Time", "key": "charge_start_time", "icon": "clock-outline"},
    {"name": "Charge End Time", "key": "charge_end_time", "icon": "clock-outline"},
    {"name": "Charge Day Mask", "key": "charge_day_mask", "icon": "calendar"},
    {"name": "Charge Power Percent", "key": "charge_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge Start Time", "key": "discharge_start_time", "icon": "clock-outline"},
    {"name": "Discharge End Time", "key": "discharge_end_time", "icon": "clock-outline"},
    {"name": "Discharge Day Mask", "key": "discharge_day_mask", "icon": "calendar"},
    {"name": "Discharge Power Percent", "key": "discharge_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 2 Start Time", "key": "discharge2_start_time", "icon": "clock-outline"},
    {"name": "Discharge 2 End Time", "key": "discharge2_end_time", "icon": "clock-outline"},
    {"name": "Discharge 2 Day Mask", "key": "discharge2_day_mask", "icon": "calendar"},
    {"name": "Discharge 2 Power Percent", "key": "discharge2_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 3 Start Time", "key": "discharge3_start_time", "icon": "clock-outline"},
    {"name": "Discharge 3 End Time", "key": "discharge3_end_time", "icon": "clock-outline"},
    {"name": "Discharge 3 Day Mask", "key": "discharge3_day_mask", "icon": "calendar"},
    {"name": "Discharge 3 Power Percent", "key": "discharge3_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 4 Start Time", "key": "discharge4_start_time", "icon": "clock-outline"},
    {"name": "Discharge 4 End Time", "key": "discharge4_end_time", "icon": "clock-outline"},
    {"name": "Discharge 4 Day Mask", "key": "discharge4_day_mask", "icon": "calendar"},
    {"name": "Discharge 4 Power Percent", "key": "discharge4_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 5 Start Time", "key": "discharge5_start_time", "icon": "clock-outline"},
    {"name": "Discharge 5 End Time", "key": "discharge5_end_time", "icon": "clock-outline"},
    {"name": "Discharge 5 Day Mask", "key": "discharge5_day_mask", "icon": "calendar"},
    {"name": "Discharge 5 Power Percent", "key": "discharge5_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 6 Start Time", "key": "discharge6_start_time", "icon": "clock-outline"},
    {"name": "Discharge 6 End Time", "key": "discharge6_end_time", "icon": "clock-outline"},
    {"name": "Discharge 6 Day Mask", "key": "discharge6_day_mask", "icon": "calendar"},
    {"name": "Discharge 6 Power Percent", "key": "discharge6_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Discharge 7 Start Time", "key": "discharge7_start_time", "icon": "clock-outline"},
    {"name": "Discharge 7 End Time", "key": "discharge7_end_time", "icon": "clock-outline"},
    {"name": "Discharge 7 Day Mask", "key": "discharge7_day_mask", "icon": "calendar"},
    {"name": "Discharge 7 Power Percent", "key": "discharge7_power_percent", "icon": "flash", "unit_of_measurement": "%"},
    {"name": "Passive Charge Enable", "key": "Passive_charge_enable", "icon": "power-settings"},
    {"name": "Passive Grid Charge Power", "key": "Passive_GridChargePower", "icon": "transmission-tower", "unit_of_measurement": "%"},
    {"name": "Passive Grid Discharge Power", "key": "Passive_GridDisChargePower", "icon": "transmission-tower", "unit_of_measurement": "%"},
    {"name": "Passive Battery Charge Power", "key": "Passive_BatChargePower", "icon": "battery-charging", "unit_of_measurement": "%"},
    {"name": "Passive Battery Discharge Power", "key": "Passive_BatDisChargePower", "icon": "battery", "unit_of_measurement": "%"},
]

anti_reflux_sensors = [
    {"name": "Anti-Reflux Power Limit", "key": "AntiRefluxPowerLimit", "icon": "flash-outline"},
    {"name": "Anti-Reflux Current Limit", "key": "AntiRefluxCurrentLimit", "icon": "current-dc"},
    {"name": "Anti-Reflux Current Mode", "key": "AntiRefluxCurrentmode", "icon": "cog-outline"},
]

SENSOR_TYPES = {
    **create_sensor_descriptions(power_sensors_group, power_sensors),
    **create_sensor_descriptions(apparent_power_sensors_group, apparent_power_sensors),
    **create_sensor_descriptions(voltage_sensors_group, voltage_sensors),
    **create_sensor_descriptions(current_sensors_group, current_sensors),
    **create_sensor_descriptions(milliampere_sensors_group, milliampere_sensors),
    **create_sensor_descriptions(temperature_sensors_group, temperature_sensors),
    **create_sensor_descriptions(energy_sensors_total_increasing_group, total_increasing_energy_sensors),
    **create_sensor_descriptions(energy_sensors_periodic_reset_group, periodic_reset_energy_sensors),
    **create_sensor_descriptions(information_sensors_group, information_sensors),
    **create_sensor_descriptions(iso_resistance_sensors_group, iso_resistance_sensors),
    **create_sensor_descriptions(battery_sensors_group, battery_sensors),
    **create_sensor_descriptions(frequency_sensors_group,frequency_sensors),
    **create_sensor_descriptions(schedule_sensors_group, battery_schedule_sensors),
    **create_sensor_descriptions(information_sensors_group, anti_reflux_sensors),
    **create_sensor_descriptions(power_factor_sensors_group, power_factor_sensors),
}

DEVICE_STATUSSES = {
    0: "Initialization",
    1: "Waiting",
    2: "Running",
    3: "Offnet mode, used for energy storage",
    4: "Grid on-load mode, used for energy storage",
    5: "Fault",
    6: "Update",
    7: "Test",
    8: "Self-checking",
    9: "Reset",
}

FAULT_MESSAGES = {
    0: {
		0x00000001: "Lost Com. H ↔ M Err",
		0x00000002: "Meter lost Meter",
		0x00000004: "HIMI Eeprom error",
		0x00000008: "HMI RTC Err",
		0x00000010: "BMS Device Error",
		0x00000020: "BMS lost communication warning",
		0x00000040: "Reserved (bit 71)",
		0x00000080: "Reserved (bit 72)",
		0x00000100: "Reserved (bit 73)",
		0x00000200: "Reserved (bit 74)",
		0x00000400: "Reserved (bit 75)",
		0x00000800: "R Phase voltage high fault",
		0x00001000: "R Phase voltage low fault",
		0x00002000: "S Phase voltage high fault",
		0x00004000: "S Phase voltage low fault",
		0x00008000: "T Phase voltage high fault",
		0x00010000: "T Phase voltage low fault",
		0x00020000: "Frequency High Fault",
		0x00040000: "Frequency Low Fault ",
		0x00080000: "Reserved (bit 84)",
		0x00100000: "Reserved (bit 85)",
		0x00200000: "Reserved (bit 86)",
		0x00400000: "Reserved (bit 87)",
		0x00800000: "No Grid Fault",
		0x01000000: "PV Input Mode Fault",
		0x02000000: "Hardware HW PV Curr High Fault",
		0x04000000: "PV Voltage",
		0x08000000: "Hardware HW Bus Volt High Fault",
		0x10000000: "Reserved (bit 93)",
		0x20000000: "Reserved (bit 94)",
		0x40000000: "Reserved (bit 95)",
		0x80000000: "Reserved (bit 96)",
},

    1: {
		0x00000001: "Master Bus Voltage High",
		0x00000002: "Master Bus Voltage Low",
		0x00000004: "Master Grid Phase Error",
		0x00000008: "Master PV Voltage High Error",
		0x00000010: "Master Islanding Error",
		0x00000020: "Reserved (bit 6)",
		0x00000040: "Master PV Input Error",
		0x00000080: "Communication between DSP and PC lost",
		0x00000100: "Master HW Bus Voltage High",
		0x00000200: "Master HW PV Current High",
		0x00000400: "Reserved (bit 11)",
		0x00000800: "Master HW Inv Current High",
		0x00001000: "Reserved (bit 13)",
		0x00002000: "Reserved (bit 14)",
		0x00004000: "Master Grid NE Voltage Error",
		0x00008000: "Master DRM0 Error",
		0x00010000: "Master Fan 1 Error",
		0x00020000: "Master Fan 2 Error",
		0x00040000: "Master Fan 3 Error",
		0x00080000: "Master Fan 4 Error",
		0x00100000: "Master Arc Error",
		0x00200000: "Master SW PV Current High",
		0x00400000: "Master Battery Voltage High",
		0x00800000: "Master Battery Current High",
		0x01000000: "Master Battery Charge Voltage High",
		0x02000000: "Master Battery Overload",
		0x04000000: "Master Battery Soft Connect Timeout",
		0x08000000: "Master Output Overload",
		0x10000000: "Master Battery Open Circuit Error",
		0x20000000: "Master Battery Discharge Voltage Low",
		0x40000000: "Authority expires",
		0x80000000: "Lost Communication D <-> C",
    },

    2: {
		0x80000000: "Bus Voltage Balance Error",
		0x40000000: "ISO Error",
		0x20000000: "Phase 3 DCI Error",
		0x10000000: "Phase 2 DCI Error",
		0x08000000: "Phase 1 DCI Error",
		0x04000000: "GFCI Error",
		0x02000000: "Reserved (bit 58)",
		0x01000000: "Reserved (bit 57)",
		0x00800000: "No Grid Error",
		0x00400000: "Phase 3 DCV Current Error",
		0x00200000: "Phase 2 DCV Current Error",
		0x00100000: "Phase 1 DCV Current Error",
		0x00080000: "Reserved (bit 52)",
		0x00040000: "Grid Frequency Low",
		0x00020000: "Grid Frequency High",
		0x00010000: "Reserved (bit 49)",
		0x00008000: "OffGrid Voltage Low",
		0x00004000: "Voltage of Master host power network is 10 Min High under voltage",
		0x00002000: "Phase 3 Voltage Low",
		0x00001000: "Phase 3 Voltage High",
		0x00000800: "Phase 2 Voltage Low",
		0x00000400: "Phase 2 Voltage High",
		0x00000200: "Phase 1 Voltage Low",
		0x00000100: "Phase 1 Voltage High",
		0x00000080: "Current Sensor Error",
		0x00000040: "DCI Device Error",
		0x00000020: "GFCI Device Error",
		0x00000010: "Communication Error M <-> S",
		0x00000008: "Temperature Low Error",
		0x00000004: "Temperature High Error",
		0x00000002: "EEPROM Error",
		0x00000001: "Relay Error",
    },
}
