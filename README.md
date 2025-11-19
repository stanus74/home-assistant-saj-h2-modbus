[![hacs_badge](https://img.shields.io/badge/HACS-default-orange.svg)](https://github.com/hacs/default)[![GitHub release](https://img.shields.io/github/v/release/stanus74/home-assistant-saj-h2-modbus)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)[![GitHub All Releases](https://img.shields.io/github/downloads/stanus74/home-assistant-saj-h2-modbus/total)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)  
[![Buy Me a Coffee](https://buymeacoffee.com/assets/img/custom_images/white_img.png)](https://buymeacoffee.com/stanus74)


# SAJ H2 Inverter Modbus - A Home Assistant integration for SAJ H2 Inverters

## <span style="color:red;">New Feature added: "Charge battery with mains power", see the Features section below</span>

Integration for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from [SAJ H2-Protocol](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/saj-h2-modbus.zip)

It should work for Ampere Solar Inverter (EKD-Solar) too. They use SAJ HS2 Inverter.

## Features 

- Installation through Config Flow UI
- Over 330 registers (power, energy, temperature sensors, battery...)
- Configurable polling interval - changeable at any time
- Smart Modbus connection management - especially for AIO3 

- **New Feature:** Configure Charging Time and Power, ability to switch the working mode between **Self-Consumption** / **Time-of-Use Mode** (to charge the battery with grid power) 

## Installation

This integration is available in the HACS default repository. 

1. Open HACS 
2. Find "SAJ H2 Inverter Modbus" and click "Install."
3. Restart Home Assistant.
4. After reboot of Home-Assistant, this integration can be configured through the integration setup UI


## Configuration

1. Navigate to the "Integrations" page in your configuration, then click "Add Integration and 
select "SAJ H2 Modbus."
2. Enter the IP Address and Interval 

**Important**: don't set intervall **at least 60 seconds**

3. Optional: Setting the charge values for charging the battery from the grid >[read the instructions](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/working-mode-doc.pdf)
4. Set charging values in Home Assistant, see below

---

## Features

### 🚀 New Fast Coordinator (10s) for Live Data

* **High-frequency polling for key metrics (e.g., PV power, battery):**

  * Introduced a 10s fast coordinator 
  * Can be disabled via simple adjustment in hub.py, 
    
    Energy sensors are polled every 10 seconds: 

    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower",

This is the default setting. Can be disabled in hub.py line 27:

`FAST_POLL_DEFAULT = True # True or False`

### 🚀 Working Mode Control (Advanced Users, new since Version 2.1)

This version adds support for controlling the working mode of the inverter. This feature is intended for advanced users.
see in [CHANGELOG](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/CHANGELOG.md)


### 🚀 Export Limit Control

- **SAJ Export Limit (Input)** 
  `number.saj_export_limit_input` : Value in **percent** – e.g. `500` = 50% of inverter max power (e.g. 4000 W for 8 kW inverter)

Perfect for zero export or dynamic grid feed-in limitation.


### Configure Charging and Discharging Time and Power

#### 🚀 Custom Lovelace Card for Charging/Discharging Control

A custom Lovelace card is available to provide a user-friendly interface for controlling settings:

![SAJ H2 Charge Card](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/images/saj_h2_modbus/charge.png "SAJ H2 Charge Card")

Features:
- Easy time selection for charge start and end
- Slider for charge power percentage
- Checkbox selection for charging days (automatically calculates the day mask)
- Button to enable/disable charging

For detailed installation instructions, see [SAJ H2 Charge Card Installation](https://github.com/stanus74/saj-h2-lovelace-card)


## Additional Information

The data from the SAJ H2 inverter is transmitted to the SAJ server via a WiFi interface, AIO3.

The AIO3 may have port 502 open, allowing us to access the Modbus data. The IP address can be determined in the router. 

There are also reports of **AIO3 devices with port 502 closed**. Then you need to have an RS232-wifi or -ethernet converter.

OR reset the AIO3 and reconfigure it, **important**: it must be given **a new IP address**. Then check with a port scanner if port 502 is open

[![Buy Me a Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/stanus74)
