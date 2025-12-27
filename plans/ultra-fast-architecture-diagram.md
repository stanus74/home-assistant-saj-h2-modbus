# Ultra Fast Mode Architecture Diagrams

## Current Architecture

```mermaid
graph TB
    subgraph Home Assistant
        HA[Home Assistant Core]
    end
    
    subgraph SAJ Hub
        Hub[SAJModbusHub]
        
        subgraph Polling Loops
            UltraFast[Ultra Fast Loop - 1s]
            Fast[Fast Loop - 10s]
            Slow[Slow Loop - 60s]
        end
        
        subgraph Locks
            ReadLock[_read_lock]
            ConnLock[_connection_lock]
        end
        
        subgraph Data
            InverterData[inverter_data dict]
            StaticData[_inverter_static_data]
        end
    end
    
    subgraph Modbus
        Client[ModbusTcpClient]
        Inverter[SAJ Inverter]
    end
    
    subgraph MQTT
        Publisher[MqttPublisher]
        Broker[MQTT Broker]
    end
    
    UltraFast -->|Every 1s| Hub
    Fast -->|Every 10s| Hub
    Slow -->|Every 60s| Hub
    
    Hub -->|Acquire| ConnLock
    Hub -->|Acquire| ReadLock
    
    Hub -->|get_client| Client
    Client -->|TCP| Inverter
    
    Hub -->|update| InverterData
    Hub -->|publish| Publisher
    Publisher -->|MQTT| Broker
    
    style UltraFast fill:#ff6b6b
    style Fast fill:#feca57
    style Slow fill:#48dbfb
    style ReadLock fill:#ff9ff3
    style ConnLock fill:#ff9ff3
```

## Performance Bottleneck Visualization

```mermaid
graph LR
    subgraph Ultra Fast Loop 1s
        A[Start] --> B[get_client]
        B --> C{Acquire ConnLock}
        C -->|Wait| D[Check Connected]
        D --> E[Return Client]
        E --> F[Read Registers]
        F -->|Acquire ReadLock| G{Wait for Lock}
        G -->|Blocked by Fast/Slow| H[Delay]
        H --> I[Read 25 Registers]
        I --> J[Decode 18 Values]
        J --> K[Filter to Fast Sensors]
        K --> L[Update inverter_data]
        L --> M[Publish to MQTT]
        M --> N[End]
    end
    
    style C fill:#ff6b6b
    style G fill:#ff6b6b
    style H fill:#ff6b6b
```

## Optimized Architecture

```mermaid
graph TB
    subgraph Home Assistant
        HA[Home Assistant Core]
    end
    
    subgraph SAJ Hub Optimized
        Hub[SAJModbusHub]
        
        subgraph Polling Loops
            UltraFast[Ultra Fast Loop - 1s]
            Fast[Fast Loop - 10s]
            Slow[Slow Loop - 60s]
        end
        
        subgraph Optimized Locks
            UltraLock[_ultra_fast_read_lock]
            FastLock[_fast_read_lock]
            SlowLock[_slow_read_lock]
        end
        
        subgraph Caching Layer
            ValueCache[_value_cache TTL=5s]
            ClientCache[_cached_client TTL=60s]
        end
        
        subgraph Data
            InverterData[inverter_data dict]
            StaticData[_inverter_static_data]
            LastValues[_last_published_values]
        end
    end
    
    subgraph Modbus
        Client[ModbusTcpClient]
        Inverter[SAJ Inverter]
    end
    
    subgraph MQTT
        Publisher[MqttPublisher Batched]
        Broker[MQTT Broker]
    end
    
    UltraFast -->|Every 1s| Hub
    Fast -->|Every 10s| Hub
    Slow -->|Every 60s| Hub
    
    Hub -->|Check Cache| ClientCache
    ClientCache -->|Valid| Hub
    ClientCache -->|Expired| Client
    
    Hub -->|Acquire| UltraLock
    Fast -->|Acquire| FastLock
    Slow -->|Acquire| SlowLock
    
    Hub -->|get_client| Client
    Client -->|TCP| Inverter
    
    Hub -->|Check Cache| ValueCache
    ValueCache -->|Hit| Hub
    ValueCache -->|Miss| Hub
    
    Hub -->|update| InverterData
    Hub -->|compare| LastValues
    Hub -->|publish delta| Publisher
    Publisher -->|Batch MQTT| Broker
    
    style UltraFast fill:#ff6b6b
    style Fast fill:#feca57
    style Slow fill:#48dbfb
    style UltraLock fill:#54a0ff
    style FastLock fill:#54a0ff
    style SlowLock fill:#54a0ff
    style ValueCache fill:#1dd1a1
    style ClientCache fill:#1dd1a1
```

## Optimization Flow Diagram

```mermaid
flowchart TD
    Start([Ultra Fast Update Triggered]) --> CheckCache{Check Value Cache}
    
    CheckCache -->|Cache Hit| GetCached[Get Cached Value]
    CheckCache -->|Cache Miss| GetClient[Get Modbus Client]
    
    GetCached --> Compare{Compare with Last Value}
    GetClient --> ReadLock[Acquire Ultra Fast Lock]
    
    ReadLock --> ReadRegs[Read 25 Registers]
    ReadRegs --> Decode[Decode 18 Values]
    Decode --> UpdateCache[Update Value Cache]
    UpdateCache --> Compare
    
    Compare -->|No Change| SkipUpdate[Skip Update]
    Compare -->|Changed| UpdateData[Update inverter_data]
    
    UpdateData --> CalcDelta[Calculate Delta]
    CalcDelta --> HasDelta{Any Changes?}
    
    HasDelta -->|No| SkipPublish[Skip MQTT Publish]
    HasDelta -->|Yes| BatchMQTT[Add to Batch]
    
    BatchMQTT --> CheckBatch{Batch Full or Timeout?}
    CheckBatch -->|No| End([End])
    CheckBatch -->|Yes| Publish[Publish Batch to MQTT]
    
    SkipUpdate --> End
    SkipPublish --> End
    Publish --> End
    
    style CheckCache fill:#1dd1a1
    style GetCached fill:#1dd1a1
    style Compare fill:#1dd1a1
    style SkipUpdate fill:#1dd1a1
    style SkipPublish fill:#1dd1a1
    style ReadLock fill:#54a0ff
    style BatchMQTT fill:#feca57
```

## Resource Usage Comparison

```mermaid
graph TB
    subgraph Current Implementation
        C1[Lock Acquisitions: 3/s]
        C2[Connection Checks: 1/s]
        C3[Register Reads: 25/s]
        C4[MQTT Messages: 18/s]
        C5[CPU Usage: HIGH]
    end
    
    subgraph Optimized Implementation
        O1[Lock Acquisitions: 1/s]
        O2[Connection Checks: 1/60s]
        O3[Register Reads: 5-10/s]
        O4[MQTT Messages: 3-5/s]
        O5[CPU Usage: LOW]
    end
    
    C1 -.->|67% reduction| O1
    C2 -.->|98% reduction| O2
    C3 -.->|60-80% reduction| O3
    C4 -.->|70-85% reduction| O4
    C5 -.->|60-80% reduction| O5
    
    style C1 fill:#ff6b6b
    style C2 fill:#ff6b6b
    style C3 fill:#ff6b6b
    style C4 fill:#ff6b6b
    style C5 fill:#ff6b6b
    style O1 fill:#1dd1a1
    style O2 fill:#1dd1a1
    style O3 fill:#1dd1a1
    style O4 fill:#1dd1a1
    style O5 fill:#1dd1a1
```

## Implementation Timeline

```mermaid
gantt
    title Ultra Fast Mode Optimization Timeline
    dateFormat  YYYY-MM-DD
    section Phase 1: Quick Wins
    Lock Optimization           :a1, 2024-01-01, 2d
    Data Caching with TTL     :a2, after a1, 2d
    Delta Updates for MQTT    :a3, after a2, 1d
    
    section Phase 2: Medium Effort
    Connection Pooling        :b1, after a3, 3d
    Batch MQTT Publishing     :b2, after b1, 2d
    
    section Phase 3: Advanced
    Selective Register Fetching :c1, after b2, 4d
    Lazy Loading               :c2, after c1, 3d
    
    section Testing
    Performance Testing        :t1, after c2, 3d
    Integration Testing        :t2, after t1, 2d
```
