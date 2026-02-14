# Troubleshooting

> Solutions for common issues with the SAJ H2 Modbus integration

---

## 🔍 Quick Diagnosis

Before you begin troubleshooting, gather the following information:

1. **Home Assistant Version**: Settings → Info
2. **Integration Version**: HACS → Integrations
3. **Inverter Model**: Is it a SAJ H2 or HS2?
4. **Network Connection**: Does ping to the IP work?
5. **Error Messages**: What's in the logs?

**View logs:**
```bash
ha logs follow | grep saj_h2_modbus
```

---

## ❌ Connection Problems

### Problem: "Connection refused"

**Symptoms:**
- Integration shows "Unavailable"
- Logs show "Connection refused"

**Causes & Solutions:**

1. **Wrong IP address**
   ```bash
   # Check IP address
   ping 192.168.1.100
   
   # Is port reachable?
   nc -zv 192.168.1.100 502
   ```

2. **Modbus TCP not enabled**
   - Check inverter settings
   - Modbus TCP must be enabled
   - Port 502 must be open

3. **Firewall blocking**
   - Check router firewall
   - Open port 502
   - Check VLAN configuration

### Problem: "Timeout"

**Symptoms:**
- Connection is established but no data comes
- Timeouts on Modbus queries

**Solutions:**

1. **Check network latency**
   ```bash
   ping 192.168.1.100 -c 10
   ```
   - Acceptable: < 50ms
   - Problem from: > 100ms

2. **Increase scan interval**
   - Go to integration settings
   - Increase scan interval to 120 seconds
   - Test the connection

3. **Inverter overloaded**
   - Reduce number of parallel queries
   - Temporarily disable fast polling

### Problem: "No route to host"

**Symptoms:**
- Ping doesn't work
- No network connection

**Solutions:**

1. **Check network connection**
   - Is the inverter connected to the network?
   - Check network cable
   - Test WiFi connection (if used)

2. **IP configuration**
   - Static IP recommended
   - Check DHCP leases
   - Verify IP address on inverter display

---

## 📊 Data Problems

### Problem: "Unknown" values on sensors

**Symptoms:**
- Some sensors show "unknown"
- Other sensors work normally

**Causes:**

1. **Unsupported register**
   - Your inverter model doesn't support this register
   - Check firmware version

2. **Wrong register address**
   - Check inverter register map
   - Consider firmware differences

3. **Read error**
   - Individual registers can't be read
   - Retry mechanism kicks in

**Solution:**
- Not critical if only few sensors affected
- Check logs for specific errors
- If many "Unknown": Check inverter model

### Problem: Wrong values

**Symptoms:**
- Values are obviously wrong (e.g., negative PV production)
- Units don't match

**Causes:**

1. **Wrong factor/data type**
   - Register read with wrong multiplier
   - 16-bit vs 32-bit confusion

2. **Wrong byte order**
   - Modbus Little Endian vs Big Endian
   - Firmware-specific differences

**Solution:**
- [Create GitHub Issue](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
- Specify register address and expected value
- Report inverter firmware version

### Problem: Missing sensors

**Symptoms:**
- Expected sensors not displayed
- Less than 390 entities

**Causes:**

1. **Inactive sensors**
   - Some sensors are disabled by default
   - Enable via Settings → Entities

2. **Wrong inverter model**
   - Not all sensors available for all models
   - HS2 has fewer sensors than H2

3. **Initialization not complete**
   - First start can take 2-3 minutes
   - All registers must be read once

---

## 🔋 Charge Control Problems

### Problem: Slots not activating

**Symptoms:**
- Schedule is configured but charging doesn't start
- `charge_time_enable` shows wrong values

**Checklist:**

1. **Check AppMode**
   - Must be 1 for active charging
   - Check `sensor.saj_app_mode`

2. **Check slot mask**
   - `number.saj_charge_time_enable_bitmask`
   - Correct bits set?

3. **Time format**
   - Format: HH:MM
   - Use 24-hour format

4. **Day mask**
   - `number.saj_charge_day_mask`
   - Today's day included in mask?

### Problem: Passive mode not working

**Symptoms:**
- Switches are toggled but power doesn't change

**Solutions:**

1. **Check AppMode**
   - Passive mode requires AppMode = 3
   - `sensor.saj_app_mode` must show 3

2. **Check power values**
   - `number.saj_passive_bat_charge_power`
   - Value > 0?
   - Value in permille (1000 = 100%)

3. **Switch sequence**
   ```
   1. Set power values
   2. Activate passive mode switch
   3. Set AppMode to 3
   ```

### Problem: Schedules not executing

**Symptoms:**
- Time is reached but charging doesn't start

**Causes:**

1. **Wrong day mask**
   - Today not included in mask
   - Example: Today is Monday, but mask = 126 (Tue-Sun)

2. **Overlapping schedules**
   - Multiple slots active at same time
   - Conflicts in prioritization

3. **Wrong time**
   - Check inverter time
   - Consider timezone

---

## ⚡ Performance Problems

### Problem: Slow updates

**Symptoms:**
- Sensors update only every few minutes
- UI feels sluggish

**Solutions:**

1. **Adjust scan interval**
   - Standard: 60 seconds
   - Reduce to 30 seconds (attention: higher load)

2. **Enable fast polling**
   - Only for important sensors
   - 10-second interval

3. **Optimize network**
   - Switch WiFi to LAN
   - Reduce latency
   - Check bandwidth

### Problem: High CPU load

**Symptoms:**
- Home Assistant CPU usage is high
- System responds slowly

**Solutions:**

1. **Disable fast polling**
   - Significantly reduces CPU load
   - Only enable when needed

2. **Disable MQTT**
   - If not needed
   - Reduces network and CPU load

3. **Increase scan interval**
   - 60 seconds → 120 seconds
   - Fewer Modbus queries

### Problem: MQTT delays

**Symptoms:**
- MQTT data arrives delayed
- Topics not updating

**Causes:**

1. **Broker overloaded**
   - Too many messages per second
   - Check broker logs

2. **Network problems**
   - Latency between HA and broker
   - Packet loss

3. **QoS settings**
   - Default is QoS 0
   - Switch to QoS 1 under high load

---

## 🐛 Known Issues

### Issue #1: Entities show "unavailable" after restart

**Status:** Normal
**Solution:** Wait 1-2 minutes until all registers are read

### Issue #2: Write operations take long

**Status:** Normal
**Cause:** Command queue serialization
**Solution:** None, works as designed

### Issue #3: Values briefly jump to 0

**Status:** Known
**Cause:** Lock conflicts during write operations
**Solution:** Disable ultra-fast MQTT while writing

---

## 📞 Collect Debug Information

For support requests we need:

1. **Home Assistant Logs:**
   ```bash
   ha logs | grep saj_h2_modbus > saj_logs.txt
   ```

2. **System Information:**
   - Home Assistant version
   - Integration version
   - Inverter model
   - Firmware version

3. **Network Test:**
   ```bash
   ping {inverter_ip} -c 10
   nc -zv {inverter_ip} 502
   ```

4. **Modbus test (optional):**
   ```bash
   # Install modbus client
   pip install pymodbus
   
   # Test reading register
   python -c "from pymodbus.client import ModbusTcpClient; c=ModbusTcpClient('{ip}'); c.connect(); print(c.read_holding_registers(0x100, 10).registers)"
   ```

---

## 🆘 Contact Support

If the problem persists:

1. **Create GitHub Issue:**
   - [New Issue](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues/new)
   - Attach all debug information
   - Describe problem in detail

2. **Home Assistant Forum:**
   - [Community Thread](https://community.home-assistant.io/)
   - Ask other users for help

3. **Discussions:**
   - [Q&A Section](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
   - Ask questions

---

[← Back to Overview](README.md)
