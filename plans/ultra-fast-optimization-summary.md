# Ultra Fast Mode Optimization Summary

## Quick Reference

### Current State
- **Polling Interval**: 1 second
- **Registers Read**: 25 registers per poll
- **Sensors Monitored**: 18 power-related sensors
- **Lock Strategy**: Single shared lock for all operations
- **MQTT Strategy**: Publish all values every second

### Key Bottlenecks

| # | Bottleneck | Impact | Root Cause |
|---|------------|--------|------------|
| 1 | Lock Contention | HIGH | Single `_read_lock` shared across 1s, 10s, and 60s loops |
| 2 | No Change Detection | HIGH | Reads all registers every second regardless of changes |
| 3 | No Caching | HIGH | Same values decoded every second |
| 4 | Connection Overhead | MEDIUM | Connection check every 1s with lock acquisition |
| 5 | MQTT Overhead | MEDIUM | 18 messages per second, no batching |
| 6 | Full Dict Update | LOW | Updates entire dictionary every second |

### Optimization Recommendations

#### Phase 1: Quick Wins (Low Complexity, High Impact)

**1. Lock Optimization**
```python
# Separate locks for different polling intervals
self._ultra_fast_read_lock = asyncio.Lock()  # For 1s polling
self._fast_read_lock = asyncio.Lock()        # For 10s polling
self._slow_read_lock = asyncio.Lock()        # For 60s polling
```
- **Impact**: 20-40% reduction in lock contention
- **Complexity**: LOW
- **Risk**: LOW

**2. Data Caching with TTL**
```python
# Cache decoded values with 5-second TTL
self._value_cache: Dict[str, CachedValue] = {}
self._cache_ttl = 5.0
```
- **Impact**: 40-60% reduction in unnecessary updates
- **Complexity**: LOW
- **Risk**: LOW

**3. Delta Updates for MQTT**
```python
# Only publish changed values
self._last_published_values: Dict[str, Any] = {}
delta_data = {k: v for k, v in fast_data.items() 
              if self._last_published_values.get(k) != v}
```
- **Impact**: 20-30% reduction in MQTT messages
- **Complexity**: LOW
- **Risk**: LOW

#### Phase 2: Medium Effort (Medium Complexity, Medium Impact)

**4. Connection Pooling**
```python
# Cache client for 60 seconds
self._cached_client = None
self._cache_expiry = 0.0
self._cache_ttl = 60.0
```
- **Impact**: 10-20% reduction in connection overhead
- **Complexity**: MEDIUM
- **Risk**: LOW

**5. Batch MQTT Publishing**
```python
# Accumulate messages and publish in batches
self._pending_messages: Dict[str, str] = {}
self._batch_size = 10
self._batch_timeout = 2.0
```
- **Impact**: 15-25% reduction in MQTT overhead
- **Complexity**: MEDIUM
- **Risk**: LOW

#### Phase 3: Advanced (High Complexity, High Impact)

**6. Selective Register Fetching**
```python
# Adaptive polling based on value changes
self._consecutive_unchanged_reads: int = 0
self._adaptive_poll_interval: float = 1.0
```
- **Impact**: 30-50% reduction in unnecessary updates
- **Complexity**: MEDIUM
- **Risk**: MEDIUM

**7. Lazy Loading**
```python
# Decode values only when accessed
class LazyDecodedValue:
    def __init__(self, raw_value: int, decoder: Callable):
        self._raw_value = raw_value
        self._decoder = decoder
```
- **Impact**: 10-15% reduction in CPU usage
- **Complexity**: HIGH
- **Risk**: MEDIUM

### Expected Combined Impact

| Metric | Current | Optimized | Improvement |
|--------|---------|-----------|-------------|
| Lock Acquisitions | 3/s | 1/s | 67% reduction |
| Connection Checks | 1/s | 1/60s | 98% reduction |
| Register Reads | 25/s | 5-10/s | 60-80% reduction |
| MQTT Messages | 18/s | 3-5/s | 70-85% reduction |
| CPU Usage | HIGH | LOW | 60-80% reduction |

### Implementation Checklist

- [ ] Phase 1: Lock Optimization
  - [ ] Add separate locks for ultra fast, fast, and slow polling
  - [ ] Update `_async_update_fast` to use appropriate lock
  - [ ] Update `_run_reader_methods` to use appropriate lock
  - [ ] Test with all polling intervals active

- [ ] Phase 1: Data Caching
  - [ ] Implement `CachedValue` class with TTL
  - [ ] Add `_value_cache` dictionary to hub
  - [ ] Implement `_get_cached_value` and `_set_cached_value` methods
  - [ ] Update `_async_update_fast` to use cache
  - [ ] Test cache invalidation

- [ ] Phase 1: Delta Updates
  - [ ] Add `_last_published_values` dictionary to hub
  - [ ] Implement delta calculation in `_async_update_fast`
  - [ ] Only publish changed values to MQTT
  - [ ] Test delta detection

- [ ] Phase 2: Connection Pooling
  - [ ] Add client caching to `ModbusConnectionManager`
  - [ ] Implement `_cache_expiry` and `_cache_ttl`
  - [ ] Update `get_client` to use cached client
  - [ ] Add connection health monitoring
  - [ ] Test connection reuse

- [ ] Phase 2: Batch MQTT Publishing
  - [ ] Add `_pending_messages` dictionary to `MqttPublisher`
  - [ ] Implement `_flush_pending_messages` method
  - [ ] Add batch size and timeout configuration
  - [ ] Update `publish_data` to use batching
  - [ ] Test batch publishing

- [ ] Phase 3: Selective Register Fetching
  - [ ] Implement change detection logic
  - [ ] Add adaptive polling interval
  - [ ] Implement `_detect_changes` method
  - [ ] Update `_async_update_fast` to skip unchanged reads
  - [ ] Test adaptive polling

- [ ] Phase 3: Lazy Loading
  - [ ] Implement `LazyDecodedValue` class
  - [ ] Update `_read_modbus_data` to return lazy values
  - [ ] Update all reader functions to use lazy decoding
  - [ ] Test lazy decoding

### Testing Strategy

1. **Baseline Measurement**
   - Measure current CPU usage
   - Measure current memory usage
   - Measure current network I/O
   - Measure current MQTT message rate

2. **Phase Testing**
   - Test each optimization independently
   - Measure impact of each optimization
   - Verify data accuracy
   - Check for regressions

3. **Integration Testing**
   - Test all optimizations together
   - Test with all polling intervals active
   - Test under load
   - Test error handling

4. **Performance Validation**
   - Compare with baseline
   - Verify expected improvements
   - Check for unexpected side effects

### Configuration Options

Consider adding these configuration options:

```yaml
# config_flow.py
CONF_CACHE_TTL = "cache_ttl"
CONF_BATCH_SIZE = "mqtt_batch_size"
CONF_BATCH_TIMEOUT = "mqtt_batch_timeout"
CONF_ADAPTIVE_POLLING = "adaptive_polling"
CONF_CHANGE_THRESHOLD = "change_threshold"
```

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Cache staleness | Configurable TTL, force refresh option |
| Lock deadlocks | Use asyncio.Lock (no deadlocks), timeout protection |
| Data loss | Maintain fallback to original behavior |
| Increased memory | Cache size limits, LRU eviction |
| Complexity | Incremental implementation, thorough testing |

### Rollback Plan

If issues arise:
1. Disable specific optimizations via configuration
2. Revert to original implementation
3. Maintain feature flags for each optimization

### Next Steps

1. Review this analysis with the team
2. Prioritize optimizations based on impact/complexity
3. Create implementation tasks for each phase
4. Set up performance monitoring
5. Begin Phase 1 implementation
