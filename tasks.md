# Aufgabenliste SAJ H2 Modbus Optimierung (sync MRZ)

## 🔴 P0 – sofort

- [x] Race Condition: `self.inverter_data` Updates (Slow/Fast/Ultra mit Lock)
- [x] Race Condition: `_fast_listeners` Iteration/Mutation absichern
- [x] `ReconnectionNeededError` in `_async_update_fast` korrekt behandeln (re-raise + reconnect)
- [x] Paho MQTT Publishing via Circuit Breaker absichern

- [x] Stale Client Reference / Cache-Race in `services.py`
  - [x] Cache-Prufung in den Lock verschieben
  - [x] `connected` Zustand vor Rueckgabe validieren

- [x] Race Condition: `ConnectionCache` in `modbus_utils.py` ohne `asyncio.Lock`
  - [x] `_cache_lock = asyncio.Lock()` hinzufuegen
  - [x] `get_cached_client`, `set_cached_client`, `invalidate` mit Lock absichern

- [x] Ultra-Fast Polling vs Write-Operationen in `hub.py`
  - [x] Nachhol-Update nach Write implementieren
  - [x] Maximalen Warte-Timeout definieren
  - [x] 0.2s `asyncio.wait_for` durch sofortiges Skip ersetzen (`hub.py` ~L419)


## 🟡 P1 – naechste Iteration

- [x] Lock-Strategie konsolidieren (Parallel Reads)
  - [x] Einheitliche Locks pro Reader-Klasse definieren
  - [x] Semaphore fuer Parallelisierungs-Limit evaluieren (Entscheidung: sequentiell, kein Semaphore noetig)
  - [x] Deadlock-Risiko bei verschachtelten Locks pruefen
  - [ ] `_lock_order_guard`: `RuntimeError` statt `_LOGGER.warning` (`hub.py` ~L614)

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

- [x] Retry-Reconnect: Lock nicht waehrend Reconnect halten (`modbus_utils.py` `_on_modbus_retry`)
  - [x] `async with lock:` um Reconnect-Block entfernen
  - [x] Reconnect ausserhalb des Locks ausfuehren

## 🟢 P2 – spaeter

- [x] Configuration Loading Optimierung
  - [x] Einmaliges Laden in Konfig-Cache
  - [x] Nutzung aller Werte aus Cache sicherstellen


- [ ] Connection Cache TTL Management
  - [ ] Dynamische TTL-Kriterien definieren
  - [ ] Anpassungslogik implementieren
  - [ ] Health Check Interval: 30s → 5s (`modbus_utils.py` `_health_check_interval`)

- [x] Memory Management / Resource Cleanup
  - [x] Explizites Cleanup beim Unload
  - [x] Periodisches Aufraeumen veralteter Cache-Eintraege
  - [ ] Memory Footprint Monitoring
- [x] `_reconnecting` Flag nur unter Lock pruefen/setzen
- [x] `_write_in_progress` Flag entfernen oder konsistent nutzen
- [x] MQTT Circuit Breaker Threshold fuer Ultra-Fast feinjustieren
  - [ ] `failure_threshold=3` → 5 setzen (`services.py` L216 + L411)
  - [ ] `timeout=30` → 60 fuer ultra-fast anpassen (`services.py` L217 + L412)

## 🔵 P3 – spaeter/optional

- [ ] Performance Metrics Collection System
  - [ ] Basis-Metriken definieren (Latency, Cache-Hits, Success Rate)
  - [ ] Metrik-Collector implementieren
  - [ ] Ausgabe in Logs oder Diagnostics
