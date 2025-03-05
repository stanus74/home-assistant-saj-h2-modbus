import asyncio
import logging
import struct
from typing import Dict, Any, List, Optional, TypeAlias
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin
from .const import DEVICE_STATUSSES, FAULT_MESSAGES
from .modbus_utils import try_read_registers

# Type aliases to make function signatures more compact
ModbusClient: TypeAlias = AsyncModbusTcpClient
Lock: TypeAlias = asyncio.Lock
DataDict: TypeAlias = Dict[str, Any]

_LOGGER = logging.getLogger(__name__)

# Shared lock for all Modbus read operations
_MODBUS_READ_LOCK = asyncio.Lock()

async def _read_modbus_data(
    client: ModbusClient,
    start_address: int,
    count: int,
    decode_instructions: List[tuple],
    data_key: str,
    default_decoder: str = "16u",
    default_factor: float = 0.01
) -> DataDict:
    """Helper function to read and decode Modbus data."""
    try:
        regs = await try_read_registers(client, _MODBUS_READ_LOCK, 1, start_address, count)
        if not regs:
            _LOGGER.error(f"Error reading modbus data: No response for {data_key}")
            return {}

        new_data = {}
        index = 0

        for instruction in decode_instructions:
            key, method, factor = (instruction + (default_factor,))[:3]
            method = method or default_decoder

            if method == "skip_bytes":
                index += factor // 2  # Each register is 2 bytes in size
                continue

            if not key:
                continue

            try:
                raw_value = regs[index]

                if method == "16i":
                    value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.INT16)
                elif method == "16u":
                    value = client.convert_from_registers([raw_value], ModbusClientMixin.DATATYPE.UINT16)
                elif method == "32u":
                    if index + 1 < len(regs):
                        value = client.convert_from_registers([raw_value, regs[index + 1]], ModbusClientMixin.DATATYPE.UINT32)
                        index += 1  # 32-bit values occupy two registers
                    else:
                        value = 0
                else:
                    value = raw_value  # Default value if no conversion is necessary

                new_data[key] = round(value * factor, 2) if factor != 1 else value
                index += 1

            except Exception as e:
                _LOGGER.error(f"Error decoding {key}: {e}")
                return {}

        return new_data

    except Exception as e:
        _LOGGER.error(f"Error reading modbus data: {e}")
        return {}

async def read_modbus_inverter_data(client: ModbusClient) -> DataDict:
    """Reads basic inverter data using the pymodbus 3.9 API, without BinaryPayloadDecoder."""
    try:
        regs = await try_read_registers(client, _MODBUS_READ_LOCK, 1, 0x8F00, 29)
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

async def read_modbus_realtime_data(client: ModbusClient) -> DataDict:
    """Reads real-time operating data."""
    decode_instructions = [
        ("mpvmode", None), ("faultMsg0", "32u"), ("faultMsg1", "32u"),
        ("faultMsg2", "32u"), (None, "skip_bytes", 8), ("errorcount", None),
        ("SinkTemp", "16i", 0.1), ("AmbTemp", "16i", 0.1),
        ("gfci", None), ("iso1", None), ("iso2", None), ("iso3", None), ("iso4", None),
    ]

    data = await _read_modbus_data(client, 16388, 19, decode_instructions, 'realtime_data', default_factor=1)

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

async def read_additional_modbus_data_1_part_1(client: ModbusClient) -> DataDict:
    """Reads the first part of additional operating data (Set 1), up to sensor pv4Power."""
    decode_instructions_part_1 = [
        ("BatTemp", "16i", 0.1), ("batEnergyPercent", None), (None, "skip_bytes", 2),
        ("pv1Voltage", None, 0.1), ("pv1TotalCurrent", None), ("pv1Power", None, 1),
        ("pv2Voltage", None, 0.1), ("pv2TotalCurrent", None), ("pv2Power", None, 1),
        ("pv3Voltage", None, 0.1), ("pv3TotalCurrent", None), ("pv3Power", None, 1),
        ("pv4Voltage", None, 0.1), ("pv4TotalCurrent", None), ("pv4Power", None, 1),
    ]

    return await _read_modbus_data(client, 16494, 15, decode_instructions_part_1, 'additional_data_1_part_1', default_factor=0.01)

async def read_additional_modbus_data_1_part_2(client: ModbusClient) -> DataDict:
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
    
    return await _read_modbus_data(client, 16533, 25, decode_instructions_part_2, 'additional_data_1_part_2', default_factor=1)

async def read_additional_modbus_data_2_part_1(client: ModbusClient) -> DataDict:
    """Reads the first part of additional operating data (Set 2)."""
    data_keys_part_1 = [
        "todayenergy", "monthenergy", "yearenergy", "totalenergy",
        "bat_today_charge", "bat_month_charge", "bat_year_charge", "bat_total_charge",
        "bat_today_discharge", "bat_month_discharge", "bat_year_discharge", "bat_total_discharge",
        "inv_today_gen", "inv_month_gen", "inv_year_gen", "inv_total_gen",
    ]
    decode_instructions_part_1 = [(key, "32u", 0.01) for key in data_keys_part_1]

    return await _read_modbus_data(client, 16575, 32, decode_instructions_part_1, 'additional_data_2_part_1')

async def read_additional_modbus_data_2_part_2(client: ModbusClient) -> DataDict:
    """Reads the second part of additional operating data (Set 2)."""
    data_keys_part_2 = [
        "total_today_load", "total_month_load", "total_year_load", "total_total_load",
        "backup_today_load", "backup_month_load", "backup_year_load", "backup_total_load",
        "sell_today_energy", "sell_month_energy", "sell_year_energy", "sell_total_energy",
        "feedin_today_energy", "feedin_month_energy", "feedin_year_energy", "feedin_total_energy",
    ]
    decode_instructions_part_2 = [(key, "32u", 0.01) for key in data_keys_part_2]

    return await _read_modbus_data(client, 16607, 32, decode_instructions_part_2, 'additional_data_2_part_2')

async def read_additional_modbus_data_3(client: ModbusClient) -> DataDict:
    """Reads additional operating data (Set 3)."""
    data_keys_part_3 = [
        "today_pv_energy2", "month_pv_energy2", "year_pv_energy2",
        "total_pv_energy2", "today_pv_energy3", "month_pv_energy3",
        "year_pv_energy3", "total_pv_energy3", "sell_today_energy_2",
        "sell_month_energy_2", "sell_year_energy_2", "sell_total_energy_2",
        "sell_today_energy_3", "sell_month_energy_3", "sell_year_energy_3",
        "sell_total_energy_3", "feedin_today_energy_2", "feedin_month_energy_2",
        "feedin_year_energy_2", "feedin_total_energy_2", "feedin_today_energy_3",
        "feedin_month_energy_3", "feedin_year_energy_3", "feedin_total_energy_3",
        "sum_feed_in_today", "sum_feed_in_month", "sum_feed_in_year",
        "sum_feed_in_total", "sum_sell_today", "sum_sell_month",
        "sum_sell_year", "sum_sell_total"
    ]
    decode_instructions_part_3 = [(key, "32u", 0.01) for key in data_keys_part_3]
    
    return await _read_modbus_data(client, 16695, 64, decode_instructions_part_3, 'additional_data_3')

async def read_additional_modbus_data_4(client: ModbusClient) -> DataDict:
    """Reads data for grid parameters (R, S, and T phase)."""
    decode_instructions = [
        ("RGridVolt", None, 0.1), ("RGridCurr", "16i", 0.01), ("RGridFreq", None, 0.01),
        ("RGridDCI", "16i"), ("RGridPowerWatt", "16i", 1),
        ("RGridPowerVA", None, 1), ("RGridPowerPF", "16i"),
        ("SGridVolt", None, 0.1), ("SGridCurr", "16i", 0.01), ("SGridFreq", None, 0.01),
        ("SGridDCI", "16i"), ("SGridPowerWatt", "16i", 1),
        ("SGridPowerVA", None, 1), ("SGridPowerPF", "16i"),
        ("TGridVolt", None, 0.1), ("TGridCurr", "16i", 0.01), ("TGridFreq", None, 0.01),
        ("TGridDCI", "16i"), ("TGridPowerWatt", "16i", 1),
        ("TGridPowerVA", None, 1), ("TGridPowerPF", "16i"),
    ]
    
    return await _read_modbus_data(client, 16433, 21, decode_instructions, "grid_phase_data", default_factor=0.001)

async def read_battery_data(client: ModbusClient) -> DataDict:
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
        ("Bat1DischarCapH", None, 1), ("Bat1DischarCapL", None, 1), ("Bat2DischarCapH", None, 1), ("Bat2DischarCapL", None, 1),
        ("Bat3DischarCapH", None, 1), ("Bat3DischarCapL", None, 1), ("Bat4DischarCapH", None, 1), ("Bat4DischarCapL", None, 1),
        ("BatProtHigh", None, 0.1), ("BatProtLow", None, 0.1), ("Bat_Chargevoltage", None, 0.1), ("Bat_DisCutOffVolt", None, 0.1),
        ("BatDisCurrLimit", None, 0.1), ("BatChaCurrLimit", None, 0.1),
    ]
    
    return await _read_modbus_data(client, 40960, 56, decode_instructions, 'battery_data', default_factor=0.01)

async def read_first_charge_data(client: ModbusClient) -> DataDict:
    """Reads the First Charge registers using the generic read_modbus_data function."""
    decode_instructions = [
        ("first_charge_start_time_raw", "16u", 1),
        ("first_charge_end_time_raw", "16u", 1),
        ("power_time_raw", "16u", 1),
    ]

    data = await _read_modbus_data(client, 0x3606, 3, decode_instructions, "first_charge_data", default_factor=1)

    if data:
        try:
            def decode_time(value: int) -> str:
                return f"{(value >> 8) & 0xFF:02d}:{value & 0xFF:02d}"
            data["first_charge_start_time"] = decode_time(data.pop("first_charge_start_time_raw"))
            data["first_charge_end_time"] = decode_time(data.pop("first_charge_end_time_raw"))
            power_value = data.pop("power_time_raw")
            data["first_charge_day_mask"] = (power_value >> 8) & 0xFF
            data["first_charge_power_percent"] = power_value & 0xFF
        except Exception as e:
            _LOGGER.error(f"Error processing First Charge data: {e}")
            return {}

    return data
