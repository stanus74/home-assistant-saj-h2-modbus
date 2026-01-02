# Home Assistant Integration Core Spec
Purpose
The SAJ H2 Modbus integration for Home Assistant aims to provide seamless control and monitoring of SAJ H2 inverters. It facilitates reading inverter data, publishing this data to Home Assistant entities, and enabling users to configure and write charge/discharge schedules back to the inverter.

### Requirement: Modbus Connection
The integration SHALL establish a connection via Modbus.

#### Scenario: Successful connection
WHEN the integration starts
THEN it connects to the inverter.

### Requirement: Data Publishing to HA
The integration SHALL publish inverter data to Home Assistant entities.

#### Scenario: Data Update
WHEN new data is read from the inverter
THEN the corresponding Home Assistant entities SHALL be updated.

### Requirement: Charge/Discharge Scheduling
The integration SHALL allow users to configure and write charge/discharge schedules to the inverter.

#### Scenario: Schedule Configuration
WHEN a user configures a charge schedule
THEN the schedule SHALL be validated and written to the inverter via Modbus.

### Requirement: MQTT Data Export (Optional)
The integration MAY publish inverter data to an MQTT broker.

#### Scenario: MQTT Publishing
WHEN MQTT is configured and enabled
THEN inverter data SHALL be published to the configured MQTT topics.