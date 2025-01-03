[![hacs_badge](https://img.shields.io/badge/HACS-default-orange.svg)](https://github.com/hacs/default)[![GitHub release](https://img.shields.io/github/v/release/stanus74/home-assistant-saj-h2-modbus)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)[![GitHub All Releases](https://img.shields.io/github/downloads/stanus74/home-assistant-saj-h2-modbus/total)](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases)  
[![Buy Me a Coffee](https://buymeacoffee.com/assets/img/custom_images/white_img.png)](https://buymeacoffee.com/stanus74)


# SAJ H2 Inverter Modbus - A Home Assistant integration for SAJ H2 Inverters

Integration for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from [SAJ H2-Protocol](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/saj-h2-modbus.zip)

It should work for Ampere Solar Inverter (EKD-Solar) too. They use SAJ HS2 Inverter.

## Features

- Installation through Config Flow UI
- Over 120 registers (power, energy, temperature sensors, ...)
- Configurable polling interval - changeable at any time
- Smart Modbus connection management - especially for AIO3

## Installation

This integration should be available in the HACS default repository. Simply go to HACS and search for "SAJ H2 Inverter Modbus", click it and click "Download". Don't forget to restart Home-Assistant. After restart, this integration can be configured through the integration setup UI.

## Configuration

1. Navigate to the "Integrations" page in your configuration, then click "Add Integration" and select "SAJ H2 Modbus."
2. Enter the IP Address and Interval.


## Additional Information

The data from the SAJ H2 inverter is transmitted to the SAJ server via a WiFi interface, AIO3.

The AIO3 may have port 502 open, allowing us to access the Modbus data. The IP address can be determined in the router. 

There are also reports of AIO3 devices with port 502 closed. Then you need to have an RS232-wifi or -ethernet converter.



[![Buy Me a Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/stanus74)
