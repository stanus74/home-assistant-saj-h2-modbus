import asyncio
import logging
import struct
from typing import Dict, Any, List, Optional, TypeAlias
from pymodbus.client.mixin import ModbusClientMixin
from .const import DEVICE_STATUSSES, FAULT_MESSAGES, ModbusClient, Lock
from .modbus_utils import try_read_registers

DataDict: TypeAlias = Dict[str, Any]

_LOGGER = logging.getLogger(__name__)

async def _read_modbus_data(
    client: ModbusClient,
    lock: Lock,
    start_address: int,
    count: int,
    decode_instructions: List[tuple],
    data_key: str,
    default_decoder: str = "16u",
    default_factor: float = 0.01,
    log_level_on_error: int = logging.ERROR
) -> DataDict:
    """Helper function to read and decode Modbus data."""
    try:
        regs = await try_read_registers(client, lock, 1, start_address, count)

        if not regs:
            _LOGGER.log(log_level_on_error, f"Error reading modbus data: No response for {data_key}")
            return {}

        new_data = {}
        index = 0

        for instruction in decode_instructions:
            key, method, factor = (instruction + (default_factor,))[:3]
            method = method or default_decoder

            if method == "skip_bytes":
                index += factor // 2  # factor in Bytes; 2 Bytes per register
                continue
            if not key or index >= len(regs):
                # Missing key or not enough registers: skip field
                continue

            try:
                raw_value = regs[index]
                if method == "16i":
                    value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.INT16)
                elif method == "16u":
                    value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.UINT16)
                elif method == "32u":
                    if index + 1 >= len(regs):
                        value = 0  # Block too short -> neutral value (existing behavior)
                    else:
                        value = client.convert_from_registers([raw_value, regs[index + 1]], ModbusClientMixin.DATATYPE.UINT32)
                        index += 1
                else:
                    value = raw_value

                new_data[key] = round(value * factor, 2) if factor != 1 else value
            except Exception as e:
                _LOGGER.log(log_level_on_error, f"Error decoding {key}: {e}")
                # Do not discard the entire dataset; continue to the next field
            finally:
                index += 1

        return new_data

    except ValueError as ve:
        # Known error, e.g. Exception 131/0
        _LOGGER.info(f"Unsupported Modbus register for {data_key}: {ve}")
        return {}

    except Exception as e:
        _LOGGER.log(log_level_on_error, f"Error reading modbus data: {e}")
        return {}

async def read_modbus_inverter_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads basic inverter data using the pymodbus 3.9 API, without BinaryPayloadDecoder."""
    try:
        regs = await try_read_registers(client, lock, 1, 0x8F00, 29)
        data = {}
        index = 0

        # Basic parameters: devtype and subtype as 16-bit unsigned values
        for key in ["devtype", "subtype"]:
            value = client.convert_from_registers(
                [regs[index]], ModbusClientMixin.DATATYPE.UINT16
            )
            data[key] = value
            index += 1

        # Communication version: 16-bit unsigned, multiplied by 0.001 and rounded to 3 decimal places
        commver = client.convert_from_registers(
            [regs[index]], ModbusClientMixin.DATATYPE.UINT16
        )
        data["commver"] = round(commver * 0.001, 3)
        index += 1

        # Serial number and PC: 20 bytes each (equivalent to 10 registers)
        for key in ["sn", "pc"]:
            reg_slice = regs[index : index + 10]
            raw_bytes = b"".join(struct.pack(">H", r) for r in reg_slice)
            data[key] = raw_bytes.decode("ascii", errors="replace").strip()
            index += 10

        # Hardware version numbers: Each as 16-bit unsigned, multiplied by 0.001
        for key in ["dv", "mcv", "scv", "disphwversion", "ctrlhwversion", "powerhwversion"]:
            value = client.convert_from_registers(
                [regs[index]], ModbusClientMixin.DATATYPE.UINT16
            )
            data[key] = round(value * 0.001, 3)
            index += 1

        return data
    except Exception as e:
        _LOGGER.error(f"Error reading inverter data: {e}")
        return {}

async def read_modbus_realtime_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads real-time operating data."""
    decode_instructions = [
        ("mpvmode", None), ("faultMsg0", "32u"), ("faultMsg1", "32u"),
        ("faultMsg2", "32u"), (None, "skip_bytes", 8), ("errorcount", None),
        ("SinkTemp", "16i", 0.1), ("AmbTemp", "16i", 0.1),
        ("gfci", None), ("iso1", None), ("iso2", None), ("iso3", None), ("iso4", None),
    ]

    data = await _read_modbus_data(client, lock, 16388, 19, decode_instructions, 'realtime_data', default_factor=1)

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
        _LOGGER.error(f"Fault detected: {data['faultmsg']}")
        
    return data

async def read_additional_modbus_data_1_part_1(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the first part of additional operating data (Set 1), up to sensor pv4Power."""
    decode_instructions_part_1 = [
        ("BatTemp", "16i", 0.1), ("batEnergyPercent", None), (None, "skip_bytes", 2),
        ("pv1Voltage", None, 0.1), ("pv1TotalCurrent", None), ("pv1Power", None, 1),
        ("pv2Voltage", None, 0.1), ("pv2TotalCurrent", None), ("pv2Power", None, 1),
        ("pv3Voltage", None, 0.1), ("pv3TotalCurrent", None), ("pv3Power", None, 1),
        ("pv4Voltage", None, 0.1), ("pv4TotalCurrent", None), ("pv4Power", None, 1),
    ]

    return await _read_modbus_data(client, lock, 16494, 15, decode_instructions_part_1, 'additional_data_1_part_1', default_factor=0.01)

async def read_additional_modbus_data_1_part_2(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the second part of additional operating data (Set 1)."""
    decode_instructions_part_2 = [
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
    
    return await _read_modbus_data(client, lock, 16533, 25, decode_instructions_part_2, 'additional_data_1_part_2', default_factor=1)

async def read_additional_modbus_data_2_part_1(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the first part of additional operating data (Set 2)."""
    data_keys_part_1 = [
        "todayenergy", "monthenergy", "yearenergy", "totalenergy",
        "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
        "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
        "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
    ]
    decode_instructions_part_1 = [(key, "32u", 0.01) for key in data_keys_part_1]

    return await _read_modbus_data(client, lock, 16575, 32, decode_instructions_part_1, 'additional_data_2_part_1')

async def read_additional_modbus_data_2_part_2(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the second part of additional operating data (Set 2)."""
    data_keys_part_2 = [
        "total_today_load", "total_month_load", "total_year_load", "total_total_load",
        "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
        "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
        "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
    ]
    decode_instructions_part_2 = [(key, "32u", 0.01) for key in data_keys_part_2]

    return await _read_modbus_data(client, lock, 16607, 32, decode_instructions_part_2, 'additional_data_2_part_2')

async def read_additional_modbus_data_3(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads additional operating data (Set 3) - first part."""
    decode_instructions_part_3 = [
        ("today_pv_energy2", "32u", 0.01), ("month_pv_energy2", "32u", 0.01),
        ("year_pv_energy2", "32u", 0.01), ("total_pv_energy2", "32u", 0.01),
        ("today_pv_energy3", "32u", 0.01), ("month_pv_energy3", "32u", 0.01),
        ("year_pv_energy3", "32u", 0.01), ("total_pv_energy3", "32u", 0.01),
        ("sell_today_energy_2", "32u", 0.01), ("sell_month_energy_2", "32u", 0.01),
        ("sell_year_energy_2", "32u", 0.01), ("sell_total_energy_2", "32u", 0.01),
        ("sell_today_energy_3", "32u", 0.01), ("sell_month_energy_3", "32u", 0.01),
        ("sell_year_energy_3", "32u", 0.01)
    ]

    return await _read_modbus_data(
        client, lock, 16695, 30, decode_instructions_part_3, 
        'additional_data_3', 
        log_level_on_error=logging.WARNING
    )

async def read_additional_modbus_data_3_2(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads additional operating data (Set 3) - second part."""
    decode_instructions_part_3_2 = [
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

    return await _read_modbus_data(
        client, lock, 16725, 34, decode_instructions_part_3_2, 
        'additional_data_3_2', 
        log_level_on_error=logging.WARNING
    )


async def _read_phase_block(
    client: ModbusClient,
    lock: Lock,
    start: int,
    count: int,
    fields: List[tuple],
    key_prefix: str,
    *,
    default_factor: float = 1,
) -> DataDict:
    """
    Reads a 3-phase block (R/S/T) compactly.
    fields: List of (name, method, [factor]) -> generates Keys R<key_prefix><name>, S..., T...
    """
    decode: List[tuple] = []
    for phase in ("R", "S", "T"):
        for entry in fields:
            name, method, *fac = entry
            factor = fac[0] if fac else default_factor
            decode.append((f"{phase}{key_prefix}{name}", method, factor))
    return await _read_modbus_data(client, lock, start, count, decode, f"{key_prefix.lower()}phase_data", default_factor=default_factor)

async def read_additional_modbus_data_4(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads data for grid parameters (R, S, and T phase)."""
    fields = [
        ("GridVolt", "16u", 0.1),
        ("GridCurr", "16i", 0.01),
        ("GridFreq", "16u", 0.01),
        ("GridDCI", "16i", 1),
        ("GridPowerWatt", "16i", 1),
        ("GridPowerVA", "16u", 1),
        ("GridPowerPF", "16i", 1),
    ]
    return await _read_phase_block(client, lock, 16433, 21, fields, key_prefix="", default_factor=0.001)

async def read_inverter_phase_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads data for inverter phase parameters (R, S, and T phase)."""
    fields = [
        ("InvVolt", "16u", 0.1),
        ("InvCurr", "16i", 0.01),
        ("InvFreq", "16u", 0.01),
        ("InvPowerWatt", "16i", 1),
        ("InvPowerVA", "16u", 1),
    ]
    return await _read_phase_block(client, lock, 16454, 15, fields, key_prefix="", default_factor=1)

async def read_offgrid_output_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads data for offgrid output parameters (R, S, and T phase)."""
    fields = [
        ("OutVolt", "16u", 0.1),
        ("OutCurr", "16u", 0.01),
        ("OutFreq", "16u", 0.01),
        ("OutDVI", "16i", 1),
        ("OutPowerWatt", "16u", 1),
        ("OutPowerVA", "16u", 1),
    ]
    return await _read_phase_block(client, lock, 16469, 18, fields, key_prefix="", default_factor=1)

async def read_battery_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads battery data from registers 40960 to 41015."""
    decode_instructions = [
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
    
    return await _read_modbus_data(client, lock, 40960, 56, decode_instructions, 'battery_data', default_factor=0.01)

def decode_time(value: int) -> str:
    """Decodes a time value from the inverter format to a string representation.
    
    Args:
        value: The raw time value from the inverter
        
    Returns:
        A string in the format "HH:MM"
    """
    return f"{(value >> 8) & 0xFF:02d}:{value & 0xFF:02d}"

async def read_charge_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the Charge registers."""
    # Read the Charge registers directly with the sensor names
    decode_instructions = [
        ("charging_enabled_raw", "16u", 1),    # 0x3604
        ("discharging_enabled_raw", "16u", 1), # 0x3605
        ("charge_start_time", "16u", 1),       # 0x3606
        ("charge_end_time", "16u", 1),         # 0x3607
        ("charge_power_raw", "16u", 1),        # 0x3608
    ]

    data = await _read_modbus_data(client, lock, 0x3604, 5, decode_instructions, "charge_data_extended", default_factor=1)

    if data:
        try:
            data["charge_start_time"] = decode_time(data["charge_start_time"])
            data["charge_end_time"] = decode_time(data["charge_end_time"])

            power_value = data.pop("charge_power_raw")
            data["charge_day_mask"] = (power_value >> 8) & 0xFF
            data["charge_power_percent"] = power_value & 0xFF

            data["charging_enabled"] = data.pop("charging_enabled_raw") > 0
            data["discharging_enabled"] = data.pop("discharging_enabled_raw") > 0

        except Exception as e:
            _LOGGER.error(f"Error processing Charge data: {e}")
            return {}

    return data

async def read_discharge_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads all Discharge registers at once (discharge 1-7), compactly."""
    # 7 * 3 registers starting from 0x361B
    decode_instructions: List[tuple] = []
    for i in range(7):
        p = "" if i == 0 else str(i + 1)
        decode_instructions += [
            (f"discharge{p}_start_time", "16u", 1),
            (f"discharge{p}_end_time", "16u", 1),
            (f"discharge{p}_power_raw", "16u", 1),
        ]

    data = await _read_modbus_data(client, lock, 0x361B, 21, decode_instructions, "discharge_data", default_factor=1)
    if not data:
        return {}

    try:
        for i in range(7):
            p = "" if i == 0 else str(i + 1)
            k_start, k_end, k_raw = f"discharge{p}_start_time", f"discharge{p}_end_time", f"discharge{p}_power_raw"
            if k_start in data:
                data[k_start] = decode_time(data[k_start])
            if k_end in data:
                data[k_end] = decode_time(data[k_end])
            if k_raw in data:
                raw = data.pop(k_raw)
                data[f"discharge{p}_day_mask"] = (raw >> 8) & 0xFF
                data[f"discharge{p}_power_percent"] = raw & 0xFF
    except Exception as e:
        _LOGGER.error("Error processing discharge data: %s", e)
        return {}
    return data



async def read_anti_reflux_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the Anti-Reflux registers using the generic read_modbus_data function."""
    decode = [
        ("AntiRefluxPowerLimit", "16u", 1),
        ("AntiRefluxCurrentLimit", "16u", 1),
        ("AntiRefluxCurrentmode_raw", "16u", 1),
    ]
    try:
        data = await _read_modbus_data(client, lock, 0x365A, 3, decode, "anti_reflux_data", default_factor=1)
        if not data:
            return {}
        mode = data.pop("AntiRefluxCurrentmode_raw", None)
        if mode is not None:
            modes = {
                0: "0: Not open anti-reflux",
                1: "1: Total power mode",
                2: "2: Phase current mode",
                3: "3: Phase power mode",
            }
            data["AntiRefluxCurrentmode"] = modes.get(mode, f"Unknown mode ({mode})")
        return data
    except Exception as e:
        _LOGGER.error("Error reading Anti-Reflux data: %s", e)
        return {}

async def read_passive_battery_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads the Passive Charge/Discharge and Battery configuration registers."""
    decode_instructions = [
        ("Passive_charge_enable", "16u", 1),
        ("Passive_GridChargePower", "16u"),
        ("Passive_GridDisChargePower", "16u"),
        ("Passive_BatChargePower", "16u"),
        ("Passive_BatDisChargePower", "16u"),
        (None, "skip_bytes", 18),  # Skip registers 363B-3643
        ("BatOnGridDisDepth", "16u", 1),
        ("BatOffGridDisDepth", "16u", 1),
        ("BatcharDepth", "16u", 1),
        ("AppMode", "16u", 1),
        (None, "skip_bytes", 10),  # Skip registers between AppMode (3647h) and BatChargePower (364Dh)
        ("BatChargePower", "16u"),  # Register 364Dh
        ("BatDischargePower", "16u"),  # Register 364Eh
        ("GridChargePower", "16u"),  # Register 364Fh
        ("GridDischargePower", "16u"),  # Register 3650h
    ]

    try:
        data = await _read_modbus_data(client, lock, 0x3636, 27, decode_instructions, "passive_battery_data", default_factor=0.1)
        return data
    except Exception as e:
        _LOGGER.error(f"Error reading Passive Battery data: {e}")
        return {}

async def read_meter_a_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads Meter A data."""
    decode_instructions = [
        ("Meter_A_Volt1", "16u", 0.1),
        ("Meter_A_Curr1", "16i", 0.01),
        ("Meter_A_PowerW", "16i", 1),
        ("Meter_A_PowerV", "16u", 1),
        ("Meter_A_PowerFa", "16i", 0.001),
        ("Meter_A_Freq1", "16u", 0.01),
        ("Meter_A_Volt2", "16u", 0.1),
        ("Meter_A_Curr2", "16i", 0.01),
        ("Meter_A_PowerW_2", "16i", 1),
        ("Meter_A_PowerV_2", "16u", 1),
        ("Meter_A_PowerFa_2", "16i", 0.001),
        ("Meter_A_Freq2", "16u", 0.01),
        ("Meter_A_Volt3", "16u", 0.1),
        ("Meter_A_Curr3", "16i", 0.01),
        ("Meter_A_PowerW_3", "16i", 1),
        ("Meter_A_PowerV_3", "16u", 1),
        ("Meter_A_PowerFa_3", "16i", 0.001),
        ("Meter_A_Freq3", "16u", 0.01),
    ]

    return await _read_modbus_data(client, lock, 0xA03D, 18, decode_instructions, "meter_a_data")

async def read_side_net_data(client: ModbusClient, lock: Lock) -> DataDict:
    """Reads data for side-net parameters."""
    decode_instructions = [
        ("ROnGridOutVolt", "16u", 0.1),
        ("ROnGridOutCurr", "16u", 0.01),
        ("ROnGridOutFreq", "16u", 0.01),
        ("ROnGridOutPowerWatt", "16u", 1),
        ("SOnGridOutVolt", "16u", 0.1),
        ("SOnGridOutPowerWatt", "16u", 1),
        ("TOnGridOutVolt", "16u", 0.1),
        ("TOnGridOutPowerWatt", "16u", 1),
    ]
    
    return await _read_modbus_data(client, lock, 16525, 8, decode_instructions, "side_net_data")
