from typing import Optional

from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.const import (
    POWER_VOLT_AMPERE_REACTIVE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

from typing import Dict, NamedTuple, Any


DOMAIN = "saj_modbus"
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
    
@dataclass
class SajModbusSensorEntityDescription(SensorEntityDescription):
    """A class that describes SAJ H2 sensor entities."""


power_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfPower.WATT,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:solar-power",  
)

temperature_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:thermometer",  
)

energy_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    icon="mdi:solar-power",  
)

information_sensors_group = SensorGroup(
    icon="mdi:information-outline"  
)


gfci_sensors_group = SensorGroup(
    unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    device_class=SensorDeviceClass.CURRENT,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:current-dc"
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



def create_sensor_descriptions(group: SensorGroup, sensors: list) -> dict:
    descriptions = {}
    for sensor in sensors:
        
        icon = sensor.get("icon", group.icon)
        if icon and not icon.startswith("mdi:"):
            icon = f"mdi:{icon}"
        
        
        enable = sensor.get("enable", True)
        
        descriptions[sensor["key"]] = SajModbusSensorEntityDescription(
            name=sensor["name"],
            key=sensor["key"],
            native_unit_of_measurement=group.unit_of_measurement,
            icon=icon,
            device_class=group.device_class,
            state_class=group.state_class,
            entity_registry_enabled_default=enable,
        )
    return descriptions


power_sensors = [
    {"name": "Total Load Power", "key": "TotalLoadPower", "icon": "transmission-tower"},
    {"name": "Grid Load Power", "key": "gridPower", "icon": "power-socket"},
    {"name": "PV Power", "key": "pvPower", "icon": "solar-power"},
    {"name": "Battery Power", "key": "batteryPower", "icon": "battery-charging-100"},
    
]

battery_sensors = [
    {"name": "Battery Energy Percent", "key": "batEnergyPercent", "icon": "battery-charging-100", "enable": True}
]

gfci_sensors = [
    {"name": "GFCI", "key": "gfci", "icon": "current-dc", "enable": False}
]

temperature_sensors = [
    {"name": "Inverter Temperature", "key": "SinkTemp", "icon": "thermometer"},
    {"name": "Environment Temperature", "key": "AmbTemp", "icon": "thermometer-lines"},
    {"name": "Battery Temperature", "key": "BatTemp", "icon": "battery-thermometer"},
    
]



iso_resistance_sensors = [
    {"name": "PV1+ Isolation Resistance", "key": "iso1", "icon": "omega"},
    {"name": "PV2+ Isolation Resistance", "key": "iso2", "icon": "omega"},
    {"name": "PV3+ Isolation Resistance", "key": "iso3", "icon": "omega", "enable": False},  
    {"name": "PV4+ Isolation Resistance", "key": "iso4", "icon": "omega", "enable": False},  
 
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
]



energy_sensors = [
    {"name": "Power current day", "key": "todayenergy", "enable": False, "icon": "solar-power"},
    {"name": "Power current month", "key": "monthenergy", "enable": False, "icon": "solar-power"},
    {"name": "Power current year", "key": "yearenergy", "enable": False, "icon": "solar-power"},
    {"name": "Total power generation", "key": "totalenergy", "enable": False, "icon": "solar-power"},
    {"name": "Battery Today Charge", "key": "bat_today_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Month Charge", "key": "bat_month_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Year Charge", "key": "bat_year_charge", "enable": False, "icon": "battery-charging"},
    {"name": "Battery Total Charge", "key": "bat_total_charge", "enable": False, "icon": "battery-charging-100"},
    {"name": "Battery Today Discharge", "key": "bat_today_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Battery Month Discharge", "key": "bat_month_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Battery Year Discharge", "key": "bat_year_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Battery Total Discharge", "key": "bat_total_discharge", "enable": False, "icon": "battery-minus"},
    {"name": "Inverter Today Generation", "key": "inv_today_gen", "enable": False, "icon": "solar-power"},
    {"name": "Inverter Month Generation", "key": "inv_month_gen", "enable": False, "icon": "solar-power"},
    {"name": "Inverter Year Generation", "key": "inv_year_gen", "enable": False, "icon": "solar-power"},
    {"name": "Inverter Total Generation", "key": "inv_total_gen", "enable": False, "icon": "solar-power"},
    {"name": "Total Today Load", "key": "total_today_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Total Month Load", "key": "total_month_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Total Year Load", "key": "total_year_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Total Load", "key": "total_total_load", "enable": False, "icon": "home-import-outline"},
    {"name": "Sell Today Energy", "key": "sell_today_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Month Energy", "key": "sell_month_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy", "key": "sell_year_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Total Energy", "key": "sell_total_energy", "enable": False, "icon": "solar-power"},
    {"name": "Sell Today Energy 2", "key": "sell_today_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Month Energy 2", "key": "sell_month_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy 2", "key": "sell_year_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Total Energy 2", "key": "sell_total_energy_2", "enable": False, "icon": "solar-power"},
    {"name": "Sell Today Energy 3", "key": "sell_today_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Sell Month Energy 3", "key": "sell_month_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Sell Year Energy 3", "key": "sell_year_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Sell Total Energy 3", "key": "sell_total_energy_3", "enable": False, "icon": "solar-power"},
    {"name": "Feed-in Today Energy", "key": "feedin_today_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-in Month Energy", "key": "feedin_month_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-in Year Energy", "key": "feedin_year_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-in Total Energy", "key": "feedin_total_energy", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Today Energy 2", "key": "feedin_today_energy_2", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Month Energy 2", "key": "feedin_month_energy_2", "enable": False, "icon": "calendar-month"},
    {"name": "Feed-In Year Energy 2", "key": "feedin_year_energy_2", "enable": False, "icon": "calendar"},
    {"name": "Feed-In Total Energy 2", "key": "feedin_total_energy_2", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Today Energy 3", "key": "feedin_today_energy_3", "enable": False, "icon": "transmission-tower"},
    {"name": "Feed-In Month Energy 3", "key": "feedin_month_energy_3", "enable": False, "icon": "calendar-month"},
    {"name": "Feed-In Year Energy 3", "key": "feedin_year_energy_3", "enable": False, "icon": "calendar"},
    {"name": "Feed-In Total Energy 3", "key": "feedin_total_energy_3", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Today", "key": "sum_feed_in_today", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Month", "key": "sum_feed_in_month", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Year", "key": "sum_feed_in_year", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Feed-In Total", "key": "sum_feed_in_total", "enable": False, "icon": "transmission-tower"},
    {"name": "Sum All Phases Sell Today", "key": "sum_sell_today", "enable": False, "icon": "currency-usd"},
    {"name": "Sum All Phases Sell Month", "key": "sum_sell_month", "enable": False, "icon": "currency-usd"},
    {"name": "Sum All Phases Sell Year", "key": "sum_sell_year", "enable": False, "icon": "currency-usd"},
    {"name": "Sum All Phases Sell Total", "key": "sum_sell_total", "enable": False, "icon": "currency-usd"},
    {"name": "Backup Today Load", "key": "backup_today_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Backup Month Load", "key": "backup_month_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Backup Year Load", "key": "backup_year_load", "enable": False, "icon": "lightning-bolt"},
    {"name": "Backup Total Load", "key": "backup_total_load", "enable": False, "icon": "lightning-bolt"},
]
    


SENSOR_TYPES = {
    **create_sensor_descriptions(power_sensors_group, power_sensors),
    **create_sensor_descriptions(temperature_sensors_group, temperature_sensors),
    **create_sensor_descriptions(energy_sensors_group, energy_sensors),
    **create_sensor_descriptions(information_sensors_group, information_sensors),
    **create_sensor_descriptions(iso_resistance_sensors_group, iso_resistance_sensors),
    **create_sensor_descriptions(battery_sensors_group, battery_sensors), 
    **create_sensor_descriptions(gfci_sensors_group,gfci_sensors),
   
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
