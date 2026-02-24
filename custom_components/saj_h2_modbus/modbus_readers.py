import asyncio
import logging
import struct
from typing import Dict, Any, List, Optional, TypeAlias
from pymodbus.client import ModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin

# Use explicit asyncio.Lock for typing to reduce dependency on .const specifics
from asyncio import Lock

from .const import DEVICE_STATUSSES, FAULT_MESSAGES
from .modbus_utils import try_read_registers, ReconnectionNeededError

DataDict: TypeAlias = Dict[str, Any]
ReadResult: TypeAlias = tuple[DataDict, List[str]]

_LOGGER = logging.getLogger(__name__)


def _log_partial_errors(data_key: str, errors: List[str], log_level_on_error: int) -> None:
    """Emit a single log entry for partial decode failures."""
    if not errors:
        return

    log_level = logging.WARNING if log_level_on_error > logging.WARNING else log_level_on_error
    _LOGGER.log(
        log_level,
        "Partial errors decoding %s (%d fields): %s",
        data_key,
        len(errors),
        "; ".join(errors),
    )

# --- Static Decoding Maps ---
# (Maps are kept as-is; omitted here to save space.)

REALTIME_DATA_MAP = [
    ("mpvmode", None), ("faultMsg0", "32u"), ("faultMsg1", "32u"),
    ("faultMsg2", "32u"), (None, "skip_bytes", 8), ("errorcount", None),
    ("SinkTemp", "16i", 0.1), ("AmbTemp", "16i", 0.1),
    ("gfci", None), ("iso1", None), ("iso2", None), ("iso3", None), ("iso4", None),
]

ADDITIONAL_DATA_1_PART_1_MAP = [
    ("BatTemp", "16i", 0.1), ("batEnergyPercent", None), (None, "skip_bytes", 2),
    ("pv1Voltage", None, 0.1), ("pv1TotalCurrent", None), ("pv1Power", None, 1),
    ("pv2Voltage", None, 0.1), ("pv2TotalCurrent", None), ("pv2Power", None, 1),
    ("pv3Voltage", None, 0.1), ("pv3TotalCurrent", None), ("pv3Power", None, 1),
    ("pv4Voltage", None, 0.1), ("pv4TotalCurrent", None), ("pv4Power", None, 1),
]

ADDITIONAL_DATA_1_PART_2_MAP = [
    ("directionPV", None), ("directionBattery", "16i"), ("directionGrid", "16i"),
    ("directionOutput", None), (None, "skip_bytes", 14), ("TotalLoadPower", "16i"),
    ("CT_GridPowerWatt", "16i"), ("CT_GridPowerVA", "16i"),
    ("CT_PVPowerWatt", "16i"), ("CT_PVPowerVA", "16i"),
    ("pvPower", "16i"), ("batteryPower", "16i"),
    ("totalgridPower", "16i"), ("totalgridPowerVA", "16i"),
    ("inverterPower", "16i"), ("TotalInvPowerVA", "16i"),
    ("BackupTotalLoadPowerWatt", None), ("BackupTotalLoadPowerVA", None),
    ("gridPower", "16i"),
]

_DATA_KEYS_PART_2_1 = [
    "todayenergy", "monthenergy", "yearenergy", "totalenergy",
    "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
    "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
    "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
]
ADDITIONAL_DATA_2_PART_1_MAP = [(key, "32u", 0.01) for key in _DATA_KEYS_PART_2_1]

_DATA_KEYS_PART_2_2 = [
    "total_today_load", "total_month_load", "total_year_load", "total_total_load",
    "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
    "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
    "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
]
ADDITIONAL_DATA_2_PART_2_MAP = [(key, "32u", 0.01) for key in _DATA_KEYS_PART_2_2]

ADDITIONAL_DATA_3_MAP = [
    ("today_pv_energy2", "32u", 0.01), ("month_pv_energy2", "32u", 0.01),
    ("year_pv_energy2", "32u", 0.01), ("total_pv_energy2", "32u", 0.01),
    ("today_pv_energy3", "32u", 0.01), ("month_pv_energy3", "32u", 0.01),
    ("year_pv_energy3", "32u", 0.01), ("total_pv_energy3", "32u", 0.01),
    ("sell_today_energy_2", "32u", 0.01), ("sell_month_energy_2", "32u", 0.01),
    ("sell_year_energy_2", "32u", 0.01), ("sell_total_energy_2", "32u", 0.01),
    ("sell_today_energy_3", "32u", 0.01), ("sell_month_energy_3", "32u", 0.01),
    ("sell_year_energy_3", "32u", 0.01)
]

ADDITIONAL_DATA_3_2_MAP = [
    ("sell_total_energy_3", "32u", 0.01), ("feedin_today_energy_2", "32u", 0.01),
    ("feedin_month_energy_2", "32u", 0.01), ("feedin_year_energy_2", "32u", 0.01),
    ("feedin_total_energy_2", "32u", 0.01), ("feedin_today_energy_3", "32u", 0.01),
    ("feedin_month_energy_3", "32u", 0.01), ("feedin_year_energy_3", "32u", 0.01),
    ("feedin_total_energy_3", "32u", 0.01), ("sum_feed_in_today", "32u", 0.01),
    ("sum_feed_in_month", "32u", 0.01), ("sum_feed_in_year", "32u", 0.01),
    ("sum_feed_in_total", "32u", 0.01), ("sum_sell_today", "32u", 0.01),
    ("sum_sell_month", "32u", 0.01), ("sum_sell_year", "32u", 0.01),
    ("sum_sell_total", "32u", 0.01)
]

ADDITIONAL_DATA_4_FIELDS = [
    ("GridVolt", "16u", 0.1), ("GridCurr", "16i", 0.01), ("GridFreq", "16u", 0.01),
    ("GridDCI", "16i", 1), ("GridPowerWatt", "16i", 1), ("GridPowerVA", "16u", 1),
    ("GridPowerPF", "16i", 1),
]

INVERTER_PHASE_FIELDS = [
    ("InvVolt", "16u", 0.1), ("InvCurr", "16i", 0.01), ("InvFreq", "16u", 0.01),
    ("InvPowerWatt", "16i", 1), ("InvPowerVA", "16u", 1),
]

OFFGRID_OUTPUT_FIELDS = [
    ("OutVolt", "16u", 0.1), ("OutCurr", "16u", 0.01), ("OutFreq", "16u", 0.01),
    ("OutDVI", "16i", 1), ("OutPowerWatt", "16u", 1), ("OutPowerVA", "16u", 1),
]

BATTERY_DATA_MAP = [
    ("BatNum", None, 1), ("BatCapcity", None, 1), ("Bat1FaultMSG", None, 1), ("Bat1WarnMSG", None, 1),
    ("Bat2FaultMSG", None, 1), ("Bat2WarnMSG", None, 1), ("Bat3FaultMSG", None, 1), ("Bat3WarnMSG", None, 1),
    ("Bat4FaultMSG", None, 1), ("Bat4WarnMSG", None, 1), ("BatUserCap", None, 1), ("BatOnline", None, 1),
    ("Bat1SOC", None), ("Bat1SOH", None), ("Bat1Voltage", None, 0.1), ("Bat1Current", "16i"),
    ("Bat1Temperature", "16i", 0.1), ("Bat1CycleNum", None, 1), ("Bat2SOC", None), ("Bat2SOH", None),
    ("Bat2Voltage", None, 0.1), ("Bat2Current", "16i"), ("Bat2Temperature", "16i", 0.1),
    ("Bat2CycleNum", None, 1), ("Bat3SOC", None), ("Bat3SOH", None), ("Bat3Voltage", None, 0.1),
    ("Bat3Current", "16i"), ("Bat3Temperature", "16i", 0.1), ("Bat3CycleNum", None, 1),
    ("Bat4SOC", None), ("Bat4SOH", None), ("Bat4Voltage", None, 0.1), ("Bat4Current", "16i"),
    ("Bat4Temperature", "16i", 0.1), ("Bat4CycleNum", None, 1), (None, "skip_bytes", 12),
    ("Bat1DischarCap", "32u", 1), ("Bat2DischarCap", "32u", 1), ("Bat3DischarCap", "32u", 1), ("Bat4DischarCap", "32u", 1),
    ("BatProtHigh", None, 0.1), ("BatProtLow", None, 0.1), ("Bat_Chargevoltage", None, 0.1), ("Bat_DisCutOffVolt", None, 0.1),
    ("BatDisCurrLimit", None, 0.1), ("BatChaCurrLimit", None, 0.1),
]

CHARGE_DATA_MAP = [
    ("charge_time_enable", "16u", 1),      # 0x3604 - RAW bitmask value (0-127)
    ("discharge_time_enable", "16u", 1),   # 0x3605 - RAW bitmask value (0-127)
]
for i in range(7):
    p = "" if i == 0 else str(i + 1)
    CHARGE_DATA_MAP += [
        (f"charge{p}_start_time", "16u", 1), (f"charge{p}_end_time", "16u", 1), (f"charge{p}_power_raw", "16u", 1),
    ]

DISCHARGE_DATA_MAP: List[tuple] = []
for i in range(7):
    p = "" if i == 0 else str(i + 1)
    DISCHARGE_DATA_MAP += [
        (f"discharge{p}_start_time", "16u", 1), (f"discharge{p}_end_time", "16u", 1), (f"discharge{p}_power_raw", "16u", 1),
    ]

PASSIVE_BATTERY_DATA_MAP = [
    ("passive_charge_enable", "16u", 1), ("passive_grid_charge_power", "16u"), ("passive_grid_discharge_power", "16u"),
    ("passive_bat_charge_power", "16u"), ("passive_bat_discharge_power", "16u"),
    (None, "skip_bytes", 18),
    ("BatOnGridDisDepth", "16u", 1), ("BatOffGridDisDepth", "16u", 1), ("BatcharDepth", "16u", 1), ("AppMode", "16u", 1),
    (None, "skip_bytes", 10),
    ("BatChargePower", "16u"), ("BatDischargePower", "16u"), ("GridChargePower", "16u"), ("GridDischargePower", "16u"),
    (None, "skip_bytes", 18),
    ("AntiRefluxPowerLimit", "16u", 1), ("AntiRefluxCurrentLimit", "16u", 1), ("AntiRefluxCurrentmode_raw", "16u", 1),
]

METER_A_DATA_MAP = [
    ("Meter_A_Volt1", "16u", 0.1), ("Meter_A_Curr1", "16i", 0.01), ("Meter_A_PowerW", "16i", 1),
    ("Meter_A_PowerV", "16u", 1), ("Meter_A_PowerFa", "16i", 0.001), ("Meter_A_Freq1", "16u", 0.01),
    ("Meter_A_Volt2", "16u", 0.1), ("Meter_A_Curr2", "16i", 0.01), ("Meter_A_PowerW_2", "16i", 1),
    ("Meter_A_PowerV_2", "16u", 1), ("Meter_A_PowerFa_2", "16i", 0.001), ("Meter_A_Freq2", "16u", 0.01),
    ("Meter_A_Volt3", "16u", 0.1), ("Meter_A_Curr3", "16i", 0.01), ("Meter_A_PowerW_3", "16i", 1),
    ("Meter_A_PowerV_3", "16u", 1), ("Meter_A_PowerFa_3", "16i", 0.001), ("Meter_A_Freq3", "16u", 0.01),
]

SIDE_NET_DATA_MAP = [
    ("ROnGridOutVolt", "16u", 0.1), ("ROnGridOutCurr", "16u", 0.01), ("ROnGridOutFreq", "16u", 0.01),
    ("ROnGridOutPowerWatt", "16u", 1),
    ("SOnGridOutVolt", "16u", 0.1), ("SOnGridOutPowerWatt", "16u", 1),
    ("TOnGridOutVolt", "16u", 0.1), ("TOnGridOutPowerWatt", "16u", 1),
]

# --- End Static Decoding Maps ---

async def _read_modbus_data(
    client: ModbusTcpClient,
    lock: Lock,
    start_address: int,
    count: int,
    decode_instructions: List[tuple],
    data_key: str,
    default_decoder: str = "16u",
    default_factor: float = 0.01,
    log_level_on_error: int = logging.ERROR
) -> ReadResult:
    """Helper function to read and decode Modbus data with partial-error resilience."""
    errors: List[str] = []
    new_data: DataDict = {}

    try:
        regs = await try_read_registers(client, lock, 1, start_address, count)
    except ValueError as ve:
        # Known error, e.g. Exception 131/0
        _LOGGER.info("Unsupported Modbus register for %s: %s", data_key, ve)
        errors.append(f"{data_key}: {ve}")
        return new_data, errors
    except ReconnectionNeededError:
        # CRITICAL FIX: Re-raise reconnection errors so the Hub can handle them!
        raise
    except Exception as e:
        _LOGGER.log(log_level_on_error, "Error reading modbus data for %s: %s", data_key, e)
        errors.append(f"{data_key}: {e}")
        return new_data, errors

    if not regs:
        message = f"{data_key}: No response"
        _LOGGER.log(log_level_on_error, "Error reading modbus data: No response for %s", data_key)
        errors.append(message)
        return new_data, errors

    index = 0

    for instruction in decode_instructions:
        key, method, factor = (instruction + (default_factor,))[:3]
        method = method or default_decoder

        if method == "skip_bytes":
            try:
                index += int(factor) // 2  # factor in Bytes; 2 Bytes per register
            except (TypeError, ValueError):
                errors.append(f"{data_key}: invalid skip_bytes factor '{factor}'")
            continue

        if not key:
            continue

        if index >= len(regs):
            errors.append(f"{key}: missing register at index {index}")
            continue

        try:
            raw_value = regs[index]
            if method == "16i":
                value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.INT16)
            elif method == "16u":
                value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.UINT16)
            elif method == "32u":
                if index + 1 >= len(regs):
                    errors.append(f"{key}: insufficient registers for 32-bit value")
                    value = 0
                else:
                    value = client.convert_from_registers(
                        [raw_value, regs[index + 1]], ModbusClientMixin.DATATYPE.UINT32
                    )
                    index += 1
            else:
                value = raw_value

            new_data[key] = round(value * factor, 2) if factor != 1 else value
        except Exception as e:
            errors.append(f"{key}: {e}")
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Error decoding %s for %s: %s", key, data_key, e)
        finally:
            index += 1

    return new_data, errors

async def read_modbus_inverter_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads basic inverter data using the pymodbus 3.9 API."""
    try:
        regs = await try_read_registers(client, lock, 1, 0x8F00, 29)
        data = {}
        index = 0

        # Basic parameters: devtype and subtype
        for key in ["devtype", "subtype"]:
            value = client.convert_from_registers([regs[index]], ModbusClientMixin.DATATYPE.UINT16)
            data[key] = value
            index += 1

        # Communication version
        commver = client.convert_from_registers([regs[index]], ModbusClientMixin.DATATYPE.UINT16)
        data["commver"] = round(commver * 0.001, 3)
        index += 1

        # Serial number and PC
        for key in ["sn", "pc"]:
            reg_slice = regs[index : index + 10]
            raw_bytes = b"".join(struct.pack(">H", r) for r in reg_slice)
            data[key] = raw_bytes.decode("ascii", errors="replace").strip()
            index += 10

        # Hardware versions
        for key in ["dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]:
            value = client.convert_from_registers([regs[index]], ModbusClientMixin.DATATYPE.UINT16)
            data[key] = round(value * 0.001, 3)
            index += 1

        return data
    
    except ReconnectionNeededError:
        raise # Allow Hub to see this and reconnect

    except Exception as e:
        _LOGGER.error("Error reading inverter data: %s", e)
        return {}

# ============================================================================
# CONFIGURATION FOR DATA READING FUNCTIONS
# ============================================================================

# OPTIMIZATION: Configuration-driven approach consolidates parameters for simple
# data reading wrappers to reduce code duplication while maintaining
# backward compatibility. All wrapper functions now use _read_configured_data()
# or _read_configured_phase_data() helper functions.

_DATA_READ_CONFIG = {
    "additional_data_1_part_1": {
        "address": 16494,
        "count": 15,
        "decode_map": ADDITIONAL_DATA_1_PART_1_MAP,
        "data_key": "additional_data_1_part_1",
        "default_factor": 0.01,
    },
    "additional_data_1_part_2": {
        "address": 16533,
        "count": 25,
        "decode_map": ADDITIONAL_DATA_1_PART_2_MAP,
        "data_key": "additional_data_1_part_2",
        "default_factor": 1,
    },
    "additional_data_2_part_1": {
        "address": 16575,
        "count": 32,
        "decode_map": ADDITIONAL_DATA_2_PART_1_MAP,
        "data_key": "additional_data_2_part_1",
    },
    "additional_data_2_part_2": {
        "address": 16607,
        "count": 32,
        "decode_map": ADDITIONAL_DATA_2_PART_2_MAP,
        "data_key": "additional_data_2_part_2",
    },
    "additional_data_3": {
        "address": 16695,
        "count": 30,
        "decode_map": ADDITIONAL_DATA_3_MAP,
        "data_key": "additional_data_3",
        "log_level_on_error": logging.WARNING,
    },
    "additional_data_3_2": {
        "address": 16725,
        "count": 34,
        "decode_map": ADDITIONAL_DATA_3_2_MAP,
        "data_key": "additional_data_3_2",
        "log_level_on_error": logging.WARNING,
    },
    "battery_data": {
        "address": 40960,
        "count": 56,
        "decode_map": BATTERY_DATA_MAP,
        "data_key": "battery_data",
        "default_factor": 0.01,
    },
    "meter_a_data": {
        "address": 0xA03D,
        "count": 18,
        "decode_map": METER_A_DATA_MAP,
        "data_key": "meter_a_data",
    },
    "side_net_data": {
        "address": 16525,
        "count": 8,
        "decode_map": SIDE_NET_DATA_MAP,
        "data_key": "side_net_data",
    },
}

_PHASE_READ_CONFIG = {
    "additional_data_4": {
        "address": 16433,
        "count": 21,
        "fields": ADDITIONAL_DATA_4_FIELDS,
        "key_prefix": "",
        "default_factor": 0.001,
    },
    "inverter_phase": {
        "address": 16454,
        "count": 15,
        "fields": INVERTER_PHASE_FIELDS,
        "key_prefix": "",
        "default_factor": 1,
    },
    "offgrid_output": {
        "address": 16469,
        "count": 18,
        "fields": OFFGRID_OUTPUT_FIELDS,
        "key_prefix": "",
        "default_factor": 1,
    },
}


async def _read_configured_data(client: ModbusTcpClient, lock: Lock, config_key: str) -> DataDict:
    """
    Generic helper function to read Modbus data based on configuration.
    
    Args:
        client: The Modbus client
        lock: Lock for thread safety
        config_key: Key in _DATA_READ_CONFIG dictionary
    
    Returns:
        Dictionary of decoded data
    """
    config = _DATA_READ_CONFIG[config_key]
    data, errors = await _read_modbus_data(
        client,
        lock,
        config["address"],
        config["count"],
        config["decode_map"],
        config["data_key"],
        default_factor=config.get("default_factor", 0.01),
        log_level_on_error=config.get("log_level_on_error", logging.ERROR)
    )
    _log_partial_errors(config["data_key"], errors, config.get("log_level_on_error", logging.ERROR))
    return data


async def _read_configured_phase_data(client: ModbusTcpClient, lock: Lock, config_key: str) -> DataDict:
    """
    Generic helper function to read phase-based Modbus data based on configuration.
    
    Args:
        client: The Modbus client
        lock: Lock for thread safety
        config_key: Key in _PHASE_READ_CONFIG dictionary
    
    Returns:
        Dictionary of decoded phase data
    """
    config = _PHASE_READ_CONFIG[config_key]
    return await _read_phase_block(
        client,
        lock,
        config["address"],
        config["count"],
        config["fields"],
        config["key_prefix"],
        default_factor=config.get("default_factor", 1)
    )


# ============================================================================
# WRAPPER FUNCTIONS (PUBLIC API)
# ============================================================================

# These functions maintain backward compatibility by keeping original signatures
# while using the optimized internal helper functions.

async def read_modbus_realtime_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads real-time operating data."""
    data, errors = await _read_modbus_data(
        client,
        lock,
        16388,
        19,
        REALTIME_DATA_MAP,
        'realtime_data',
        default_factor=1,
    )
    _log_partial_errors('realtime_data', errors, logging.ERROR)

    fault_messages = []
    for key in ["faultMsg0", "faultMsg1", "faultMsg2"]:
        fault_code = data.get(key, 0)
        fault_messages.extend([
            msg for code, msg in FAULT_MESSAGES[int(key[-1])].items()
            if int(fault_code) & code
        ])
        data[key] = fault_code

    data["mpvstatus"] = DEVICE_STATUSSES.get(data.get("mpvmode"), "Unknown")
    data["faultmsg"] = ", ".join(fault_messages).strip()[:254]
    
    if fault_messages:
        _LOGGER.error("Fault detected: %s", data["faultmsg"])
        
    return data

# Simple data reading wrappers - now using configuration-driven approach
async def read_additional_modbus_data_1_part_1(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_1_part_1")

async def read_additional_modbus_data_1_part_2(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_1_part_2")

async def read_additional_modbus_data_2_part_1(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_2_part_1")

async def read_additional_modbus_data_2_part_2(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_2_part_2")

async def read_additional_modbus_data_3(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_3")

async def read_additional_modbus_data_3_2(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "additional_data_3_2")

# ============================================================================
# PHASE DATA READING
# ============================================================================

async def _read_phase_block(client: ModbusTcpClient, lock: Lock, start: int, count: int, fields: List[tuple], key_prefix: str, *, default_factor: float = 1) -> DataDict:
    decode: List[tuple] = []
    for phase in ("R", "S", "T"):
        for entry in fields:
            name, method, *fac = entry
            factor = fac[0] if fac else default_factor
            decode.append((f"{phase}{key_prefix}{name}", method, factor))
    data_key = f"{key_prefix.lower()}phase_data"
    data, errors = await _read_modbus_data(
        client,
        lock,
        start,
        count,
        decode,
        data_key,
        default_factor=default_factor,
    )
    _log_partial_errors(data_key, errors, logging.ERROR)
    return data

# Phase data reading wrappers - now using configuration-driven approach
async def read_additional_modbus_data_4(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_phase_data(client, lock, "additional_data_4")

async def read_inverter_phase_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_phase_data(client, lock, "inverter_phase")

async def read_offgrid_output_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_phase_data(client, lock, "offgrid_output")

# ============================================================================
# BATTERY DATA READING
# ============================================================================

# Simple data reading wrappers - now using configuration-driven approach
async def read_battery_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    return await _read_configured_data(client, lock, "battery_data")


# ============================================================================
# TIME AND POWER SLOT DECODING HELPERS
# ============================================================================

def decode_time(value: int) -> str:
    """Decode a raw time value (HHMM format) to HH:MM string."""
    return f"{(value >> 8) & 0xFF:02d}:{value & 0xFF:02d}"


def _decode_time_power_slots(data: DataDict, prefix: str, slots: int = 7) -> None:
    """
    Decode time and power slot data from raw values.
    
    Args:
        data: Dictionary containing the raw data (modified in-place)
        prefix: Prefix for the slot keys (e.g., "charge" or "discharge")
        slots: Number of slots to decode (default: 7)
    """
    for i in range(slots):
        p = "" if i == 0 else str(i + 1)
        k_start, k_end, k_raw = f"{prefix}{p}_start_time", f"{prefix}{p}_end_time", f"{prefix}{p}_power_raw"
        if k_start in data: data[k_start] = decode_time(data[k_start])
        if k_end in data: data[k_end] = decode_time(data[k_end])
        if k_raw in data:
            raw = data.pop(k_raw)
            data[f"{prefix}{p}_day_mask"] = (raw >> 8) & 0xFF
            data[f"{prefix}{p}_power_percent"] = raw & 0xFF


# ============================================================================
# CHARGE AND DISCHARGE DATA READING
# ============================================================================

async def read_charge_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads charge schedule data and decodes time/power slots."""
    data, errors = await _read_modbus_data(
        client,
        lock,
        0x3604,
        23,
        CHARGE_DATA_MAP,
        "charge_data_extended",
        default_factor=1,
    )
    _log_partial_errors("charge_data_extended", errors, logging.ERROR)
    if data:
        try:
            _decode_time_power_slots(data, "charge")
            # NOTE: These flags only reflect the bitmask (at least one slot planned).
            # Whether charging is actually active depends on AppMode == 1.
            data["charging_enabled"] = data.get("charge_time_enable", 0) > 0
            data["discharging_enabled"] = data.get("discharge_time_enable", 0) > 0
        except Exception as e:
            _LOGGER.error("Error processing Charge data: %s", e)
            return {}
    return data


async def read_discharge_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads discharge schedule data and decodes time/power slots."""
    data, errors = await _read_modbus_data(
        client,
        lock,
        0x361B,
        21,
        DISCHARGE_DATA_MAP,
        "discharge_data",
        default_factor=1,
    )
    _log_partial_errors("discharge_data", errors, logging.ERROR)
    if not data: return {}
    try:
        _decode_time_power_slots(data, "discharge")
    except Exception as e:
        _LOGGER.error("Error processing discharge data: %s", e)
        return {}
    return data


# ============================================================================
# PASSIVE BATTERY AND ANTI-REFLUX DATA
# ============================================================================

async def read_passive_battery_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads passive battery and anti-reflux data with mode decoding."""
    try:
        data, errors = await _read_modbus_data(
            client,
            lock,
            0x3636,
            39,
            PASSIVE_BATTERY_DATA_MAP,
            "passive_battery_anti_reflux_data",
            default_factor=0.1,
        )
        _log_partial_errors("passive_battery_anti_reflux_data", errors, logging.ERROR)
        if data:
            mode = data.pop("AntiRefluxCurrentmode_raw", None)
            if mode is not None:
                modes = {0: "0: Not open anti-reflux", 1: "1: Total power mode", 2: "2: Phase current mode", 3: "3: Phase power mode"}
                data["AntiRefluxCurrentmode"] = modes.get(mode, "Unknown mode (%s)" % mode)
        return data
    except ReconnectionNeededError:
        raise
    except Exception as e:
        _LOGGER.error("Error reading Passive Battery and Anti-Reflux data: %s", e)
        return {}


# ============================================================================
# METER AND SIDE NET DATA
# ============================================================================

async def read_meter_a_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads meter A data and calculates total grid power."""
    data = await _read_configured_data(client, lock, "meter_a_data")
    if data:
        try:
            p1 = data.get("Meter_A_PowerW", 0)
            p2 = data.get("Meter_A_PowerW_2", 0)
            p3 = data.get("Meter_A_PowerW_3", 0)
            data["CT_GridPower_total"] = p1 + p2 + p3
        except Exception as e:
            _LOGGER.error("Error calculating CT_GridPower_total: %s", e)
    return data


async def read_side_net_data(client: ModbusTcpClient, lock: Lock) -> DataDict:
    """Reads side net data."""
    return await _read_configured_data(client, lock, "side_net_data")
