# FAQ - Frequently Asked Questions

> Answers to the most common questions about the SAJ H2 Modbus integration

---

## 🚀 General Questions

### Q: Is this integration officially from SAJ?

**A:** No, this is an **unofficial community integration**. It was developed through reverse engineering of Modbus registers and is not authorized or supported by SAJ. Use at your own risk.

### Q: Which inverters are supported?

**A:** The integration supports:
- **SAJ H2** Inverters (8kW, 10kW)
- **SAJ HS2** Inverters
- **Ampere Solar** (EKD-Solar) - uses SAJ HS2 hardware

**Not supported:**
- Other SAJ series (R5, Sununo, etc.)
- Non-SAJ inverters

### Q: Is the usage free?

**A:** Yes, the integration is open source and free under the MIT license. There are no hidden costs or subscriptions.

### Q: Will I be locked out by updates?

**A:** No, since this is a local integration, there are no cloud dependencies. You have full control over the software.

---

## ⚙️ Technical Questions

### Q: How often is data updated?

**A:** The integration uses a 3-tier system:

| Mode | Interval | Sensors |
|------|----------|---------|
| **Standard** | 60 seconds | All 390+ sensors |
| **Fast** | 10 seconds | 6 important sensors (optional) |
| **Ultra-Fast** | 1 second | MQTT publishing (optional) |

### Q: Can I use multiple inverters?

**A:** Yes, you can install the integration multiple times:
1. First integration with IP 192.168.1.100
2. Second integration with IP 192.168.1.101
3. Each integration has its own name and entities

### Q: What happens on connection loss?

**A:** The integration has a robust reconnection mechanism:
- Automatic reconnection after connection loss
- Retry logic with exponential backoff
- Entities show "unavailable" during interruption
- After reconnection: normal updates resume

### Q: Is Modbus TCP secure?

**A:** Modbus TCP itself has no encryption. For additional security:
- Use a separate IoT VLAN
- Firewall rules for port 502
- VPN for remote access

---

## 🔋 Charging Management Questions

### Q: What's the difference between Time-of-Use and Passive Mode?

**A:**

| Feature | Time-of-Use | Passive Mode |
|---------|-------------|--------------|
| **Control** | Time-based | Direct power specification |
| **Use** | Automatic night charging | Dynamic control |
| **AppMode** | 1 (Active) | 3 (Passive) |
| **Scenario** | Cheap night rates | PV surplus, grid support |

### Q: What does "AppMode" mean?

**A:** AppMode determines the inverter's operating mode:

- **0**: Standby
- **1**: Active Mode (Time-of-Use, normal operation)
- **2**: Standby
- **3**: Passive Mode (Direct power control)

**Important:** For active charging, AppMode must be 1; for Passive Mode, AppMode must be 3.

### Q: How does Passive Mode work?

**A:** Passive mode allows direct specification of charge/discharge power:

1. **Set power**:
   - `number.saj_passive_bat_charge_power` = 800 (80%)
   
2. **Activate mode**:
   - Set AppMode to 3
   - `switch.saj_passive_charge_control` = ON

3. **Result**: Battery charges at 80% of maximum power

**Use cases:**
- Dynamic electricity price optimization
- Grid support (grid stabilization)
- PV surplus control

### Q: What's the difference between 0x3604 and 0x3605?

**A:**

| Register | Name | Function |
|----------|------|----------|
| **0x3604** | Charge Time Enable | Bitmask for charge time slots |
| **0x3605** | Discharge Time Enable | Bitmask for discharge time slots |

**Bit layout** (for both registers):
```
Bit 0: Charging/Discharging State (1 = active)
Bit 1-6: Slot 1-7 Enable (1 = enabled)
Bit 7: Reserved

Example: 0x0F = Slots 1,2,3,4 enabled
```

### Q: Why do some sensors show "unavailable"?

**A:** Possible causes:

1. **Initialization**: Wait 1-2 minutes after restart
2. **Not supported**: Your inverter doesn't support this sensor
3. **Read error**: Temporary Modbus communication problems
4. **Disabled**: Entity is disabled in Home Assistant

---

## 🔧 Configuration Questions

### Q: How do I find my inverter's IP address?

**A:** Several methods:

1. **Router web interface**: Search for "SAJ" or MAC address
2. **SAJ App**: Network settings in menu
3. **Display**: On inverter → Network → IP Address
4. **Network scanner**: Tools like Fing, nmap

### Q: What's the best scan rate?

**A:** Recommendations:

- **Standard use**: 60 seconds (default)
- **Live monitoring**: 60s Standard + 10s Fast Polling
- **Real-time data**: + 1s MQTT for selected sensors
- **Remote access/VPN**: 120 seconds (less load)

### Q: Can I disable sensors I don't need?

**A:** Yes:
1. Go to **Settings** → **Devices & Services**
2. Select the SAJ integration
3. Click **Entities**
4. Select the entity
5. Click **Settings** (gear icon)
6. Disable "Entity enabled"

---

## 📊 Data Questions

### Q: What data is saved?

**A:** All sensor data is saved in the Home Assistant database:
- Default: 10 days (recorder configuration)
- Configurable in `configuration.yaml`
- Long-term storage with InfluxDB possible

### Q: Can I export the data?

**A:** Yes, several options:

1. **Home Assistant**: Developer Tools → Statistics → Export
2. **MariaDB**: Direct database access
3. **InfluxDB**: Time series database
4. **MQTT**: Real-time export to external systems

### Q: How accurate is the data?

**A:** Accuracy depends on the sensor:

- **Voltage/Current**: ±0.1% (highly accurate)
- **Power**: ±1% (good)
- **Energy**: ±2% (accumulated values)
- **Temperatures**: ±1°C

---

## 🏠 Home Assistant Questions

### Q: Does the integration work with Home Assistant Cloud?

**A:** Yes, all features work with Home Assistant Cloud:
- Remote access to all sensors
- Alexa/Google Assistant integration
- Mobile app display

**Note:** Modbus communication remains local!

### Q: Can I use the integration in automations?

**A:** Absolutely! Examples:

```yaml
# Night charging
automation:
  - alias: "SAJ Night Charging"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.saj_charge_power_percent
        data:
          value: 80
```

[→ More automation examples](advanced/automations.md)

### Q: Is there a ready-made dashboard?

**A:** Yes, several options:

1. **Custom Lovelace Card**: [saj-h2-lovelace-card](https://github.com/stanus74/saj-h2-lovelace-card)
2. **ApexCharts**: For detailed diagrams
3. **Standard Entities Card**: Quick setup
4. **Community Dashboards**: Available in the forum

---

## 🆘 Troubleshooting

### Q: How do I debug connection problems?

**A:** Step-by-step:

1. **Test ping**:
   ```bash
   ping 192.168.1.100
   ```

2. **Test port**:
   ```bash
   nc -zv 192.168.1.100 502
   ```

3. **Check logs**:
   ```bash
   ha logs | grep saj_h2_modbus
   ```

4. **Test Modbus directly** (optional):
   ```bash
   python -c "from pymodbus.client import ModbusTcpClient; c=ModbusTcpClient('192.168.1.100'); c.connect(); print(c.read_holding_registers(0x100, 1).registers)"
   ```

[→ Detailed troubleshooting](troubleshooting.md)

### Q: Where can I find the logs?

**A:** Several ways:

1. **Terminal**:
   ```bash
   ha logs follow | grep saj_h2_modbus
   ```

2. **Home Assistant UI**:
   - Settings → System → Logs
   - Filter for "saj_h2_modbus"

3. **File** (Container/Core):
   ```
   /config/home-assistant.log
   ```

---

## 🤝 Community & Support

### Q: How can I contribute to development?

**A:** Several options:

1. **Bug Reports**: [GitHub Issues](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
2. **Feature Requests**: [Discussions](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
3. **Code**: Pull requests welcome!
4. **Documentation**: Improve the wiki
5. **Testing**: Test new versions and provide feedback

### Q: Is there a forum or chat?

**A:** Yes:
- [GitHub Discussions](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
- [Home Assistant Forum](https://community.home-assistant.io/)

### Q: Is commercial support available?

**A:** No, this is a purely community-driven project. There is no commercial support. For professional assistance, we recommend:
- Electrical contractors
- SAJ directly (for hardware problems)
- Home Assistant service providers

---

## 💡 Tips & Tricks

### Q: What are the best settings for beginners?

**A:** Recommended starting configuration:
- Scan interval: 60 seconds
- Fast polling: ON (for better UX)
- MQTT: OFF (only when needed)
- Time-of-Use: Configure one slot for night charging

### Q: How do I optimize performance?

**A:** Tips:
- Use LAN instead of WiFi
- Static IP for the inverter
- Fast polling only when needed
- Disable entities you don't need
- Home Assistant on SSD instead of SD card

### Q: What's the best way to save electricity costs?

**A:** Strategies:
1. **Time-of-Use**: Night charging with cheap electricity
2. **PV surplus**: Maximize self-consumption
3. **Dynamic tariffs**: Tibber/Awattar integration
4. **Passive Mode**: Grid support for compensation

---

Question not found? [Ask in the Discussions!](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)

[← Back to Overview](README.md)
