# SAJ H2 Modbus Integration - Implementierungs-Tasks

**Version:** 1.0 | **Basierend auf:** Code-Improvement-Plan v2.0  
**Gesamter Aufwand:** ~31 Stunden | **Empfohlener Start:** Phase 1

---

## Phase 1: Quick Wins (Critical Issues) ⭐
**Dauer:** ~6 Stunden | **Risiko:** Minimal | **Impact:** Hoch

### 1.1 Fast-Poll State-Class Fix [CRITICAL] 🚨
**Aufwand:** 30 Min | **Priorität:** P0

- [ ] Neue Sensor-Klasse `FastPollSensor` in `sensor.py` erstellen
  - [ ] `state_class = None` setzen (keine DB-Aufzeichnung)
  - [ ] `force_update = True` beibehalten (UI-Updates)
- [ ] `SlowPollSensor` als Standard-Klasse definieren
- [ ] `async_setup_entry` anpassen:
  - [ ] Prüfung auf `FAST_POLL_SENSORS` Membership
  - [ ] Korrekte Klasse zuweisen (FastPollSensor vs SlowPollSensor)
- [ ] Test: Verifizieren, dass Fast-Poll Sensoren nicht in `states` Tabelle geschrieben werden

**Akzeptanzkriterien:**
- [ ] Fast-Poll Sensoren (10s) erzeugen keine DB-Einträge
- [ ] UI zeigt trotzdem Live-Updates
- [ ] Slow-Poll Sensoren (60s) werden normal aufgezeichnet

---

### 1.2 Config Value Utility
**Aufwand:** 30 Min | **Priorität:** P1

- [ ] Neue Datei `utils.py` erstellen
  - [ ] Funktion `get_config_value(entry, key, default=None)` implementieren
  - [ ] Docstring mit Args/Returns
- [ ] `hub.py` refactoren:
  - [ ] Import hinzufügen: `from .utils import get_config_value`
  - [ ] Methode `_get_config_value()` entfernen
  - [ ] Alle Aufrufe anpassen
- [ ] `__init__.py` refactoren:
  - [ ] Import hinzufügen
  - [ ] Funktion `_get_config_value()` entfernen
  - [ ] Aufrufe anpassen
- [ ] `config_flow.py` refactoren:
  - [ ] Import hinzufügen
  - [ ] Methode `_get_option_default()` entfernen
  - [ ] Aufrufe anpassen

**Akzeptanzkriterien:**
- [ ] Alle 3 Dateien nutzen zentrale Funktion
- [ ] Keine Duplikation mehr
- [ ] Integration startet ohne Fehler

---

### 1.3 Slot Entity Generation Utility
**Aufwand:** 1 Stunde | **Priorität:** P1

- [ ] `utils.py` erweitern:
  - [ ] Funktion `generate_slot_definitions(slot_type, count=7)` implementieren
  - [ ] Number-Entities für day_mask und power_percent generieren
  - [ ] Text-Entities für start_time und end_time generieren
  - [ ] Rückgabe als Dict mit 'number' und 'text' Keys
- [ ] `number.py` refactoren:
  - [ ] Import hinzufügen
  - [ ] 4 identische Loops (je ~40 Zeilen) entfernen
  - [ ] Utility-Funktion nutzen für Charge/Discharge
- [ ] `text.py` refactoren:
  - [ ] Import hinzufügen
  - [ ] 4 identische Loops entfernen
  - [ ] Utility-Funktion nutzen

**Akzeptanzkriterien:**
- [ ] Alle 28 Slot-Entities werden korrekt erzeugt
- [ ] ~120 Zeilen Code eliminiert
- [ ] Entity-Namen und IDs unverändert

---

### 1.4 Exception-Hierarchie
**Aufwand:** 2 Stunden | **Priorität:** P1

- [ ] Neue Datei `exceptions.py` erstellen:
  ```python
  class SAJIntegrationError(Exception)
  class SAJCommunicationError(SAJIntegrationError)
  class SAJModbusError(SAJCommunicationError)
  class SAJValidationError(SAJIntegrationError)
  class SAJTimeoutError(SAJCommunicationError)
  class SAJRegisterError(SAJIntegrationError)
  ```
- [ ] Jede Exception-Klasse mit:
  - [ ] Docstring
  - [ ] Kontext-Attributen (address, operation, etc.)
  - [ ] Sinnvoller __str__ Implementierung
- [ ] `modbus_utils.py` aktualisieren:
  - [ ] Import der neuen Exceptions
  - [ ] `ReconnectionNeededError` falls nötig verschieben
- [ ] Bestehende Try-Except Blöcke identifizieren:
  - [ ] `modbus_readers.py`: Exceptions mappen
  - [ ] `charge_control.py`: Exceptions mappen
  - [ ] `hub.py`: Exceptions mappen

**Akzeptanzkriterien:**
- [ ] Alle Exceptions sind spezifisch
- [ ] Fehlermeldungen enthalten Kontext (Adresse, Operation)
- [ ] `ReconnectionNeededError` wird weiterhin korrekt behandelt

---

### 1.5 Logging-Konsistenz
**Aufwand:** 30 Min | **Priorität:** P2

- [x] `sensor.py` durchsuchen:
  - [x] Alle f-string Logs finden (~10 Stück)
  - [x] In %-Formatierung umwandeln
- [x] `number.py` durchsuchen:
  - [x] f-string Logs finden (~1 Stück)
  - [x] In %-Formatierung umwandeln
- [x] `config_flow.py` durchsuchen:
  - [x] f-string Logs finden (~1 Stück)
  - [x] In %-Formatierung umwandeln
- [x] Überprüfung:
  - [x] Keine f-Strings in Logs mehr
  - [x] Lazy evaluation funktioniert

**Akzeptanzkriterien:**
- [x] Alle LOG-Aufrufe nutzen %-Formatierung
- [x] Keine f-Strings in _LOGGER Aufrufen
- [x] Performance-Verbesserung bei deaktiviertem DEBUG

---

## Phase 2: Quality & Tests
**Dauer:** ~13 Stunden | **Risiko:** Moderat | **Impact:** Mittel

### 2.1 Unit-Test-Framework
**Aufwand:** 8 Stunden | **Priorität:** P1 | **Abhängig von:** 1.4

- [ ] Verzeichnisstruktur erstellen:
  ```
  tests/
  ├── __init__.py
  ├── conftest.py
  ├── test_hub.py
  ├── test_charge_control.py
  ├── test_modbus_readers.py
  ├── test_services.py
  ├── test_utils.py
  └── fixtures/
      └── __init__.py
  ```
- [ ] `conftest.py` erstellen:
  - [ ] Fixture `mock_hub`
  - [ ] Fixture `mock_modbus_client`
  - [ ] Fixture `sample_inverter_data`
  - [ ] Fixture `event_loop` (für async Tests)
- [ ] `test_charge_control.py`:
  - [ ] Test: `test_set_charging_state_success`
  - [ ] Test: `test_set_charging_state_retry`
  - [ ] Test: `test_parse_time_to_register`
  - [ ] Test: `test_merge_write_register`
- [ ] `test_modbus_readers.py`:
  - [ ] Test: `test_read_realtime_data_success`
  - [ ] Test: `test_read_realtime_data_partial_failure`
  - [ ] Test: `test_decode_data_types`
- [ ] `test_utils.py`:
  - [ ] Test: `test_get_config_value`
  - [ ] Test: `test_time_utils`
  - [ ] Test: `test_generate_slot_definitions`
- [ ] Coverage-Check:
  - [ ] Ziel: >80% Coverage für neue Tests
  - [ ] Coverage-Report generieren

**Akzeptanzkriterien:**
- [ ] Tests laufen mit `pytest`
- [ ] >80% Coverage für getestete Module
- [ ] Alle Tests bestehen

---

### 2.2 Zeit-Utilities
**Aufwand:** 1 Stunde | **Priorität:** P2 | **Abhängig von:** 1.1

- [ ] `utils.py` erweitern:
  ```python
  class TimeUtils:
      TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
      
      @staticmethod
      def validate_time_string(time_str: str) -> bool
      
      @staticmethod
      def parse_time_to_register(time_str: str) -> Optional[int]
      
      @staticmethod
      def decode_time_from_register(value: int) -> str
  ```
- [ ] `charge_control.py` refactoren:
  - [ ] Methode `_parse_time_to_register()` entfernen
  - [ ] `TimeUtils.parse_time_to_register()` nutzen
- [ ] `text.py` refactoren:
  - [ ] Zeit-Validierung entfernen
  - [ ] `TimeUtils.validate_time_string()` nutzen

**Akzeptanzkriterien:**
- [ ] Zeit-Funktionen zentralisiert
- [ ] Duplizierter Code entfernt
- [ ] Funktionalität unverändert

---

### 2.3 Error Handler Decorators
**Aufwand:** 2 Stunden | **Priorität:** P2 | **Abhängig von:** 1.4

- [ ] `utils.py` erweitern:
  ```python
  def handle_reconnection_errors(func)
  def log_and_continue(logger_func=_LOGGER.warning)
  ```
- [ ] `modbus_readers.py` anpassen:
  - [ ] Decorator auf Reader-Funktionen anwenden
  - [ ] Redundante Try-Except entfernen
- [ ] `sensor.py` anpassen:
  - [ ] Decorator auf Listener-Funktionen anwenden
- [ ] Dokumentation:
  - [ ] Decorator-Usage in AGENTS.md dokumentieren

**Akzeptanzkriterien:**
- [ ] DRY Principle für Error Handling
- [ ] `ReconnectionNeededError` wird garantiert weitergegeben
- [ ] ~15 Zeilen Reduktion

---

### 2.4 Switch-Definitionen nach const.py
**Aufwand:** 1 Stunde | **Priorität:** P3

- [ ] `const.py` erweitern:
  ```python
  SWITCH_TYPES = {
      "charging": {"name": "Charging Control", ...},
      "discharging": {"name": "Discharging Control", ...},
      "passive_charge": {...},
      "passive_discharge": {...},
  }
  ```
- [ ] `switch.py` refactoren:
  - [ ] `SWITCH_DEFINITIONS` Liste entfernen
  - [ ] Import von `SWITCH_TYPES` aus const.py
  - [ ] Loop anpassen für Dict statt List

**Akzeptanzkriterien:**
- [ ] Konsistent mit SENSOR_TYPES Pattern
- [ ] Alle Switches funktionieren
- [ ] Keine Breaking Changes

---

### 2.5 Docstring-Vervollständigung
**Aufwand:** 3 Stunden | **Priorität:** P2

- [ ] `hub.py`:
  - [ ] `_write_register()` Docstring
  - [ ] `merge_write_register()` Docstring
  - [ ] `_async_update_data()` Docstring
  - [ ] Lock-Methoden Docstrings
- [ ] `charge_control.py`:
  - [ ] `ChargeSettingHandler` Klassen-Docstring
  - [ ] `process_queue()` Docstring
  - [ ] Setter-Methoden Docstrings
- [ ] `modbus_readers.py`:
  - [ ] `_DATA_READ_CONFIG` Dokumentation
  - [ ] Reader-Funktionen Docstrings
- [ ] `modbus_utils.py`:
  - [ ] `try_read_registers()` Docstring
  - [ ] `try_write_registers()` Docstring

**Akzeptanzkriterien:**
- [ ] Alle öffentlichen Methoden haben Docstrings
- [ ] Args, Returns, Raises dokumentiert
- [ ] Beispiele wo sinnvoll

---

### 2.6 Architektur-Dokumentation
**Aufwand:** 2 Stunden | **Priorität:** P3

- [ ] `docs/architecture.md` erstellen:
  - [ ] Datenfluss-Diagramm (ASCII oder Mermaid)
  - [ ] Lock-Strategie Übersicht
  - [ ] Komponenten-Interaktion
- [ ] `docs/` Verzeichnis erstellen falls nicht vorhanden
- [ ] Diagramme:
  - [ ] Polling-Architektur
  - [ ] Lock-Hierarchie
  - [ ] Entity-Lifecycle

**Akzeptanzkriterien:**
- [ ] Neue Entwickler können Architektur verstehen
- [ ] Visuelle Darstellung vorhanden
- [ ] Mit bestehender Doku verlinkt

---

## Phase 3: Architecture (Optional) ⚠️
**Dauer:** ~11 Stunden | **Risiko:** Moderat-Hoch | **Nur nach Phase 1&2!**

### 3.1 Lock-System Vereinfachung
**Aufwand:** 3 Stunden | **Priorität:** P2 | **Abhängig von:** 2.1

- [ ] Analyse:
  - [ ] Aktuelle 5 Locks dokumentieren
  - [ ] Nutzungsmuster analysieren
- [ ] `hub.py` refactoren:
  - [ ] 5 Locks entfernen
  - [ ] 2 neue Locks einführen: `_read_lock`, `_write_lock`
  - [ ] `_merge_locks` beibehalten (kritisch!)
- [ ] Alle Dateien anpassen:
  - [ ] `modbus_readers.py`: Neue Lock-Namen
  - [ ] `charge_control.py`: Neue Lock-Namen
  - [ ] `hub.py`: Alle Lock-Referenzen
- [ ] Testing:
  - [ ] Parallele Operationen testen
  - [ ] Race Conditions prüfen
  - [ ] Deadlock-Prüfung

**Akzeptanzkriterien:**
- [ ] Nur noch 2 Locks (+ merge_locks)
- [ ] Keine Deadlocks
- [ ] Performance verbessert
- [ ] Alle Tests bestehen

---

### 3.2 Entity Factory Pattern
**Aufwand:** 4 Stunden | **Priorität:** P2 | **Abhängig von:** 2.1

- [ ] Neue Datei `entity_factory.py`:
  ```python
  class EntityDefinition:
      def __init__(self, key, name, entity_type, factory, ...)
  
  class SAJEntityFactory:
      _definitions: Dict[str, EntityDefinition]
      
      @classmethod
      def register(cls, definition)
      
      @classmethod
      def create_entity(cls, key, hub, device_info, **kwargs)
  ```
- [ ] `const.py`:
  - [ ] Entity-Definitionen als Datenstruktur
  - [ ] Factory-Registrierung
- [ ] `sensor.py`, `number.py`, `text.py`, `switch.py`:
  - [ ] Statische Entity-Erzeugung entfernen
  - [ ] Factory-Pattern nutzen

**Akzeptanzkriterien:**
- [ ] Zentrale Entity-Definition
- [ ] ~200 Zeilen eliminiert
- [ ] Einfache Erweiterbarkeit

---

### 3.3 Batch-Modbus-Reads
**Aufwand:** 4 Stunden | **Priorität:** P2 | **Abhängig von:** 2.1

- [ ] Neue Datei `batch_reader.py`:
  ```python
  class BatchReadBlock:
      def __init__(self, start, end, decoders)
  
  class ModbusBatchReader:
      def __init__(self, client, max_block_size=50)
      def _optimize_read_plan(self) -> List[BatchReadBlock]
      async def read_all(self) -> Dict[str, Any]
  ```
- [ ] `_DATA_READ_CONFIG` analysieren:
  - [ ] Register-Blöcke identifizieren
  - [ ] Optimale Lesestrategie berechnen
- [ ] `hub.py` integrieren:
  - [ ] Batch-Reader instanziieren
  - [ ] Neue Lesemethode implementieren
- [ ] Testing:
  - [ ] Weniger Modbus-Requests
  - [ ] Korrekte Daten
  - [ ] Fehlerbehandlung

**Akzeptanzkriterien:**
- [ ] ~50% weniger Modbus-Requests
- [ ] Daten bleiben korrekt
- [ ] Performance verbessert

---

## Testing & Qualitätsicherung

### Vor jedem Task:
- [ ] Backup der aktuellen Version
- [ ] Branch erstellen: `feature/task-name`

### Nach jedem Task:
- [ ] Manuelle Tests durchführen:
  - [ ] Config Flow durchlaufen
  - [ ] Alle Entities prüfen
  - [ ] Sensor-Updates funktionieren
  - [ ] Switch-Operationen funktionieren
  - [ ] Number-Eingaben funktionieren
  - [ ] Zeit-Eingaben funktionieren
  - [ ] Fast Poll aktiv (wenn enabled)
- [ ] Logs auf Fehler prüfen
- [ ] Dokumentation aktualisieren (falls nötig)

### Nach Abschluss einer Phase:
- [ ] Integration 24h im Produktivbetrieb testen
- [ ] Performance-Monitoring
- [ ] Review der Änderungen
- [ ] Merge in main branch

---

## Rollback-Plan

### Wenn etwas schiefgeht:

1. **Sofortmaßnahmen:**
   ```bash
   # Backup wiederherstellen
   git checkout main
   git branch -D feature/problem-branch
   ```

2. **Fehler identifizieren:**
   - Logs prüfen: `ha logs follow | grep saj_h2_modbus`
   - Letzte funktionierende Version finden
   - Diff analysieren

3. **Kommunikation:**
   - Issue im Repository erstellen
   - Betroffene User informieren (falls released)

---

## Zeitplan-Vorschlag

### Woche 1: Phase 1 (6h)
- **Tag 1:** 1.1 + 1.2 (1h)
- **Tag 2:** 1.3 (1h)
- **Tag 3:** 1.4 (2h)
- **Tag 4:** 1.5 + Testing (1h)
- **Tag 5:** Buffer/Review (1h)

### Woche 2: Phase 2 (13h)
- **Tag 1-2:** 2.1 Unit-Tests (8h)
- **Tag 3:** 2.2 + 2.3 (3h)
- **Tag 4:** 2.4 + 2.5 (4h)
- **Tag 5:** 2.6 + Testing (2h)

### Woche 3-4: Phase 3 (11h) - Optional
- **Tag 1-2:** 3.1 Lock-System (3h)
- **Tag 3-4:** 3.2 Entity Factory (4h)
- **Tag 5:** 3.3 Batch-Reads (4h)

---

## Empfohlene Reihenfolge

```
Phase 1 (MUST):
├── 1.1 Fast-Poll Fix [START HERE]
├── 1.2 Config Utility
├── 1.3 Slot Generation
├── 1.4 Exceptions
└── 1.5 Logging

Phase 2 (SHOULD):
├── 2.1 Unit Tests [ABHÄNGIG von 1.4]
├── 2.2 Time Utils
├── 2.3 Error Decorators [ABHÄNGIG von 1.4]
├── 2.4 Switch Definitions
├── 2.5 Docstrings
└── 2.6 Arch Docs

Phase 3 (COULD - Nur nach 1&2!):
├── 3.1 Lock System [ABHÄNGIG von 2.1]
├── 3.2 Entity Factory [ABHÄNGIG von 2.1]
└── 3.3 Batch Reads [ABHÄNGIG von 2.1]
```

---

**Hinweis:** Phase 1 hat den besten ROI (Return on Investment). Phase 2 verbessert langfristige Qualität. Phase 3 ist optional und sollte nur angegangen werden, wenn Phase 1 & 2 erfolgreich abgeschlossen wurden.

**Gesamtfortschritt:**
- [ ] Phase 1 abgeschlossen
- [ ] Phase 2 abgeschlossen
- [ ] Phase 3 abgeschlossen
