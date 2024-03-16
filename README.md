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
4. Find "SAJ H2 Inverter Modbus", click and go to download.
5. Restart Home Assistant.
6. After reboot of Home-Assistant, this integration can be configured through the integration setup UI

## Configuration

1. Navigate to the "Integrations" page in your configuration, then click "Add Integration" and select "SAJ H2 Modbus."
2. Enter the IP Address and Interval.


## Additional Imformation

The data from the SAJ H2 inverter is transmitted to the SAJ server via a WiFi interface, AIO3.

The AIO3 has port 502 open, allowing us to access the Modbus data. The IP address can be determined in the router.

However, the connection is not as stable and fast as with a TCP Modbus converter like the Elfin EW10. [Elfin EW10 - Hi-Flying](http://www.hi-flying.com/elfin-ew10-elfin-ew11)

I have tested with EW10 and the Connection is stable and responsive.

Therefore, the addon has functions programmed to check the connection and restore it if necessary, as well as further checking the data provided.

Connection problems are logged. This is completely normal.

Those who want to do without the eSAJ Home App or the web portal can use an RS232 to TCP converter (Elfin EW10).

However, an automation must be created in Home Assistant to send the sensor error messages.
Using the AIO3 for data collection in Home Assistant is completely sufficient.

Even controlling the battery charging times is possible in HA with the integrated Modbus module.
We will soon provide a guide on GitHub with code for this.


![SAJ](https://github.com/stanus74/home-assistant-saj-h2-modbus/raw/main/images/saj_h2_modbus/logo.png)
