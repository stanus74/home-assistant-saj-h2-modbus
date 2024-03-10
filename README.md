# SAJ H2 Inverter Modbus - A Home Assistant Custom Component for SAJ H2 Inverters

Home Assistant Custom Component for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from `saj-plus-series-inverter-modbus-protocol.pdf` <upload new PDF>

Idea based on [home-assistant-solaredge-modbus](https://github.com/binsentsu/home-assistant-solaredge-modbus) from [@binsentsu](https://github.com/binsentsu). Modified for SAJ Inverters by [@wimb0](https://github.com/wimb0)

## Features

- Installation through Config Flow UI
- Separate sensor per register
- Auto applies scaling factor
- Configurable polling interval
- All Modbus registers are read within 1 read cycle for data consistency between sensors

## Installation

This integration is NOT available in the HACS default repository.

1. Copy files in a new directory `/custom_components/saj_modbus`
2. After reboot of Home-Assistant, this integration can be configured through the integration setup UI

## Configuration

1. Go to the integrations page in your configuration and click on new integration -> SAJ Modbus

Home Assistant Custom Component for reading data from SAJ Solar Inverters through Modbus over TCP. This integration should work with SAJ R5, Sununo and Suntrio inverters.
