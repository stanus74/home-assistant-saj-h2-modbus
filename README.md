# SAJ H2 Inverter Modbus - A Home Assistant Custom Component for SAJ H2 Inverters

Home Assistant Custom Component for reading data from SAJ Inverters through Modbus TCP.

Implements SAJ H2/HS2 Inverter registers from [SAJ H2-Protocol](https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/saj-h2-modbus.zip)

It should work for Ampere Solar Inverter (EKD-Solar) too. They use SAJ HS2 Inverter.

Idea based on [home-assistant-solaredge-modbus](https://github.com/binsentsu/home-assistant-solaredge-modbus) from [@binsentsu](https://github.com/binsentsu). Modified for SAJ Inverters by [@wimb0](https://github.com/wimb0)

## Features

- Installation through Config Flow UI
- Over 60 registers (power, energy, temperature sensors)
- Configurable polling interval
- Smart Modbus connection management - especially for AIO3

## Installation

This integration should be available in the HACS default repository. Simply go to HACS and search for "SAJ H2 Inverter Modbus", click it and click "Download". Don't forget to restart Home-Assistant. After restart, this integration can be configured through the integration setup UI.

## Configuration

1. Navigate to the "Integrations" page in your configuration, then click "Add Integration" and select "SAJ H2 Modbus."
2. Enter the IP Address and Interval.


## Additional Imformation

The data from the SAJ H2 inverter is transmitted to the SAJ server via a WiFi interface, AIO3.

The AIO3 has port 502 open, allowing us to access the Modbus data. The IP address can be determined in the router.

However, the connection is not as stable and fast as with a TCP Modbus converter like the Elfin EW10. [Elfin EW10 - Hi-Flying](http://www.hi-flying.com/elfin-ew10-elfin-ew11)

I have tested with EW10a and the Connection is stable and responsive.

Therefore, the addon has functions programmed to check the connection and restore it if necessary, as well as further checking the data provided.

Connection problems are logged. This is completely normal.

Those who want to do without the eSAJ Home App or the web portal can use an RS232 to TCP converter (Elfin EW10).

However, an automation must be created in Home Assistant to send the sensor error messages.
Using the AIO3 for data collection in Home Assistant is completely sufficient.

Even controlling the battery charging times is possible in HA with the integrated Modbus module.
We will soon provide a guide on GitHub with code for this.


![SAJ](https://github.com/stanus74/home-assistant-saj-h2-modbus/raw/main/images/saj_h2_modbus/logo.png)
