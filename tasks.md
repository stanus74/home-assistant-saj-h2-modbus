# Aufgabenliste SAJ H2 Modbus Optimierung 01.03.26

## 🔴 CRITICAL

- [x] Stale Client Reference / Cache-Race in `services.py`
  - [x] Cache-Prufung in den Lock verschieben
  - [x] `connected` Zustand vor Rueckgabe validieren
  - [ ] Tests fuer parallele `get_client()` Aufrufe unter Last

- [x] Ultra-Fast Polling vs Write-Operationen in `hub.py`
  - [x] Nachhol-Update nach Write implementieren
  - [x] Maximalen Warte-Timeout definieren
  - [ ] Regressionstest fuer veraltete Echtzeitwerte

## 🟡 HIGH

- [x] Lock-Strategie konsolidieren (Parallel Reads)
  - [x] Einheitliche Locks pro Reader-Klasse definieren
  - [ ] Semaphore fuer Parallelisierungs-Limit evaluieren
  - [ ] Deadlock-Risiko bei verschachtelten Locks pruefen

- [ ] Circuit Breaker fuer Modbus Reads
  - [ ] Threshold + Timeout festlegen
  - [ ] Integration in `get_client()` und Read-Pfade
  - [ ] Recovery-Logik fuer HALF_OPEN testen

- [ ] MQTT Strategy Decision Caching
  - [ ] Strategie-Cache einbauen
  - [ ] Cache-Invalidierung bei Config-Change
  - [ ] CPU-Last vor/nachher messen

## 🟢 MEDIUM

- [ ] Configuration Loading Optimierung
  - [ ] Einmaliges Laden in Konfig-Cache
  - [ ] Nutzung aller Werte aus Cache sicherstellen
  - [ ] Startup-Zeit messen

- [ ] Connection Cache TTL Management
  - [ ] Dynamische TTL-Kriterien definieren
  - [ ] Anpassungslogik implementieren
  - [ ] Stabilitaetstests mit variabler TTL

- [ ] Memory Management / Resource Cleanup
  - [ ] Explizites Cleanup beim Unload
  - [ ] Periodisches Aufraeumen veralteter Cache-Eintraege
  - [ ] Memory Footprint Monitoring

## 🔵 LOW / SPAETER

- [ ] Performance Metrics Collection System
  - [ ] Basis-Metriken definieren (Latency, Cache-Hits, Success Rate)
  - [ ] Metrik-Collector implementieren
  - [ ] Ausgabe in Logs oder Diagnostics
