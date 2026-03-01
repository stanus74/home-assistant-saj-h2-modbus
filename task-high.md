# Plan HIGH (1-3) mit Unterpunkten

## 1) Lock-Strategie konsolidieren (Parallel Reads)
- [x] Reader-Gruppen inventarisieren und aktuelle Lock-Nutzung dokumentieren
- [x] Einheitliche Lock-Policy definieren (z. B. slow/fast/ultra)
- [ ] Entscheidung fuer Semaphore-Parallelisierung treffen (Grenzwert festlegen)
- [x] Implementierung der konsistenten Locks in Reader-Aufrufen
- [ ] Regressionstest: parallele Reads unter Last, keine Deadlocks

## 2) Circuit Breaker fuer Modbus Reads
- [ ] Parameter definieren (failure_threshold, timeout, half_open)
- [ ] Circuit Breaker in `get_client()`/Read-Pfaden integrieren
- [ ] Fehlerzaehlung und Reset-Logik verifizieren
- [ ] Tests fuer OPEN -> HALF_OPEN -> CLOSED Ablauf
  - [ ] Optional: Nach erfolgreichem Reconnect einen einmaligen Read-Refresh im selben Zyklus ausloesen

## 3) MQTT Strategy Decision Caching
- [ ] Cache-Feld und Invalidation-Trigger definieren
- [ ] Strategie-Entscheidung cachen und nur bei Config-Change neu bewerten
- [ ] Logging sicherstellen (nur bei Wechsel)
- [ ] CPU-Last vorher/nachher messen
