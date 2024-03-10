# SAJ H2 Inverter Modbus - A Home Assistant custom component for SAJ H2 Inverters
Home assistant Custom Component for reading data from SAJ Inverters through modbus TCP.

Implements SAJ H2/HS2 Inverter registers from saj-plus-series-inverter-modbus-protocal.pdf. > neues PDF hochloaden

Idea based on home-assistant-solaredge-modbus from @binsentsu. Modified for SAJ Inverters from @wimb0

##Features

* Installation through Config Flow UI.
* Separate sensor per register
* Auto applies scaling factor
* Configurable polling interval
* All modbus registers are read within 1 read cycle for data consistency between sensors.

##Configuration
Go to the integrations page in your configuration and click on new integration -> SAJ Modbus

Home Assistant Custom Component for reading data from SAJ Solar Inverters through modbus over TCP. This integration should work with SAJ R5, Sununo and Suntrio inverters.

##Installation

This integration is NOT available in the HACS default repository.

copy Files in a new Diretory /saj-modbus

After reboot of Home-Assistant, this integration can be configured through the integration setup UI
