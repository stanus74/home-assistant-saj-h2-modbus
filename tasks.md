# Aufgabenliste SAJ H2 Modbus Optimierung (sync MRZ)

## 🔴 P0 – sofort

- [x] Race Condition: `self.inverter_data` Updates (Slow/Fast/Ultra mit Lock)
- [x] Race Condition: `_fast_listeners` Iteration/Mutation absichern
- [x] `ReconnectionNeededError` in `_async_update_fast` korrekt behandeln (re-raise + reconnect)
- [x] Paho MQTT Publishing via Circuit Breaker absichern

- [x] Stale Client Reference / Cache-Race in `services.py`
  - [x] Cache-Prufung in den Lock verschieben
  - [x] `connected` Zustand vor Rueckgabe validieren


- [x] Ultra-Fast Polling vs Write-Operationen in `hub.py`
  - [x] Nachhol-Update nach Write implementieren
  - [x] Maximalen Warte-Timeout definieren


## 🟡 P1 – naechste Iteration

- [x] Lock-Strategie konsolidieren (Parallel Reads)
  - [x] Einheitliche Locks pro Reader-Klasse definieren
  - [x] Semaphore fuer Parallelisierungs-Limit evaluieren (Entscheidung: sequentiell, kein Semaphore noetig)
  - [x] Deadlock-Risiko bei verschachtelten Locks pruefen

- [ ] Circuit Breaker fuer Modbus Reads
  - [ ] Threshold + Timeout festlegen
  - [ ] Integration in `get_client()` und Read-Pfade
  - [ ] Recovery-Logik fuer HALF_OPEN testen

- [x] MQTT Strategy Decision Caching
  - [x] Strategie-Cache einbauen
  - [x] Cache-Invalidierung bei Config-Change
  - [ ] CPU-Last vor/nachher messen
- [x] Write-Priority in Ultra-Fast pruefen (Timeout-Strategie)
- [x] `get_client()` Status-Check vor Read/Write verifizieren

## 🟢 P2 – spaeter

- [x] Configuration Loading Optimierung
  - [x] Einmaliges Laden in Konfig-Cache
  - [x] Nutzung aller Werte aus Cache sicherstellen


- [ ] Connection Cache TTL Management
  - [ ] Dynamische TTL-Kriterien definieren
  - [ ] Anpassungslogik implementieren
 
- [x] Memory Management / Resource Cleanup
  - [x] Explizites Cleanup beim Unload
  - [x] Periodisches Aufraeumen veralteter Cache-Eintraege
  - [ ] Memory Footprint Monitoring
- [x] `_reconnecting` Flag nur unter Lock pruefen/setzen
- [x] `_write_in_progress` Flag entfernen oder konsistent nutzen
- [x] MQTT Circuit Breaker Threshold fuer Ultra-Fast feinjustieren

## 🔵 P3 – spaeter/optional

- [ ] Performance Metrics Collection System
  - [ ] Basis-Metriken definieren (Latency, Cache-Hits, Success Rate)
  - [ ] Metrik-Collector implementieren
  - [ ] Ausgabe in Logs oder Diagnostics
