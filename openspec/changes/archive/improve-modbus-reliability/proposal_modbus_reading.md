# Proposal: Enhance Modbus Register Reading Robustness

## 1. Introduction
This proposal addresses critical issues identified in the Modbus Register Reading (Data Ingestion) component of the SAJ H2 Modbus integration. The primary goal is to significantly improve the reliability and data integrity of Modbus communication by tackling data loss, lock contention, and connection management.

## 2. Background
The current implementation of Modbus register reading faces challenges that can lead to data inaccuracies and operational instability. Specifically, the handling of errors during data acquisition, the management of concurrent read operations, and the robustness of connection retries are areas requiring immediate attention. This proposal is informed by the analysis prompt for Area 1 in the `openspec/project.md` document.

## 3. Problem Statement
The current Modbus reading mechanism exhibits the following critical issues:
- **Data Loss on Error**: The `_read_modbus_data()` function returns an empty dictionary (`{}`) upon encountering any error, leading to potential data loss for sensors that rely on this data.
- **Lock Contention**: The use of three distinct locks (`_slow_lock`, `_fast_lock`, `_ultra_fast_lock`) for different polling levels may lead to contention, impacting performance and potentially causing deadlocks.
- **Suboptimal Retry & Reconnection**: The current retry logic and connection cache TTL might not be sufficiently robust for intermittent network issues or inverter unavailability.
- **Register Mapping & Decoding Accuracy**: Potential inaccuracies in register addresses or data decoding can lead to incorrect sensor values.

## 4. Proposed Solution

### 4.1. Implement Partial-Data Recovery
- **Objective**: Prevent data loss by ensuring that even if an error occurs during a read operation, previously known valid data for unaffected registers is retained.
- **Approach**: Modify the `_read_modbus_data()` function to distinguish between complete read failures and partial failures. If a read operation for a subset of registers fails, the function should return the successfully read data along with an indicator of the failed subset, rather than an empty dictionary. This will require changes in how data is processed and stored.

### 4.2. Optimize Lock Strategies
- **Objective**: Mitigate lock contention and ensure efficient concurrent access to Modbus resources.
- **Approach**:
    - Analyze the current lock usage and identify specific points of contention.
    - Evaluate if a single, more granular lock or a different synchronization mechanism would be more appropriate.
    - Consider the interaction between the different polling levels (`_slow_lock`, `_fast_lock`, `_ultra_fast_lock`) and refactor if necessary to reduce blocking.

### 4.3. Enhance Retry & Reconnection Logic
- **Objective**: Improve the resilience of Modbus connections against transient network issues and inverter unresponsiveness.
- **Approach**:
    - Review and potentially adjust the exponential backoff values for retries to better suit typical network conditions.
    - Re-evaluate the Connection Cache TTL (currently 60s) to ensure it balances performance with responsiveness to connection changes.
    - Implement more sophisticated connection health checks.

### 4.4. Verify Register Mapping & Decoding
- **Objective**: Ensure the accuracy of all Modbus register addresses and the correctness of data decoding.
- **Approach**:
    - Cross-reference all 330+ register addresses against the inverter's Modbus documentation.
    - Thoroughly test and validate the decoding logic for BCD time, scaling factors, and bit masks.

## 5. Technical Guardrails
This proposal aligns with the project's technical guardrails:
- **Partial-Data Recovery**: Directly addressed by section 4.1.
- **Lock-Contention Avoidance**: Directly addressed by section 4.2.
- **Write Verification**: While this proposal focuses on reading, the principles of robust data handling are maintained.

## 6. Analysis Prompt Reference
This proposal is based on the analysis prompt for Area 1 in `openspec/project.md`.

## 7. Next Steps
- Review and approval of this proposal.
- Implementation of the proposed changes in `modbus_readers.py` and related files.
- Comprehensive testing to validate the improvements.
