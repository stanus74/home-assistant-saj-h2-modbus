# Installation

> Detailed installation instructions for the SAJ H2 Modbus integration

---

## 📥 Prerequisites

### Hardware
- SAJ H2 inverter (8kW or 10kW)
- Network connection to the inverter
- Home Assistant instance (OS, Container, Core, or Supervised)

### Software
- Home Assistant version 2023.x or later
- [HACS](https://hacs.xyz/) (recommended, but optional)
- Network access to port 502 (Modbus TCP)

### Network Configuration
- Static IP address for the inverter recommended
- Port 502 must be reachable
- No firewall rules blocking Modbus TCP

---

## 🔧 Installation Methods

### Method 1: HACS (Recommended)

The easiest way to install:

1. **Open HACS**
   - Go to HACS in the Home Assistant sidebar
   - Click on "Integrations"

2. **Search for the integration**
   - Click the "+" icon in the bottom right
   - Search for "SAJ H2 Modbus"

3. **Install**
   - Click on "SAJ H2 Inverter Modbus"
   - Select the latest version
   - Click "Install"

4. **Restart**
   - Restart Home Assistant
   - Wait for all services to start

### Method 2: Manual Installation

If you don't want to use HACS:

1. **Download the latest version**
   ```bash
   # Via GitHub CLI
   gh release download --repo stanus74/home-assistant-saj-h2-modbus --latest
   
   # Or manually from:
   # https://github.com/stanus74/home-assistant-saj-h2-modbus/releases
   ```

2. **Extract files**
   - Extract the archive
   - Navigate to `custom_components/saj_h2_modbus`

3. **Copy to Home Assistant**
   - Copy the folder `saj_h2_modbus` to:
     - Home Assistant OS/Supervised: `/config/custom_components/`
     - Home Assistant Container: `/config/custom_components/`
     - Home Assistant Core: `.homeassistant/custom_components/`

4. **Restart**
   - Restart Home Assistant

### Method 3: Git Clone (For Developers)

```bash
# Navigate to custom_components directory
cd /config/custom_components

# Clone repository
git clone https://github.com/stanus74/home-assistant-saj-h2-modbus.git saj_h2_modbus

# Restart Home Assistant
```

---

## ⚙️ Initial Configuration

### Step 1: Add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "SAJ H2 Modbus"
4. Click on the integration

### Step 2: Enter Connection Data

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| **Name** | Display name in Home Assistant | SAJ | My Inverter |
| **IP Address** | Inverter IP address | - | 192.168.1.100 |
| **Port** | Modbus TCP port | 502 | 502 |
| **Scan Interval** | Update interval in seconds | 60 | 60 |

### Step 3: Advanced Options (Optional)

After initial setup, you can configure additional options:

1. Go to **Settings** → **Devices & Services**
2. Find the SAJ H2 Modbus integration
3. Click **Configure**

**Available Options:**

- **Fast Polling (10s)**: Enables 10-second updates for important sensors
- **Enable MQTT**: Publishes data to an MQTT broker
- **MQTT Broker**: Address of the MQTT broker (optional)
- **MQTT Port**: Port of the MQTT broker (default: 1883)
- **MQTT Topic Prefix**: Prefix for MQTT topics

---

## ✅ Verify Installation

### 1. Check Entities

1. Go to **Developer Tools** → **States**
2. Enter `saj_` in the search field
3. Several entities should appear:
   - `sensor.saj_pv_power`
   - `sensor.saj_battery_soc`
   - `sensor.saj_grid_power`
   - And many more...

### 2. Check Logs

```bash
# View Home Assistant logs
ha logs follow | grep saj_h2_modbus
```

You should see messages like:
```
INFO (MainThread) [custom_components.saj_h2_modbus] SAJ H2 Modbus integration starting
INFO (MainThread) [custom_components.saj_h2_modbus.hub] Connected to SAJ inverter at 192.168.1.100
```

### 3. View Device

1. Go to **Settings** → **Devices & Services**
2. Click on the SAJ H2 Modbus integration
3. A device with all sensors should be displayed

---

## 🔄 Updates

### Via HACS

1. Go to HACS → Integrations
2. Find "SAJ H2 Inverter Modbus"
3. Click "Update" if available
4. Restart Home Assistant

### Manual Update

1. Download the latest version
2. Replace the folder `custom_components/saj_h2_modbus`
3. Restart Home Assistant

---

## ❌ Uninstallation

### Via HACS

1. Go to HACS → Integrations
2. Find "SAJ H2 Inverter Modbus"
3. Click the menu (⋮) → "Delete"
4. Restart Home Assistant

### Manual

1. Delete the folder `custom_components/saj_h2_modbus`
2. Restart Home Assistant

---

## 🐛 Known Installation Issues

### Issue: "Integration not found"

**Solution:**
- Clear browser cache
- Restart Home Assistant
- Check if the folder was copied correctly

### Issue: "Connection failed"

**Solution:**
- Check IP address and port
- Test ping to inverter: `ping 192.168.1.100`
- Check firewall rules
- Enable Modbus TCP on the inverter

### Issue: "No entities displayed"

**Solution:**
- Wait 2-3 minutes (first query takes longer)
- Check logs for error messages
- Verify inverter model (only H2/HS2 supported)

---

## 📞 Support

For installation problems:
- [Create GitHub Issue](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
- [Home Assistant Forum](https://community.home-assistant.io/)
- [Troubleshooting Guide →](troubleshooting.md)

---

[← Back to Overview](README.md)
