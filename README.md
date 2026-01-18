[![hacs_badge](https://img.shields.io/badge/HACS-default-orange.svg)](https://github.com/hacs/default)[![GitHub release](https://img.shields.io/github/v/release/stanus74/home-assistant-saj-h2-modbus)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)[![GitHub All Releases](https://img.shields.io/github/downloads/stanus74/home-assistant-saj-h2-modbus/total)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)  
[![Buy Me a Coffee](https://buymeacoffee.com/assets/img/custom_images/white_img.png)](https://buymeacoffee.com/stanus74)


# SAJ H2 Inverter Modbus - A Home Assistant integration for SAJ H2 Inverters

> **Disclaimer / Important Notice**
>
> This Home Assistant integration is an **unofficial community project** and is **not affiliated with or endorsed by SAJ**.
>
> The Modbus register addresses and sensor mappings used in this integration were  
> **independently determined through empirical testing and publicly available information**.  
> No confidential documents, proprietary materials, or NDA-protected data have been included or published.
>
> The register mappings in the source code are provided **solely for interoperability purposes**  
> and are **not based on any official SAJ documentation**.  
> Users install and use this integration **at their own risk**.


Integration for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from [SAJ H2-Protocol](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/saj-h2-modbus.zip)

It should work for Ampere Solar Inverter (EKD-Solar) too. They use SAJ HS2 Inverter.

## Features 

- Installation through Config Flow UI
- Over 390 registers (power, energy, temperature sensors, battery...)
- Configurable polling interval - changeable at any time, with real-time sensors adjustable at 10-second intervals or **even 1-second intervals** (via MQTT)

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

3. Optional: Setting the charge values for charging the battery from the grid >[read the instructions](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/working-mode-doc.pdf)
4. Set charging values in Home Assistant, see below

---

## Features

### 🚀 New Fast Coordinator (10s) for Live Data

* **High-frequency polling for key metrics (e.g., PV power, battery):**

  * Introduced a 10s fast coordinator 
    Energy sensors are polled every 10 seconds: 

    "TotalLoadPower", "pvPower", "batteryPower", "totalgridPower",
    "inverterPower", "gridPower",

You can be enabled/disable in Configuration Settings every time


### 🚀 Charging/Discharging Control

> **⚠️ Warning: Write Registers**
>
> This integration exposes input entities that write directly to Modbus registers.  
> These commands change inverter behaviour in real time.
>
> Incorrect values can cause:
> - wrong battery charging/discharging
> - wrong export limit / grid behaviour
> - inverter protection mode activation
>
> Use write functions carefully.  
> The developer is not liable for any issues arising from user-applied register writes.

### ⚡ SAJ Inverter – Passive Mode 

Passive Mode allows you to charge or discharge your battery at a fixed power level – for example, during low electricity rates or for grid support.

Learn more: https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions/105

**How it works:**

1. **Set the power level** (0–1000, where 1000 = 100%):
   - `number.saj_passive_bat_charge_power` – Battery charge power
   - `number.saj_passive_bat_discharge_power` – Battery discharge power

2. **Activate the mode** via Switch:
   - `switch.saj_passive_charge_control` (ON = Charge / OFF = Off)
   - `switch.saj_passive_discharge_control` (ON = Discharge / OFF = Off)

**Important** for Power Settings
https://github.com/stanus74/home-assistant-saj-h2-modbus/issues/141

That's it – the inverter handles the rest automatically.

### 🚀 Export Limit Control

- **SAJ Export Limit (Input)** 
  `number.saj_export_limit_input` : Value in **percent** – e.g. `500` = 50% of inverter max power (e.g. 4000 W for 8 kW inverter)

Perfect for zero export or dynamic grid feed-in limitation. 
**Important**: This applies to PV power surplus that is fed into the public grid.


### Configure Charging and Discharging Time and Power (Time-of-Use Mode)

#### 🚀 Custom Lovelace Card for Charging/Discharging Control

A custom Lovelace card is available to provide a user-friendly interface for controlling settings:

![SAJ H2 Charge Card](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/images/saj_h2_modbus/charge.png "SAJ H2 Charge Card")

Features:
- Easy time selection for charge start and end
- Slider for charge power percentage
- Checkbox selection for charging days 
- Button to enable/disable charging



For detailed installation instructions, see [SAJ H2 Charge Card Installation](https://github.com/stanus74/saj-h2-lovelace-card)





[![Buy Me a Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/stanus74)
