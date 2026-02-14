# Configuration

> Configuration options and settings for the SAJ H2 Modbus integration

---

## 🎛️ Basic Configuration

### Initial Setup

When adding the integration for the first time, you must fill in the following required fields:

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| **Name** | Display name in Home Assistant | SAJ | No |
| **IP Address** | IP address of the inverter | - | Yes |
| **Port** | Modbus TCP port | 502 | Yes |
| **Scan Interval** | Default update interval (seconds) | 60 | Yes |

### Finding the IP Address

You can find your inverter's IP address via:

1. **Router web interface**: Search for "SAJ" or the MAC address
2. **SAJ App**: In the network settings menu
3. **Display**: On the inverter under Network → IP
4. **Network scanner**: Tools like Fing, nmap

### Port Information

- **Default**: 502 (Modbus TCP)
- **Only change** if the inverter is configured on a different port
- Port 502 is the official Modbus TCP port

---

## ⚡ Advanced Configuration

After initial setup, you can configure additional options via **Settings** → **Devices & Services** → **SAJ H2 Modbus** → **Configure**.

### Fast Polling (10 seconds)

Enables faster updates for critical sensors.

**Affected sensors:**
- `sensor.saj_pv_power` - PV production
- `sensor.saj_battery_power` - Battery power
- `sensor.saj_battery_soc` - Battery state of charge
- `sensor.saj_grid_power` - Grid power
- `sensor.saj_total_load_power` - Total load
- `sensor.saj_inverter_power` - Inverter power

**Pros:**
- Real-time monitoring
- Faster response in automations
- Better visualization

**Cons:**
- Higher network load
- More CPU load on Home Assistant

**Recommended setting:** Enable for live dashboards

### Ultra-Fast MQTT (1 second)

Publishes data to an MQTT broker with 1-second interval.

**Configuration options:**

| Option | Description | Default |
|--------|-------------|---------|
| **Enable MQTT** | Turn MQTT publishing on/off | Off |
| **MQTT Broker** | IP/hostname of MQTT broker | - |
| **MQTT Port** | Port of MQTT broker | 1883 |
| **MQTT Topic Prefix** | Prefix for all topics | `saj_h2/inverter` |

**Topic format:**
```
{prefix}/{sensor_name}
# Example:
saj_h2/inverter/pvPower
saj_h2/inverter/batterySOC
```

**Important:** Ultra-Fast is paused during write operations to ensure data consistency.

---

## 🔋 Charging Settings

### Time-of-Use Configuration

Time-of-Use settings control when your inverter charges from the grid.

**Access via:**
1. **Settings** → **Devices & Services**
2. Open SAJ H2 Modbus integration
3. **Configure charging settings**

**Available parameters:**

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| **Charge Power Percent** | Charging power in % | 0-100 | 50 |
| **Charge Start Time** | Start time (HH:MM) | 00:00-23:59 | 22:00 |
| **Charge End Time** | End time (HH:MM) | 00:00-23:59 | 06:00 |
| **Charge Day Mask** | Weekdays (bitmask) | 0-127 | 127 |

**Day Mask calculation:**
```
Bit 0 (value 1)   = Monday
Bit 1 (value 2)   = Tuesday
Bit 2 (value 4)   = Wednesday
Bit 3 (value 8)   = Thursday
Bit 4 (value 16)  = Friday
Bit 5 (value 32)  = Saturday
Bit 6 (value 64)  = Sunday
```

### Passive Mode Settings

**Important entities:**

| Entity | Description | Range |
|--------|-------------|-------|
| `number.saj_passive_bat_charge_power` | Battery charge power | 0-1000 |
| `number.saj_passive_bat_discharge_power` | Battery discharge power | 0-1000 |
| `number.saj_passive_grid_charge_power` | Grid charge power | 0-1000 |
| `number.saj_passive_grid_discharge_power` | Grid discharge power | 0-1000 |
| `switch.saj_passive_charge_control` | Enable passive charging | On/Off |
| `switch.saj_passive_discharge_control` | Enable passive discharging | On/Off |

**Note:** Power values are in permille (1000 = 100%) of maximum inverter output.

---

## 🌐 Network Configuration

### Modbus TCP Connection

**Optimal settings:**
- **Timeout**: 10 seconds (default)
- **Retries**: 3 attempts
- **Retry delay**: 1 second

**These settings are hardcoded and cannot be changed.**

### Connection Cache

The integration uses a connection cache:
- **Cache TTL**: 60 seconds
- **Automatic reconnection** on connection loss
- **Retry logic** with exponential backoff

---

## 📊 Polling Strategy

The integration uses a 3-tier polling system:

### Tier 1: Standard (60s)
- **All sensors** are updated
- Includes all 390+ registers
- Highest data volume

### Tier 2: Fast (10s)
- Only **FAST_POLL_SENSORS**
- Live data for important metrics
- Optional, can be enabled

### Tier 3: Ultra-Fast (1s)
- Only **FAST_POLL_SENSORS**
- MQTT publishing
- Optional, only if MQTT is enabled

### Prioritization

**Write operations always have priority:**
1. Write (highest priority)
2. Ultra-Fast MQTT
3. Fast Polling
4. Standard Polling

---

## 🔄 Changing Configuration

### Changing Options Later

1. Go to **Settings** → **Devices & Services**
2. Find the SAJ H2 Modbus integration
3. Click **Configure**
4. Change the desired options
5. Click **Save**

### Reconfiguring the Integration

If you need to change the IP address or other basic settings:

1. Go to **Settings** → **Devices & Services**
2. Find the SAJ H2 Modbus integration
3. Click the menu (⋮) → **Delete**
4. Add the integration again

**Note:** All history data is retained as it's stored in the Home Assistant database.

---

## 🐛 Troubleshooting Configuration

### Issue: Changes not applied

**Solution:**
- Restart Home Assistant
- Clear browser cache
- Check if the change was saved in `config_entry`

### Issue: Fast polling not working

**Check:**
```bash
# Check logs
ha logs | grep saj_h2_modbus
```

**Possible causes:**
- Lock conflicts with write operations
- Network latency too high
- Inverter responds too slowly

### Issue: MQTT data not arriving

**Checklist:**
- [ ] Is MQTT broker reachable?
- [ ] Is port 1883 (or configured port) open?
- [ ] Is topic prefix correct?
- [ ] Is Home Assistant MQTT integration set up?

**Test:**
```bash
# Start MQTT subscriber
mosquitto_sub -h {broker_ip} -t "saj_h2/inverter/#" -v
```

---

## 📋 Configuration Examples

### Example 1: Standard Setup

```yaml
Name: SAJ
IP Address: 192.168.1.100
Port: 502
Scan Interval: 60
Fast Polling: Off
MQTT: Off
```

### Example 2: Live Monitoring Setup

```yaml
Name: SAJ Live
IP Address: 192.168.1.100
Port: 502
Scan Interval: 60
Fast Polling: On
MQTT: On
MQTT Broker: 192.168.1.10
MQTT Port: 1883
MQTT Topic Prefix: home/saj
```

### Example 3: Night Charging Setup

```yaml
# Time-of-Use settings
Charge Start Time: 22:00
Charge End Time: 06:00
Charge Day Mask: 31  # Mon-Fri
Charge Power Percent: 80
```

---

[← Back to Overview](README.md) | [Next: Sensors →](sensors.md)
