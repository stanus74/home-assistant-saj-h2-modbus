# Proposal: Optimize Communication Efficiency

## Problem
The current Modbus communication implementation lacks explicit timeouts and may have suboptimal retry delays, potentially leading to unresponsive behavior or unnecessary delays when communicating with the SAJ H2 inverter.

## Solution
1.  **Add Explicit Timeout:** Introduce a 5-second timeout for Modbus TCP connections to prevent indefinite waits.
2.  **Implement Fail-Fast Retry:** For the ultra-fast (1s) poll, if a read fails, immediately retry once. If the retry also fails, skip the update cycle. This prevents a single slow read from delaying the next poll.
3.  **Review Retry Delays:** Evaluate and potentially adjust `DEFAULT_READ_BASE_DELAY` and `DEFAULT_READ_CAP_DELAY` for optimal responsiveness.

## Implementation Plan
See `tasks.md`.