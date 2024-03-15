# SAJ H2 Inverter Modbus - A Home Assistant Custom Component for SAJ H2 Inverters

Home Assistant Custom Component for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from [SAJ H2-Protocol](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/H2-3~6K-S2%20single%20phase%20communication%20protocol%20-2022.12.02-EN.pdf)

Idea based on [home-assistant-solaredge-modbus](https://github.com/binsentsu/home-assistant-solaredge-modbus) from [@binsentsu](https://github.com/binsentsu). Modified for SAJ Inverters by [@wimb0](https://github.com/wimb0)

## Features

- Installation through Config Flow UI
- Separate sensor per register
- Auto applies scaling factor
- Configurable polling interval
- All Modbus registers are read within 1 read cycle for data consistency between sensors

## Installation

This integration is NOT available in the HACS default repository.

1. Open HACS and click the three dots in the top right corner.
2. Select "Custom repositories," then enter the GitHub URL.
3. Choose "Integration" and click "Add."
4. Find "SAJ H2 Inverter Modbus" and click "Install."
5. Restart Home Assistant.
6. After reboot of Home-Assistant, this integration can be configured through the integration setup UI

## Configuration

1. Navigate to the "Integrations" page in your configuration, then click "Add Integration" and select "SAJ H2 Modbus."
2. Enter the IP Address and Interval.
