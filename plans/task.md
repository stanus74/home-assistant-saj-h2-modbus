# Umsetzungstasks: SAJ H2 Modbus Integration Optimierung (opti-2305)

Basierend auf dem Plan `plans/opti-2305.md`.

## Phase 1 — Quick Wins (Vorarbeiten Code-Qualität & kleine Fixes)
- [x] **E402 Docstring-Platzierung:** Moduldokstring in `hub.py` als allererste Zeile (vor den `__future__`-Import) setzen.
- [x] **Ungenutzte Imports entfernen (F401):** Aus `charge_control.py`, `hub.py`, `services.py` und `sensor.py` verwaiste Imports aufräumen.
- [x] **Fehlende Type Hints in `number.py`:** Sämtliche Methoden, Parameter und Rückgabewerte explizit typisieren.
- [x] **Circuit Breaker für Write-Fehler:** In `modbus_utils.py` die Bedingung `_should_trip_circuit_breaker()` um `ModbusIOException` ergänzen, damit auch Modbus-Protokollfehler Rate-Limits triggern.

## Phase 2 — Stabilität (Race Conditions beheben)
- [x] **`_is_removed` Race Condition:** In `sensor.py` `_handle_fast_update` so umschreiben, dass der Status atomar gesetzt und bei Entfernungen konsequent asynchrone "Double-Writes" an Home Assistant unterbunden werden.
- [x] **`_rmw_locks` LRU-Eviction ohne Lock-Schutz:** In `hub.py` die Eviction von RMW-Locks (Read-Modify-Write) thread-safe machen, damit beim Rotieren aus dem Cache keine Locks fälschlicherweise in aktiven Prozessen freigegeben werden.
- [x] **`_on_remove_cleanup_registered` Race:** Flag in `sensor.py` entfernen; HA registriert beim `async_added_to_hass` / `async_will_remove_from_hass` korrekte State-Lifecycles von alleine ohne redundante Überprüfung.

## Phase 3 — Multi-Inverter-Fähigkeit (Architektonischer Kernumbau)
- [ ] **`ModbusGlobalConfig` entfernen:** Modul-Zustand aus `modbus_utils.py` entfernen. Stattdessen eine `ModbusConnectionConfig` Klasse (pro Verbindung) instanziieren und an die entsprechenden Lese/Schreib-Routinen weiterreichen.
- [ ] **`_RECONNECT_LOCK` / `_RECONNECT_DONE` instanziieren:** Auch diese Reconnect-Guards pro `ModbusConnectionManager`-Instanz anlegen, damit zwei getrennte Inverter sich bei Reconnects nicht global blockieren.

## Phase 4 — Performance (Latenz & Systemauslastung)
- [x] **`async_add_executor_job` für Modbus-Aufrufe entfernen:** Pymodbus 3.x ist voll asynchron. Folglich in `modbus_utils.py` direkte `await operation(...)` Routine einrichten, anstatt Kontext-Wechsel in HA-Threads zu erzwingen.
- [x] **`_rmw_locks` TTL-Garbage Collection:** Speichermanagement in `hub.py` einbauen, durch das selten geschriebene Register-Locks nach z.B. 1 Stunde aus dem Cache aufgeräumt werden.
- [x] **Lock-Strategie straffen (`_fast_lock` / `_ultra_fast_lock`):** Da Register sequenziell auf dem gleichen Client gepollt werden, reicht in `hub.py` ein zusammengefasster `_read_lock` für alle Lese-Routinen völlig aus. Reduziert Instanzen.

## Phase 5 — MQTT & Entity Polishing
- [ ] **`notify_error` Race Condition:** Die Auswertung des `_connection_healthy` Flags in `services.py` nochmals innerhalb des Cache-Locks in `get_cached_client` verifizieren, um die Weitergabe stale/alter Client-Instanzen zu unterbinden.
- [ ] **MQTT Publishing Rate-Limiting:** Einen lokalen Cooldown-Stempel in `MqttPublisher.publish_data` verwalten, der im Ultra-Fast-Modus abfängt, dass identische Werte den HA Ereignis-Bus dauerfeuern.
- [ ] **Fast-Sensor Redundanzen (Dualität):** In `sensor.py` abstellen, dass für jeden 'Fast'-Sensor zwei verschiedene HA-Entities initialisiert werden; besser via `force_update=True` oder dynamischer Polling-Zeit managen.
