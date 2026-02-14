# Quick Start Guide

> Get your first connection to your SAJ H2 inverter in 5 minutes

---

## ✅ Prerequisites

Before you begin, make sure:

- [ ] You have a **SAJ H2 inverter** (8-10 kW)
- [ ] The inverter is reachable via **Modbus TCP**
- [ ] You know the **IP address** of the inverter
- [ ] Home Assistant is installed and running
- [ ] [HACS](https://hacs.xyz/) is installed (recommended)

---

## 🚀 Installation in 3 Steps

### Step 1: Install the Integration

**Option A: Via HACS (recommended)**
1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Search for "SAJ H2 Modbus"
4. Click "Install"
5. Restart Home Assistant

**Option B: Manual Installation**
1. Download the latest version from [GitHub Releases](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)
2. Extract the folder `custom_components/saj_h2_modbus`
3. Copy it to your Home Assistant `custom_components` directory
4. Restart Home Assistant

### Step 2: Configure the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "SAJ H2 Modbus"
4. Enter the following data:
   - **IP Address**: e.g., `192.168.1.100`
   - **Port**: `502` (default)
   - **Update interval**: `60` seconds (default)

### Step 3: Test the Connection

1. After configuration, the first sensors should appear
2. Check under **Developer Tools** → **States**
3. Search for `sensor.saj_` entities
4. If values are displayed → **Success!** 🎉

---

## 📊 First Steps

### Find Important Sensors

The most important sensors for getting started:

| Sensor | Entity ID | Meaning |
|--------|-----------|---------|
| PV Power | `sensor.saj_pv_power` | Current PV production in watts |
| Battery SOC | `sensor.saj_battery_soc` | State of charge in % |
| Battery Power | `sensor.saj_battery_power` | Charging/discharging in watts |
| Grid Power | `sensor.saj_grid_power` | Import/export in watts |
| Load Power | `sensor.saj_total_load_power` | Home consumption in watts |

### Create a Dashboard

Create a new Lovelace card:

```yaml
type: entities
title: SAJ H2 Overview
entities:
  - entity: sensor.saj_pv_power
    name: PV Production
  - entity: sensor.saj_battery_soc
    name: Battery SOC
  - entity: sensor.saj_battery_power
    name: Battery Power
  - entity: sensor.saj_grid_power
    name: Grid Power
  - entity: sensor.saj_total_load_power
    name: Home Consumption
```

---

## ⚡ Quick Configurations

### 1. Enable Fast Polling (10 seconds)

1. Go to **Settings** → **Devices & Services**
2. Find the SAJ H2 Modbus integration
3. Click **Configure**
4. Enable **Fast Polling (10s)**
5. Save

**Important sensors with fast polling:**
- PV Power
- Battery Power
- Grid Power
- Total Load Power

### 2. MQTT for Real-time Data (1 second)

If you have MQTT set up in Home Assistant:

1. Configure the MQTT broker in the integration
2. Data will be automatically published
3. Topic format: `saj_h2/inverter/{sensor_name}`

---

## 🎯 Next Steps

- [Learn about charging management →](charging.md)
- [Explore all sensors →](sensors.md)
- [Create your first automation →](advanced/automations.md)

---

## ❓ Problems?

If something doesn't work:

1. **No connection?** → Check IP address and port
2. **No sensors?** → Wait 1-2 minutes after startup
3. **Wrong values?** → Verify inverter model

[→ Go to Troubleshooting](troubleshooting.md)

---

## 📚 Further Reading

- [Detailed installation instructions](installation.md)
- [Full configuration options](configuration.md)
- [All available sensors](sensors.md)

---

[← Back to Overview](README.md)
