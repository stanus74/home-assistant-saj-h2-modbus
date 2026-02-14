# Charging Management

> Comprehensive guide to all charging modes and functions of the SAJ H2 integration

---

## 🎯 Overview

The SAJ H2 integration offers two main charging modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Time-of-Use** | Time-based charging control | Night charging with cheap electricity |
| **Passive Mode** | Direct power specification | Dynamic PV surplus control |

---

## ⚡ Time-of-Use Mode (Self-Consumption)

### What is Time-of-Use?

Time-of-Use (ToU) enables automatic battery charging based on configured schedules. Ideal for:
- **Night charging** with cheap electricity
- **Automated charging cycles**
- **Time-variable tariffs** (e.g., Tibber, Awattar)

### Slot System (7 Slots)

The inverter supports **7 independent charging schedules**:

```
Slot 1: 22:00 - 06:00 (Night charging) - Mon-Fri
Slot 2: 12:00 - 14:00 (Midday boost) - Sat,Sun  
Slot 3: 02:00 - 05:00 (Super off-peak) - Daily
...
```

**Important registers:**
- **0x3604**: Charge Time Enable (bitmask)
- **0x3605**: Discharge Time Enable (bitmask)

### Understanding Bit Layout

Both registers (0x3604/0x3605) use the same bit layout:

```
Bit 0: Charging/Discharging State (1 = active, 0 = inactive)
Bit 1: Slot 1 Enable
Bit 2: Slot 2 Enable
Bit 3: Slot 3 Enable
Bit 4: Slot 4 Enable
Bit 5: Slot 5 Enable
Bit 6: Slot 6 Enable
Bit 7: Reserved

Example: 0x0F = 00001111 = Slots 1-4 enabled
```

### Configuration

#### Entities for Time-of-Use

| Entity | Type | Description |
|--------|------|-------------|
| `text.saj_charge_start_time` | Text | Start time Slot 1 (HH:MM) |
| `text.saj_charge_end_time` | Text | End time Slot 1 (HH:MM) |
| `number.saj_charge_day_mask` | Number | Weekdays Slot 1 (bitmask) |
| `number.saj_charge_power_percent` | Number | Charge power Slot 1 (0-100%) |
| `text.saj_charge_2_start_time` | Text | Start time Slot 2 |
| ... | ... | Slots 3-7 similar |
| `number.saj_charge_time_enable_bitmask` | Number | Master enable for all charge slots |
| `number.saj_discharge_time_enable_bitmask` | Number | Master enable for all discharge slots |

#### Day Mask Calculation

The day mask determines on which weekdays a slot is active:

```
Bit 0 (value 1)   = Monday
Bit 1 (value 2)   = Tuesday
Bit 2 (value 4)   = Wednesday
Bit 3 (value 8)   = Thursday
Bit 4 (value 16)  = Friday
Bit 5 (value 32)  = Saturday
Bit 6 (value 64)  = Sunday
```

**Calculation:**
```python
# Weekdays (Mon-Fri)
mask = 1 + 2 + 4 + 8 + 16  # = 31

# Weekend (Sat-Sun)
mask = 32 + 64  # = 96

# Every day
mask = 1 + 2 + 4 + 8 + 16 + 32 + 64  # = 127
```

### Configuration Examples

#### Example 1: Night Charging (cheap electricity)

**Scenario**: Every day from 22:00 to 06:00 at 80% power

```yaml
# Slot 1 configuration
text.saj_charge_start_time: "22:00"
text.saj_charge_end_time: "06:00"
number.saj_charge_day_mask: 127  # Every day
number.saj_charge_power_percent: 80

# Enable
number.saj_charge_time_enable_bitmask: 2  # Bit 1 = Slot 1
```

#### Example 2: Midday Charging (PV surplus)

**Scenario**: On weekends from 12:00 to 14:00 at 100% power

```yaml
# Slot 2 configuration
text.saj_charge_2_start_time: "12:00"
text.saj_charge_2_end_time: "14:00"
number.saj_charge_2_day_mask: 96  # Sat + Sun
number.saj_charge_2_power_percent: 100

# Enable (Slot 1 + Slot 2)
number.saj_charge_time_enable_bitmask: 6  # Bits 1+2 = 2+4
```

#### Example 3: Super Off-Peak (very cheap)

**Scenario**: In deep night (02:00-05:00) at maximum power

```yaml
# Slot 3 configuration
text.saj_charge_3_start_time: "02:00"
text.saj_charge_3_end_time: "05:00"
number.saj_charge_3_day_mask: 31  # Mon-Fri (weekdays)
number.saj_charge_3_power_percent: 100

# Enable
number.saj_charge_time_enable_bitmask: 14  # Slots 1+2+3
```

### AppMode

For Time-of-Use, **AppMode must be 1** (Active Mode):

- **AppMode = 1**: Time-of-Use active
- **AppMode = 3**: Passive Mode (Time-of-Use is ignored)

Entity: `sensor.saj_app_mode`

---

## 🔋 Passive Mode

### What is Passive Mode?

Passive Mode enables **direct power control** without time schedules. You specify a fixed power that the inverter maintains.

**Use cases:**
- **PV surplus control**: Charge only with PV surplus
- **Grid support**: Support the power grid
- **Dynamic tariffs**: React to electricity prices
- **Emergency modes**: Manual control in critical situations

### Entities in Passive Mode

| Entity | Type | Range | Description |
|--------|------|-------|-------------|
| `number.saj_passive_bat_charge_power` | Number | 0-1000 | Battery charge power |
| `number.saj_passive_bat_discharge_power` | Number | 0-1000 | Battery discharge power |
| `number.saj_passive_grid_charge_power` | Number | 0-1000 | Grid charge power |
| `number.saj_passive_grid_discharge_power` | Number | 0-1000 | Grid discharge power |
| `switch.saj_passive_charge_control` | Switch | On/Off | Enable passive charging |
| `switch.saj_passive_discharge_control` | Switch | On/Off | Enable passive discharging |
| `sensor.saj_app_mode` | Sensor | 0-3 | AppMode (must be 3) |

**Important:** Values are in **permille** (1000 = 100% of maximum power).

### Activation

**Step-by-step:**

1. **Set power values** (before activating!)
   ```yaml
   number.saj_passive_bat_charge_power: 800  # 80% charge power
   ```

2. **Set AppMode to 3**
   - Inverter switches to Passive Mode

3. **Activate switch**
   ```yaml
   switch.saj_passive_charge_control: on
   ```

### Examples

#### Example 1: Constant Charging at 50%

```yaml
number.saj_passive_bat_charge_power: 500  # 50%
switch.saj_passive_charge_control: on
# AppMode automatically to 3
```

#### Example 2: Battery Discharge for Grid Support

```yaml
number.saj_passive_bat_discharge_power: 700  # 70% discharge
switch.saj_passive_discharge_control: on
# AppMode = 3
```

#### Example 3: Dynamic PV Surplus Control

```yaml
# Automation: Charge only when PV surplus > 2000W
automation:
  - alias: "SAJ PV Surplus Charging"
    trigger:
      - platform: numeric_state
        entity_id: sensor.saj_pv_power
        above: 2000
    action:
      - service: number.set_value
        target:
          entity_id: number.saj_passive_bat_charge_power
        data:
          value: 800
      - service: switch.turn_on
        target:
          entity_id: switch.saj_passive_charge_control
```

---

## 🔄 Switching Between Modes

### Time-of-Use → Passive Mode

```yaml
# 1. Set AppMode to 3
# 2. Activate Passive Mode switch
# 3. Configure power values

service: number.set_value
target:
  entity_id: number.saj_app_mode
data:
  value: 3

service: switch.turn_on
target:
  entity_id: switch.saj_passive_charge_control
```

### Passive Mode → Time-of-Use

```yaml
# 1. Disable Passive Mode switch
# 2. Set AppMode to 1
# 3. Enable Time-of-Use slots

service: switch.turn_off
target:
  entity_id: switch.saj_passive_charge_control

service: number.set_value
target:
  entity_id: number.saj_app_mode
data:
  value: 1
```

---

## 📊 State of Charge Displays

### Important Monitoring Entities

| Entity | Description | Note |
|--------|-------------|------|
| `sensor.saj_battery_soc` | Battery state of charge | 0-100% |
| `sensor.saj_battery_power` | Current battery power | Positive = Charging, Negative = Discharging |
| `sensor.saj_charge_time_enable` | Active charge slots | Bitmask display |
| `sensor.saj_discharge_time_enable` | Active discharge slots | Bitmask display |
| `sensor.saj_app_mode` | Current AppMode | 1=Active, 3=Passive |

---

## ⚠️ Important Notes

### Write Guards

The integration implements **Write Guards** for critical registers:

- **0x3604/0x3605**: Direct write access is blocked
- Use entities instead (`number.saj_charge_time_enable_bitmask`)
- Or use `merge_write_register()` for developers

### Lock Management

For simultaneous write operations:
- Integration uses `_merge_locks` for 0x3604/0x3605
- Prevents race conditions
- Automatic retry logic

### Prioritization

When both modes are configured:
1. **AppMode = 3**: Passive Mode has priority
2. **AppMode = 1**: Time-of-Use is executed

---

## 🔧 Advanced Configuration

### Export Limitation (Anti-Reflux)

In addition to charging management, you can also control grid feed-in:

| Entity | Description |
|--------|-------------|
| `number.saj_export_limit_input` | Export limit in % (e.g., 500 = 50%) |
| `number.saj_anti_reflux_power_limit` | Power limit |
| `number.saj_anti_reflux_current_limit` | Current limit |

**Application:** Zero-export or dynamic grid limits

### Battery Limits

Protect battery with charge/discharge limits:

| Entity | Description |
|--------|-------------|
| `number.saj_battery_charge_power_limit` | Max charge power |
| `number.saj_battery_discharge_power_limit` | Max discharge power |
| `number.saj_battery_on_grid_discharge_depth` | Discharge depth on grid |
| `number.saj_battery_offgrid_discharge_depth` | Discharge depth off-grid |

---

## 💡 Best Practices

### For Beginners

1. **Start with Time-of-Use**
   - One simple night charging slot
   - Less complex than Passive Mode

2. **Test in summer**
   - PV production is high
   - Errors have less impact

3. **Enable monitoring**
   - `sensor.saj_battery_power` in dashboard
   - Observe trends

### For Advanced Users

1. **Combine both modes**
   - Time-of-Use as fallback
   - Passive Mode for optimizations

2. **Use automations**
   - Dynamic electricity prices (Tibber)
   - PV forecast integration
   - Weather-dependent control

3. **Use multiple slots**
   - Cover different price times
   - Weekend vs. weekday profiles

---

[← Back to Overview](README.md) | [Next: Troubleshooting →](troubleshooting.md)
