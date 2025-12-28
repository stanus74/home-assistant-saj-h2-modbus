# Entity-Optimierungsplan für SAJ H2 Modbus Home Assistant Integration

## Zusammenfassung

Dieser Plan beschreibt die Optimierung der Entity-Implementierungen für die SAJ H2 Modbus Integration. Der Fokus liegt auf der Verbesserung der Schreibbestätigung, der Implementierung von optimistischen Updates, der Fehlerbehandlung und der Reduzierung von Codeduplizierung.

## Prioritätsmatrix

| Priorität | Kategorie | Beschreibung |
|-----------|-----------|--------------|
| **Kritisch** | Funktionalität | Schreibbestätigung für number.py und text.py |
| **Kritisch** | Funktionalität | Statusverifizierung für switch.py |
| **Hoch** | UX | Optimistische Updates für alle schreibbaren Entities |
| **Hoch** | UX | Konfigurierbare Standardwerte für text.py |
| **Mittel** | Codequalität | Reduzierung von Codeduplizierung |
| **Mittel** | Codequalität | Verbesserte Fehlerbehandlung und Logging |
| **Niedrig** | Codequalität | Type Hints hinzufügen |
| **Niedrig** | Dokumentation | Dokumentationsupdates |

## Detaillierte Optimierungselemente

### 1. number.py Optimierungen

#### 1.1 Schreibbestätigung (Kritisch)
**Problem:** Aktuell werden Werte geschrieben, aber nicht verifiziert.

**Lösung:**
- Implementierung einer Rücklesemethode nach dem Schreiben
- Vergleich des geschriebenen Werts mit dem gelesenen Wert
- Fehlerbehandlung bei Diskrepanz

**Implementierung:**
```python
async def async_set_native_value(self, value):
    val = int(value)
    if not self._attr_native_min_value <= val <= self._attr_native_max_value:
        _LOGGER.error(f"Invalid value for {self._attr_name}: {val}")
        return
    
    # Optimistisches Update
    self._attr_native_value = val
    self.async_write_ha_state()
    
    # Schreiben und Bestätigen
    if self.set_method:
        success = await self.set_method(val)
        if not success:
            _LOGGER.error(f"Failed to write {self._attr_name}: {val}")
            # Rollback bei Fehler
            self._attr_native_value = self._hub.inverter_data.get(self._get_data_key())
            self.async_write_ha_state()
            return
    
    # Verifizierung durch Rücklesen
    await asyncio.sleep(0.5)  # Kurze Verzögerung für Modbus
    actual_value = await self._read_value_from_device()
    if actual_value != val:
        _LOGGER.warning(f"Value mismatch for {self._attr_name}: expected {val}, got {actual_value}")
        self._attr_native_value = actual_value
        self.async_write_ha_state()
```

#### 1.2 Optimistische Updates (Hoch)
**Problem:** Keine sofortige UI-Feedback bei Schreibvorgängen.

**Lösung:**
- Sofortiges Update des UI-Status vor dem eigentlichen Schreiben
- Nutzung des bestehenden `_optimistic_overlay` Mechanismus im Hub

#### 1.3 Fehlerbehandlung (Mittel)
**Problem:** Einfache Fehlerbehandlung ohne Retry-Logik.

**Lösung:**
- Integration mit dem Retry-Mechanismus aus `charge_control.py`
- Exponentielles Backoff bei Fehlern
- Detailliertes Logging

### 2. text.py Optimierungen

#### 2.1 Schreibbestätigung (Kritisch)
**Problem:** Zeitwerte werden geschrieben, aber nicht verifiziert.

**Lösung:**
- Ähnlich wie number.py: Rücklesen nach dem Schreiben
- Konvertierung des Registerwerts zurück in Zeitformat für Vergleich

**Implementierung:**
```python
async def async_set_value(self, value) -> None:
    # Validierung
    if isinstance(value, datetime.time):
        value = value.strftime("%H:%M")
    
    if not isinstance(value, str) or not re.match(self._attr_pattern, value):
        _LOGGER.error(f"Invalid time format for {self._attr_name}: {value}")
        return
    
    # Optimistisches Update
    self._attr_native_value = value
    self.async_write_ha_state()
    
    # Schreiben
    await self.set_method(value)
    
    # Verifizierung
    await asyncio.sleep(0.5)
    actual_value = await self._read_time_from_device()
    if actual_value != value:
        _LOGGER.warning(f"Time mismatch for {self._attr_name}: expected {value}, got {actual_value}")
        self._attr_native_value = actual_value
        self.async_write_ha_state()
```

#### 2.2 Konfigurierbare Standardwerte (Hoch)
**Problem:** Hardcodierte Standardwerte (01:00-01:10 für Charge, 02:00-02:10 für Discharge).

**Lösung:**
- Standardwerte aus `const.py` oder Config Entry lesen
- Möglichkeit für Benutzer, Standardwerte zu konfigurieren

**Implementierung:**
```python
# In const.py hinzufügen:
DEFAULT_CHARGE_START_TIME = "01:00"
DEFAULT_CHARGE_END_TIME = "01:10"
DEFAULT_DISCHARGE_START_TIME = "02:00"
DEFAULT_DISCHARGE_END_TIME = "02:10"

# In text.py verwenden:
from .const import (
    DEFAULT_CHARGE_START_TIME,
    DEFAULT_CHARGE_END_TIME,
    DEFAULT_DISCHARGE_START_TIME,
    DEFAULT_DISCHARGE_END_TIME,
)

def __init__(self, hub, name, unique_id, set_method, device_info, defaults=None):
    # ...
    if defaults:
        self._attr_native_value = defaults.get("default_value", "00:00")
    else:
        # Fallback auf Konstanten
        if "discharge" in name.lower():
            self._attr_native_value = DEFAULT_DISCHARGE_START_TIME if "start" in name.lower() else DEFAULT_DISCHARGE_END_TIME
        else:
            self._attr_native_value = DEFAULT_CHARGE_START_TIME if "start" in name.lower() else DEFAULT_CHARGE_END_TIME
```

#### 2.3 Fehlerbehandlung (Mittel)
**Problem:** Keine Retry-Logik bei Schreibfehlern.

**Lösung:**
- Integration mit dem Retry-Mechanismus aus `charge_control.py`
- Detailliertes Logging bei Fehlern

### 3. sensor.py Optimierungen

#### 3.1 Statusüberprüfung (Niedrig)
**Problem:** Sensor ist bereits gut implementiert, aber kleine Verbesserungen möglich.

**Lösung:**
- Bessere Fehlerbehandlung bei fehlenden Daten
- Warnungen bei inkonsistenten Daten

#### 3.2 Type Hints (Niedrig)
**Problem:** Fehlende Type Hints für bessere IDE-Unterstützung.

**Lösung:**
- Hinzufügen von Type Hints für alle Methoden und Eigenschaften

### 4. switch.py Optimierungen

#### 4.1 Statusverifizierung (Kritisch)
**Problem:** `assumed_state=True` ohne echte Verifizierung des Schaltzustands.

**Lösung:**
- Rücklesen des Status nach dem Schreiben
- Vergleich mit dem erwarteten Status
- Fehlerbehandlung bei Diskrepanz

**Implementierung:**
```python
async def _set_state(self, desired_state: bool) -> None:
    if self.is_on == desired_state:
        _LOGGER.debug("%s already %s", self._switch_type.capitalize(), "on" if desired_state else "off")
        return

    if not self._allow_switch():
        return

    try:
        _LOGGER.debug("%s turned %s", self._switch_type.capitalize(), "ON" if desired_state else "OFF")
        
        # Schreiben
        if self._switch_type in PASSIVE_SWITCH_KEYS:
            if not await self._handle_passive_mode_state(desired_state):
                return
        else:
            setter = getattr(self._hub, f"set_{self._switch_type}", None)
            if setter is None:
                _LOGGER.error("Hub missing setter for %s", self._switch_type)
                return
            await setter(desired_state)

        self._last_switch_time = time.time()
        
        # Verifizierung durch Rücklesen
        await asyncio.sleep(0.5)
        actual_state = self._read_actual_state()
        if actual_state != desired_state:
            _LOGGER.error(
                "State verification failed for %s: expected %s, got %s",
                self._switch_type, desired_state, actual_state
            )
            # Optional: Retry oder Fehlerstatus setzen
        else:
            _LOGGER.debug("State verification successful for %s", self._switch_type)

        self.async_write_ha_state()
    except Exception as e:
        _LOGGER.error("Failed to set %s state: %s", self._switch_type, e)
        raise

def _read_actual_state(self) -> bool:
    """Liest den tatsächlichen Status vom Gerät."""
    try:
        data = self._hub.inverter_data
        if self._switch_type == "charging":
            return bool(data.get("charging_enabled", 0) > 0)
        elif self._switch_type == "discharging":
            return bool(data.get("discharging_enabled", 0) > 0)
        elif self._switch_type in PASSIVE_SWITCH_KEYS:
            return data.get("passive_charge_enable") == PASSIVE_MODE_TARGETS[self._switch_type]
    except Exception as e:
        _LOGGER.warning("Error reading actual state for %s: %s", self._switch_type, e)
    return False
```

#### 4.2 Verbesserte Cooldown-Handling (Mittel)
**Problem:** Feste 2-Sekunden-Cooldown ohne Konfigurierbarkeit.

**Lösung:**
- Konfigurierbarer Cooldown über Config Entry
- Unterschiedliche Cooldowns für verschiedene Switch-Typen

**Implementierung:**
```python
# In const.py hinzufügen:
CONF_SWITCH_COOLDOWN = "switch_cooldown"
DEFAULT_SWITCH_COOLDOWN = 2

# In switch.py verwenden:
def __init__(self, hub: SAJModbusHub, device_info, description: dict):
    # ...
    self._switch_timeout = self._get_cooldown_for_switch(description["key"])

def _get_cooldown_for_switch(self, switch_type: str) -> float:
    """Gibt den Cooldown für einen bestimmten Switch-Typ zurück."""
    cooldowns = {
        "charging": 2.0,
        "discharging": 2.0,
        "passive_charge": 3.0,  # Längerer Cooldown für Passive Mode
        "passive_discharge": 3.0,
    }
    return cooldowns.get(switch_type, 2.0)
```

#### 4.3 Entfernung von assumed_state (Hoch)
**Problem:** `assumed_state=True` führt zu Verwirrung bei Benutzern.

**Lösung:**
- Auf `assumed_state=False` setzen, wenn Verifizierung implementiert ist
- Nutzung von `extra_state_attributes` für Pending-Status

## Implementierungsstrategie

### Phase 1: Grundlagen (Kritisch)
1. **Schreibbestätigung für number.py**
   - Implementierung der Rücklesemethode
   - Integration mit Hub-Methoden
   - Tests mit echtem Gerät

2. **Schreibbestätigung für text.py**
   - Implementierung der Rücklesemethode für Zeitwerte
   - Konvertierung zwischen Zeitformat und Registerwert
   - Tests mit echtem Gerät

3. **Statusverifizierung für switch.py**
   - Implementierung der Rücklesemethode
   - Entfernung von `assumed_state=True`
   - Tests mit echtem Gerät

### Phase 2: UX-Verbesserungen (Hoch)
1. **Optimistische Updates**
   - Implementierung für number.py
   - Implementierung für text.py
   - Implementierung für switch.py

2. **Konfigurierbare Standardwerte**
   - Definition in const.py
   - Integration in text.py
   - Optional: Config Flow Erweiterung

### Phase 3: Codequalität (Mittel)
1. **Fehlerbehandlung**
   - Retry-Logik für alle schreibbaren Entities
   - Detailliertes Logging
   - Fehlerbenachrichtigungen

2. **Cooldown-Verbesserungen**
   - Konfigurierbare Cooldowns
   - Unterschiedliche Cooldowns pro Switch-Typ

### Phase 4: Codequalität (Niedrig)
1. **Type Hints**
   - Hinzufügen zu allen Entity-Klassen
   - Verbesserung der IDE-Unterstützung

2. **Dokumentation**
   - Update der README.md
   - Update der CHANGELOG.md
   - Hinzufügen von Beispielen

### Abhängigkeiten

```
Phase 1: Grundlagen
├── number.py Schreibbestätigung
├── text.py Schreibbestätigung
└── switch.py Statusverifizierung

Phase 2: UX-Verbesserungen
├── Optimistische Updates
└── Konfigurierbare Standardwerte

Phase 3: Codequalität
├── Fehlerbehandlung
└── Cooldown-Verbesserungen

Phase 4: Dokumentation
├── Type Hints
└── Dokumentation
```

## Codequalitätsverbesserungen

### Reduzierung von Codeduplizierung

**Problem:** Ähnliche Muster in number.py, text.py und switch.py.

**Lösung:**
- Erstellung einer Basisklasse für schreibbare Entities
- Gemeinsame Methoden für Schreibbestätigung und optimistische Updates

**Implementierung:**
```python
# Neue Datei: base_entity.py
from homeassistant.helpers.entity import Entity

class SajWritableEntity(Entity):
    """Basisklasse für schreibbare SAJ Entities."""
    
    def __init__(self, hub, name, unique_id, device_info):
        self._hub = hub
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._pending_write = False
    
    async def _write_with_confirmation(self, value, write_method, read_method=None):
        """Schreibt einen Wert mit Bestätigung."""
        # Optimistisches Update
        self._pending_write = True
        self.async_write_ha_state()
        
        # Schreiben
        success = await write_method(value)
        if not success:
            _LOGGER.error(f"Failed to write {self._attr_name}: {value}")
            self._pending_write = False
            self.async_write_ha_state()
            return False
        
        # Verifizierung
        if read_method:
            await asyncio.sleep(0.5)
            actual_value = await read_method()
            if actual_value != value:
                _LOGGER.warning(f"Value mismatch for {self._attr_name}: expected {value}, got {actual_value}")
                self._pending_write = False
                self.async_write_ha_state()
                return False
        
        self._pending_write = False
        self.async_write_ha_state()
        return True
```

### Verbesserte Fehlerbehandlung

**Problem:** Inkonsistente Fehlerbehandlung über alle Entities.

**Lösung:**
- Zentralisierte Fehlerbehandlung im Hub
- Einheitliches Logging-Format
- Retry-Logik mit exponentiellem Backoff

### Logging-Verbesserungen

**Problem:** Unterschiedliche Logging-Level und -Formate.

**Lösung:**
- Einheitliches Logging-Format
- Strukturiertes Logging für bessere Analyse
- Debug-Logging für Entwickler

## Rückwärtskompatibilität

### Breaking Changes

Keine Breaking Changes geplant. Alle Änderungen sind abwärtskompatibel.

### Migration

Keine Migration erforderlich. Die Änderungen werden automatisch übernommen.

### Konfiguration

Bestehende Konfigurationen bleiben unverändert. Neue Optionen sind optional.

## Dokumentationsupdates

### Zu aktualisierende Dokumente

1. **README.md**
   - Beschreibung der neuen Schreibbestätigung
   - Erklärung der optimistischen Updates
   - Beispiele für die Konfiguration

2. **CHANGELOG.md**
   - Liste aller Änderungen
   - Versionierung nach SemVer

3. **input-entities.md**
   - Aktualisierung der Entity-Beschreibungen
   - Hinweise zur Schreibbestätigung

4. **Neue Dokumentation**
   - `docs/entity-optimization.md` - Detaillierte Beschreibung der Optimierungen
   - `docs/troubleshooting.md` - Fehlerbehebung bei Schreibproblemen

## Teststrategie

### Unit-Tests

- Tests für alle neuen Methoden
- Mocking von Modbus-Kommunikation
- Tests für Fehlerbehandlung

### Integrationstests

- Tests mit echtem SAJ H2 Wechselrichter
- Tests für Schreibbestätigung
- Tests für optimistische Updates

### Manuelle Tests

- Tests in einer Home Assistant Instanz
- Tests mit verschiedenen Konfigurationen
- Tests für Edge Cases

## Zeitplan

### Phase 1: Grundlagen
- number.py Schreibbestätigung
- text.py Schreibbestätigung
- switch.py Statusverifizierung

### Phase 2: UX-Verbesserungen
- Optimistische Updates
- Konfigurierbare Standardwerte

### Phase 3: Codequalität
- Fehlerbehandlung
- Cooldown-Verbesserungen

### Phase 4: Dokumentation
- Type Hints
- Dokumentationsupdates

## Fazit

Dieser Optimierungsplan verbessert die Zuverlässigkeit und Benutzerfreundlichkeit der SAJ H2 Modbus Integration erheblich. Die Implementierung erfolgt in Phasen, um sicherzustellen, dass jede Änderung gründlich getestet wird, bevor die nächste Phase beginnt.
