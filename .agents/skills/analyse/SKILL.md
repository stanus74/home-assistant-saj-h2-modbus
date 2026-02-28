---
name: saj-h2-modbus-analysis
description: Analysiert und optimiert die SAJ H2 Modbus Home Assistant Integration. Verwende diesen Skill bei Fragen zu Performance, Race Conditions, Polling-Optimierung, Lock-Verwaltung, Circuit Breaker, Connection Management oder Code-Review der Integration. Auch bei allgemeinen Begriffen wie "Optimierung", "Debugging" oder "Analyse" im Kontext dieser Integration aktivieren.
license: MIT
compatibility: opencode
metadata:
  language: de
  project: home-assistant-saj-h2-modbus
  domain: home-assistant
---

# SAJ H2 Modbus Integration – Analyse Skill

Antworte immer auf Deutsch, es sei denn, der Nutzer fragt explizit auf Englisch.

**Projekt-Verzeichnis:** `/home/pat/Dokumente/GitHub/home-assistant-saj-h2-modbus/`
**Pläne speichern unter:** `/home/pat/Dokumente/GitHub/home-assistant-saj-h2-modbus/plans/`

## Was ich tue

- **Codebase-Analyse:** Systematische Untersuchung der Integration auf Schwachstellen und Optimierungspotenzial
- **Race Condition Erkennung:** Identifiziere ungeschützte gleichzeitige Modbus-Zugriffe und Lock-Probleme
- **Polling-Optimierung:** Analysiere das Drei-Schicht-Polling System (60s / 10s / 1s)
- **Connection Management:** Bewerte Circuit Breaker Pattern und Reconnect-Logik
- **Optimierungsplanung:** Erstelle priorisierte Pläne mit CRITICAL / HIGH / MEDIUM

## Wann mich verwenden

- Umfassende Analyse des SAJ H2 Integrationscodes
- Entwicklung von Optimierungsplänen mit Priorisierung
- Identifikation und Dokumentation von Race Conditions
- Review des Drei-Schicht-Polling Systems
- Erstellung technischer Dokumentation für weitere Entwicklung

---

## Architektur

### Drei-Schicht-Polling

| Schicht | Intervall | Zweck |
|---------|-----------|-------|
| Slow    | 60s       | Statische Werte (Seriennummer, Firmware) |
| Normal  | 10s       | Standard-Sensordaten |
| Fast    | 1s        | Kritische Echtzeit-Werte |

### Schlüsselkomponenten
- **Connection Manager** – Modbus TCP Verbindungsverwaltung
- **Circuit Breaker** – Schutz vor Kaskadenfehler
- **Async Command Queue** – Serialisierung von Modbus-Anfragen
- **Lock Management** – Vermeidung gleichzeitiger Zugriffe
- **Register Cache** – Zwischenspeicherung häufig abgefragter Register

### Wichtige Dateien
```
custom_components/saj_modbus/
├── __init__.py          # Entry Point, Coordinator Setup
├── coordinator.py       # Data Update Coordinator, Polling-Logik
├── modbus_controller.py # Modbus Kommunikation
├── sensor.py            # Sensor Entity Definitionen
└── const.py             # Konstanten, Register-Definitionen
```

---

## Analyse-Workflow

### 1. Exploration
```bash
find /home/pat/Dokumente/GitHub/home-assistant-saj-h2-modbus \
  -name "*.py" | grep -v __pycache__
```

### 2. Race Condition Prüfung

```python
# ANTI-PATTERN – kein Lock-Schutz
async def update_fast(self):
    data = await self.read_registers(...)  # gleichzeitig mit update_normal möglich!

# KORREKT – Lock-Schutz
async def read_registers(self, ...):
    async with self._lock:
        return await self._client.read_holding_registers(...)
```

Worauf achten:
- Shared State ohne Lock (`self._client`, `self._connected`)
- `asyncio.Lock` vs `asyncio.Semaphore` – was ist angemessen?
- Deadlock-Potenzial bei verschachtelten Locks
- Timeout bei blockierenden Lock-Wartezeiten

### 3. Circuit Breaker Prüfung

```python
# Zustände prüfen:
# CLOSED    → Normal, Anfragen werden durchgelassen
# OPEN      → Fehler-Zustand, Anfragen blockiert
# HALF_OPEN → Test-Phase, Wiederherstellung

# Zu prüfen:
# - Threshold für OPEN (wie viele Fehler nötig?)
# - Timeout bis HALF_OPEN
# - Recovery-Logik korrekt?
```

---

## Optimierungspriorisierung

### 🔴 CRITICAL – sofort beheben
- Race Conditions mit Datenverlust-Risiko
- Unbehandelte Exceptions die Integration zum Absturz bringen
- Memory Leaks bei langen Laufzeiten
- Deadlocks im Lock-System

### 🟡 HIGH – nächste Iteration
- Connection Pooling / effiziente Verbindungsverwaltung
- Circuit Breaker (falls fehlend)
- Batch-Register-Reads statt Einzel-Reads
- Fehlerhafte Retry-Logik

### 🟢 MEDIUM – nach Stabilisierung
- Cache-Strategie für statische Register
- Konfigurierbare Polling-Intervalle
- Logging-Optimierung
- Home Assistant Diagnostics Metriken

---

## Performance-Zielwerte

| Metrik | Ziel |
|--------|------|
| Response Time kritische Sensoren | < 500ms |
| Connection Success Rate | > 95% |
| Memory Footprint | < 90MB |
| Lock Contention Reduktion | > 40% |
| Cache Hit Ratio | > 80% |
| Reconnect Zeit nach Fehler | < 5s |

---

## Dokumentationsformat für Findings

```markdown
## Finding: [Komponente/Problem]

**Priorität:** 🔴 CRITICAL / 🟡 HIGH / 🟢 MEDIUM
**Datei:** `custom_components/saj_modbus/xxx.py`, Zeile YYY

**Problem:**
[Kurze Beschreibung]

**Problematischer Code:**
[Code-Snippet]

**Auswirkung:**
[Was passiert wenn das Problem auftritt?]

**Lösung:**
[Verbesserter Code]

**Messbare Verbesserung:**
[Konkrete Zielwerte]
```