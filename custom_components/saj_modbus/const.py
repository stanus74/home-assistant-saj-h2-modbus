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


DOMAIN = "saj_modbus"
DEFAULT_NAME = "SAJ"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_PORT = 502
CONF_SAJ_HUB = "saj_hub"
ATTR_MANUFACTURER = "SAJ Electric"


@dataclass
class SajModbusSensorEntityDescription(SensorEntityDescription):
    """A class that describes SAJ H2 sensor entities."""


SENSOR_TYPES: dict[str, list[SajModbusSensorEntityDescription]] = {
    "DevType": SajModbusSensorEntityDescription(
        name="Device Type",
        key="devtype",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "TotalLoadPower": SajModbusSensorEntityDescription(
        key="TotalLoadPower",
        name="TotalLoadPower",
        icon="",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    
    "gridPower": SajModbusSensorEntityDescription(
        key="gridPower",
        name="gridPower",
        icon="mdi:solar-panel-large",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    
    "pvPower": SajModbusSensorEntityDescription(  
        key="pvPower",
        name="PV Power",
        icon="mdi:solar-panel-large",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    
        
    "BatteryPower": SajModbusSensorEntityDescription( 
        key="batteryPower",
        name="batteryPower",
        icon="mdi:solar-panel-large",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,        
    ),
    
    "BatEnergyPercent": SajModbusSensorEntityDescription(
        key="batEnergyPercent",
        name="Battery Energy Percent",
        icon="mdi:battery-charging-100",
        native_unit_of_measurement='%',  # Verwenden Sie einfach einen String für Prozentsätze
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),

    "SinkTemp": SajModbusSensorEntityDescription(
        key="SinkTemp",
        name="Inverter temperature",
        icon="",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    
    "AmbTemp": SajModbusSensorEntityDescription(
        key="AmbTemp",
        name="Environment temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    
    "BatTemp": SajModbusSensorEntityDescription(
        key="BatTemp",
        name="Battery temperature",
        icon="mdi:battery-thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
        
    "SubType": SajModbusSensorEntityDescription(
        name="Sub Type",
        key="subtype",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "CommVer": SajModbusSensorEntityDescription(
        name="Comms Protocol Version",
        key="commver",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "SN": SajModbusSensorEntityDescription(
        name="Serial Number",
        key="sn",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "PC": SajModbusSensorEntityDescription(
        name="Product Code",
        key="pc",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "DV": SajModbusSensorEntityDescription(
        name="Display Software Version",
        key="dv",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "MCV": SajModbusSensorEntityDescription(
        name="Master Ctrl Software Version",
        key="mcv",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "SCV": SajModbusSensorEntityDescription(
        name="Slave Ctrl Software Version",
        key="scv",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "DispHWVersion": SajModbusSensorEntityDescription(
        name="Display Board Hardware Version",
        key="disphwversion",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "CtrlHWVersion": SajModbusSensorEntityDescription(
        name="Control Board Hardware Version",
        key="ctrlhwversion",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "PowerHWVersion": SajModbusSensorEntityDescription(
        name="Power Board Hardware Version",
        key="powerhwversion",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),

    "MPVStatus": SajModbusSensorEntityDescription(
        name="Inverter status",
        key="mpvstatus",
        icon="mdi:information-outline",
    ),

    "MPVMode": SajModbusSensorEntityDescription(
        name="Inverter working mode",
        key="mpvmode",
        icon="mdi:information-outline",
    ),

    "FaultMSG": SajModbusSensorEntityDescription(
        name="Inverter error message",
        key="faultmsg",
        icon="mdi:message-alert-outline",
    ),
  
       
    "GFCI": SajModbusSensorEntityDescription(
        name="GFCI",
        key="gfci",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        icon="mdi:current-dc",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
  
    "ErrorCount": SajModbusSensorEntityDescription(
        name="Error count",
        key="errorcount",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
        
    "ISO1": SajModbusSensorEntityDescription(
        name="PV1+_ISO",
        key="iso1",
        native_unit_of_measurement="kΩ",
        icon="mdi:omega",
        #entity_registry_enabled_default=False,
    ),

    "ISO2": SajModbusSensorEntityDescription(
        name="PV2+_ISO",
        key="iso2",
        native_unit_of_measurement="kΩ",
        icon="mdi:omega",
        #entity_registry_enabled_default=False,
    ),

    "ISO3": SajModbusSensorEntityDescription(
        name="PV3+_ISO",
        key="iso3",
        native_unit_of_measurement="kΩ",
        icon="mdi:omega",
        entity_registry_enabled_default=False,
    ),

    "ISO4": SajModbusSensorEntityDescription(
        name="PV__ISO",
        key="iso4",
        native_unit_of_measurement="kΩ",
        icon="mdi:omega",
        entity_registry_enabled_default=False,
    ),
    
    "TodayEnergy": SajModbusSensorEntityDescription(
        name="Power generation on current day",
        key="todayenergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "MonthEnergy": SajModbusSensorEntityDescription(
        name="Power generation in current month",
        key="monthenergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "YearEnergy": SajModbusSensorEntityDescription(
        name="Power generation in current year",
        key="yearenergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "TotalEnergy": SajModbusSensorEntityDescription(
        name="Total power generation",
        key="totalenergy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "TodayHour": SajModbusSensorEntityDescription(
        name="Daily working hours",
        key="todayhour",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:progress-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "TotalHour": SajModbusSensorEntityDescription(
        name="Total working hours",
        key="totalhour",
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:progress-clock",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    

    "BatTodayCharge": SajModbusSensorEntityDescription(
        name="Battery Today Charge",
        key="bat_today_charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "BatMonthCharge": SajModbusSensorEntityDescription(
        name="Battery Month Charge",
        key="bat_month_charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "BatYearCharge": SajModbusSensorEntityDescription(
        name="Battery Year Charge",
        key="bat_year_charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "BatTotalCharge": SajModbusSensorEntityDescription(
        name="Battery Total Charge",
        key="bat_total_charge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-charging-100",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),

    "BatTodayDischarge": SajModbusSensorEntityDescription(
        name="Battery Today Discharge",
        key="bat_today_discharge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-minus",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "BatMonthDischarge": SajModbusSensorEntityDescription(
        name="Battery Month Discharge",
        key="bat_month_discharge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-minus",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "BatYearDischarge": SajModbusSensorEntityDescription(
        name="Battery Year Discharge",
        key="bat_year_discharge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-minus",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "BatTotalDischarge": SajModbusSensorEntityDescription(
        name="Battery Total Discharge",
        key="bat_total_discharge",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-minus",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,

    ),

    "InvTodayGen": SajModbusSensorEntityDescription(
        name="Inverter Today Generation",
        key="inv_today_gen",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "InvMonthGen": SajModbusSensorEntityDescription(
        name="Inverter Month Generation",
        key="inv_month_gen",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "InvYearGen": SajModbusSensorEntityDescription(
        name="Inverter Year Generation",
        key="inv_year_gen",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "InvTotalGen": SajModbusSensorEntityDescription(
        name="Inverter Total Generation",
        key="inv_total_gen",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "TotalTodayLoad": SajModbusSensorEntityDescription(
        name="Total Today Load",
        key="total_today_load",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

    "TotalMonthLoad": SajModbusSensorEntityDescription(
        name="Total Month Load",
        key="total_month_load",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "TotalYearLoad": SajModbusSensorEntityDescription(
        name="Total Year Load",
        key="total_year_load",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "TotalTotalLoad": SajModbusSensorEntityDescription(
        name="Total Load",
        key="total_total_load",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:home-import-outline",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),

    "ErrorCount": SajModbusSensorEntityDescription(
        name="Error count",
        key="errorcount",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),

  

    
}

DEVICE_STATUSSES = {
    0: "Not Connected",
    1: "Waiting",
    2: "Normal",
    3: "Error",
    4: "Upgrading",
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
