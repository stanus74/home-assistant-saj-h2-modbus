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


## Additional Information

The data from the SAJ H2 inverter is transmitted to the SAJ server via a WiFi interface, AIO3.

The AIO3 may have port 502 open, allowing us to access the Modbus data. The IP address can be determined in the router. There are also reports of AIO3 devices with port 502 closed. Then you need to have an RS232-wifi or -ethernet converter, see below.

Also, the connection is not as stable and fast as with a TCP Modbus converter like the [Elfin EW10 - Hi-Flying](http://www.hi-flying.com/elfin-ew10-elfin-ew11) or the [Waveshare RS232/485 to ethernet](https://www.waveshare.com/RS232-485-TO-ETH.htm).

I have tested with EW10a and the Connection is stable and responsive.

Therefore, the addon has functions programmed to check the connection and restore it if necessary, as well as further checking the data provided.

Connection problems are logged. This is completely normal.

Those who want to do without the eSAJ Home App or the web portal can use an RS232 to TCP converter, like the Elfin EW10 (wifi) or the Waveshare RS232/RS485 to Ethernet converter.

However, an automation must be created in Home Assistant to send the sensor error messages.
Using the AIO3 for data collection in Home Assistant is completely sufficient.

Even controlling the battery charging times is possible in HA with the integrated Modbus module.
We will soon provide a guide on GitHub with code for this.

## Cable layout

Connecting to the H2/HS2 can be done through the connector of the left side of the inverter, marked "4G/WIFI". This looks like a regular USB-connector, but it is not! It is an RS-232 port with power supply. Connection is as follows:

```
+-------------+
|#############|
| "" "" "" "" |
+-------------+
 Vcc tx rx GND
 
 Vcc: about 7 volt power supply
 tx: serial transmission, 115200 bps (no parity, 8 bits, 1 stop bit)
 rx: serial reception, 115200 bps (no parity, 8 bits, 1 stop bit)
 GND: ground
```
The serial transmission runs at 0-6v so be careful if you connect a micro controller or another device that has 3.3v or 5v restrictions. RS-232 asks you to connect tx to the Elfin or Waveshare rx and vice versa.

### Connections
For the Elfin: connect tx to RJ-45 pin 6 (RXD) of the EW10, connect rx to pin 5 (TXD). Connect VCC to pin 7 and GND to pin 8.

For the Waveshare or any other device that has a regular DE-9 male connector: connect tx to pin 2 (RxD) and tx to pin 3 (RxD), connect GND to pin 5. You can power the Waveshare from the inverter, but it's probably cleaner to not connect Vcc and use the supplied power adapter.

Set the Waveshare RS232 settings to 115200 8N1, flow mode NONE, packet time none, work mode TCP Server / ModbusTCP. You can choose any port number you like - enter this port number in the configuration of the integration. I left it at 23. It is possible to use port 502 but then you must renumber the RS485 port in the Waveshare web interface - they cannot both use the same port.

![SAJ](https://github.com/stanus74/home-assistant-saj-h2-modbus/raw/main/images/saj_h2_modbus/logo.png)
