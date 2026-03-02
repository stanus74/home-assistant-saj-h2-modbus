# Aufgabenliste SAJ H2 Modbus Optimierung (sync MRZ)

## 🔴 P0 – sofort

- [x] Race Condition: `self.inverter_data` Updates (Slow/Fast/Ultra mit Lock)
- [x] Race Condition: `_fast_listeners` Iteration/Mutation absichern
- [x] `ReconnectionNeededError` in `_async_update_fast` korrekt behandeln (re-raise + reconnect)
- [x] Paho MQTT Publishing via Circuit Breaker absichern

- [x] Stale Client Reference / Cache-Race in `services.py`
  - [x] Cache-Prufung in den Lock verschieben
  - [x] `connected` Zustand vor Rueckgabe validieren
  - [ ] Tests fuer parallele `get_client()` Aufrufe unter Last

- [x] Ultra-Fast Polling vs Write-Operationen in `hub.py`
  - [x] Nachhol-Update nach Write implementieren
  - [x] Maximalen Warte-Timeout definieren
  - [ ] Regressionstest fuer veraltete Echtzeitwerte

## 🟡 P1 – naechste Iteration

- [x] Lock-Strategie konsolidieren (Parallel Reads)
  - [x] Einheitliche Locks pro Reader-Klasse definieren
  - [ ] Semaphore fuer Parallelisierungs-Limit evaluieren
  - [x] Deadlock-Risiko bei verschachtelten Locks pruefen

- [ ] Circuit Breaker fuer Modbus Reads
  - [ ] Threshold + Timeout festlegen
  - [ ] Integration in `get_client()` und Read-Pfade
  - [ ] Recovery-Logik fuer HALF_OPEN testen

- [x] MQTT Strategy Decision Caching
  - [x] Strategie-Cache einbauen
  - [x] Cache-Invalidierung bei Config-Change
  - [ ] CPU-Last vor/nachher messen
- [ ] Write-Priority in Ultra-Fast pruefen (Timeout-Strategie)
- [ ] `get_client()` Status-Check vor Read/Write verifizieren

## 🟢 P2 – spaeter

- [x] Configuration Loading Optimierung
  - [x] Einmaliges Laden in Konfig-Cache
  - [x] Nutzung aller Werte aus Cache sicherstellen
  - [ ] Startup-Zeit messen

- [ ] Connection Cache TTL Management
  - [ ] Dynamische TTL-Kriterien definieren
  - [ ] Anpassungslogik implementieren
  - [ ] Stabilitaetstests mit variabler TTL

- [x] Memory Management / Resource Cleanup
  - [x] Explizites Cleanup beim Unload
  - [x] Periodisches Aufraeumen veralteter Cache-Eintraege
  - [ ] Memory Footprint Monitoring
- [ ] `_reconnecting` Flag nur unter Lock pruefen/setzen
- [ ] `_write_in_progress` Flag entfernen oder konsistent nutzen
- [ ] MQTT Circuit Breaker Threshold fuer Ultra-Fast feinjustieren

## 🔵 P3 – spaeter/optional

- [ ] Performance Metrics Collection System
  - [ ] Basis-Metriken definieren (Latency, Cache-Hits, Success Rate)
  - [ ] Metrik-Collector implementieren
  - [ ] Ausgabe in Logs oder Diagnostics
