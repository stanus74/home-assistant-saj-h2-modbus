# Core Specification

### Requirement: Modbus Connection
The integration SHALL connect.

#### Scenario: Success
- WHEN starting
- THEN it connects.

### Communication Constants
The following constants are used for Modbus communication:

- DEFAULT_READ_RETRIES = 3
- DEFAULT_READ_BASE_DELAY = 0.5 seconds
- DEFAULT_READ_CAP_DELAY = 5.0 seconds
- DEFAULT_WRITE_RETRIES = 3
- DEFAULT_WRITE_BASE_DELAY = 1.0 seconds
- DEFAULT_WRITE_CAP_DELAY = 5.0 seconds
- ModbusTcpClient timeout = 5 seconds