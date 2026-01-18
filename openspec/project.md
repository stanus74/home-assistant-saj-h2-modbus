# Project Context

## Purpose
[Describe your project's purpose and goals]

## Tech Stack
- [List your primary technologies]
- [e.g., TypeScript, React, Node.js]

## Project Conventions

### Code Style
[Describe your code style preferences, formatting rules, and naming conventions]

### Architecture Patterns
[Document your architectural decisions and patterns]

## Domain Context
This project integrates with SAJ H2 Modbus inverters, focusing on reliable data acquisition and control. Key areas include Modbus communication, Home Assistant entity updates, MQTT publishing, charge/discharge scheduling, and robust error handling.

## Functional Areas & Analysis Prompts

### 1️⃣ **MODBUS REGISTER LESEN** (Data Ingestion)
**Betroffene Dateien:**
- `modbus_readers.py` (Haupt-Modul)
- `modbus_utils.py` (Verbindung & Retry)
- `hub.py` (Orchestrierung)

**Verantwortlichkeiten:**
- Verbindung zum Inverter herstellen
- Register auslesen (300+ Register in Gruppen)
- Dekodierung der Rohdaten
- Fehlerbehandlung bei Verbindungsabbrüchen
- Caching und Polling-Strategien (60s, 10s, 1s)

**Kritische Themen:**
- Datenverlust bei Fehlern (leeres `{}` statt Partial-Daten)
- Lock-Contention zwischen 3 Polling-Levels
- Timeout & Reconnection Logic
- Register-Adress-Mapping

**Analysis Prompt:** [Link to prompt for Area 1](#area-1-prompt)

### 2️⃣ **HOME ASSISTANT ENTITY UPDATES** (Data Publishing zu HA)
**Betroffene Dateien:**
- `sensor.py` (Entity-Klasse SajSensor)
- `hub.py` (DataUpdateCoordinator)
- `const.py` (Sensor-Definitionen)

**Verantwortlichkeiten:**
- Sensoren aus Registry laden
- Native Values aus `inverter_data` abrufen
- Fast-Update Listener registrieren/deregistrieren
- State-Schreiben mit `async_write_ha_state()`
- Entity-Registry-Status verwalten (enabled/disabled)
- Force-Update für Power-Sensoren

**Kritische Themen:**
- Fast Listener lifecycle
- Removed Entity Race Conditions
- State-Change Detection
- Force-Update Spam

**Analysis Prompt:** [Link to prompt for Area 2](#area-2-prompt)

### 3️⃣ **MQTT PUBLISHING** (MQTT Data Export)
**Betroffene Dateien:**
- `services.py` (MqttPublisher Klasse)
- `hub.py` (MQTT-Integration)

**Verantwortlichkeiten:**
- MQTT-Connection verwalten (Paho oder HA-MQTT)
- Daten zu MQTT Topics veröffentlichen
- Topic-Prefix und Payload-Format
- Ultra-Fast Modus (1s Interval nur über MQTT)
- Fallback-Logik (HA-MQTT vs. Custom Paho)

**Kritische Themen:**
- MQTT Connection Reliability
- Publish-Fehler bei Stromausfall/Netzwerk
- Topic-Struktur Design
- Payload-Format (JSON vs. einzelne Values)
- Ultra-Fast Mode Performance

**Analysis Prompt:** [Link to prompt for Area 3](#area-3-prompt)

### 4️⃣ **CHARGE/DISCHARGE ZEITPLANUNG - PROGRAMMIERUNG** (Schedule Input)
**Betroffene Dateien:**
- `charge_control.py` (ChargeSettingHandler)
- `number.py` & `text.py` (UI Entities für Input)
- `config_flow.py` (Keine Rolle hier)

**Verantwortlichkeiten:**
- Benutzer-Eingaben für 7 Charge-Zeitslots entgegennehmen
- Benutzer-Eingaben für 7 Discharge-Zeitslots entgegennehmen
- Time Format Validierung (HH:MM)
- Day-Mask Verarbeitung (Weekday Bitmap)
- Power-Percent Validierung
- Optimistic UI Updates (Immediate Feedback)

**Kritische Themen:**
- Input-Validierung
- Pending State Tracking
- Optimistic Overlay
- Entity Enable/Disable Logic

**Analysis Prompt:** [Link to prompt for Area 4](#area-4-prompt)

### 5️⃣ **CHARGE/DISCHARGE SCHREIBEN ZUM MODBUS** (Register Write & Verification)
**Betroffene Dateien:**
- `charge_control.py` (ChargeSettingHandler - Schreib-Logik)
- `modbus_utils.py` (try_write_registers)
- `hub.py` (_write_register, merge_write_register)

**Verantwortlichkeiten:**
- Gültige Modbus-Adressen bestimmen
- Register-Werte berechnen (Time Encoding, Day-Mask Packing, Power %)
- Read-Modify-Write für Bit-Felder (0x3604, 0x3605)
- Sequenzielles Schreiben (Queue-based)
- Retry-Logic mit exponentiellem Backoff
- Verifikation nach Write (Read-Back)
- Fehlerbehandlung und Rollback

**Kritische Themen:**
- Register-Adressen korrekt?
- Bit-Masken-Manipulation richtig?
- Race Conditions zwischen Read/Write?
- Merge-Locks sinnvoll?

**Analysis Prompt:** [Link to prompt for Area 5](#area-5-prompt)

### 6️⃣ **KONFIGURATION & LIFECYCLE** (Setup & Teardown)
**Betroffene Dateien:**
- `__init__.py` (Integrations-Setup)
- `config_flow.py` (ConfigFlow UI)
- `hub.py` (Initialization & Unload)

**Verantwortlichkeiten:**
- Integration registrieren
- Config Entry erstellen/aktualisieren
- Modbus-Verbindung initialisieren
- Fast/Ultra-Fast Polling starten
- MQTT-Strategie wählen
- Koordinator starten
- Entities laden
- Auf Reload reagieren

**Kritische Themen:**
- First Refresh Timeout
- Startup Delay Logik
- Config-Fallback-Kette
- Hot-Reload Support

**Analysis Prompt:** [Link to prompt for Area 6](#area-6-prompt)

### 7️⃣ **ERROR HANDLING & LOGGING** (Diagnostik & Troubleshooting)
**Betroffene Dateien:**
- Alle Dateien (verteilt)
- `modbus_utils.py` (Exception Handling)
- `modbus_readers.py` (Decoder Errors)

**Verantwortlichkeiten:**
- Aussagekräftige Error-Meldungen
- Strukturiertes Logging (DEBUG, INFO, WARNING, ERROR)
- Exception-Klassifizierung
- Debugging-Informationen bereitstellen
- Performance-Metriken
- User-facing Error Messages

**Analysis Prompt:** [Link to prompt for Area 7](#area-7-prompt)

## Technical Guardrails
This section outlines critical technical considerations for ensuring the reliability and integrity of the SAJ H2 Modbus integration.

### Partial-Data Recovery
In scenarios where Modbus communication encounters transient errors, the system must be able to recover partial data rather than discarding all information. This prevents data loss and ensures that sensors reflect the most up-to-date state possible, even during brief interruptions.

### Lock-Contention Avoidance
The integration employs multiple polling levels (e.g., slow, fast, ultra-fast) and potentially different communication strategies (Modbus, MQTT). Mechanisms must be in place to prevent or mitigate lock contention between these concurrent operations, ensuring smooth execution and preventing deadlocks or performance degradation.

### Write Verification
After writing data to the Modbus registers, a verification step is crucial. This involves reading back the written values to confirm that the operation was successful and that the inverter has correctly registered the changes. This guards against silent failures in write operations.

## Project Conventions

### Code Style
[Describe your code style preferences, formatting rules, and naming conventions]

### Architecture Patterns
[Document your architectural decisions and patterns]

### Testing Strategy
[Explain your testing approach and requirements]

### Git Workflow
[Describe your branching strategy and commit conventions]

## External Dependencies
[Document key external services, APIs, or systems]
