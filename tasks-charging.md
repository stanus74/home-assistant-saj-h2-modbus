# Task: Separation of Switch and Number Logic for Passive Charge Control

**Ziel:** Separierung der AppMode-Logik zwischen Switches und Number-Entities.

**Priorität:** HIGH  
**Geschätzter Aufwand:** 1-2 Stunden  
**Status:** IN PROGRESS (Tasks 1 & 2 completed)

---

## Problemstellung

Aktuell verwenden sowohl Switches (`passive_charge`/`passive_discharge`) als auch die Number-Entity (`passive_charge_enable`) dieselbe Methode `_handle_passive_mode()` in `charge_control.py`, die immer den AppMode ändert.

**Gewünschtes Verhalten:**

**Switches - AppMode wird automatisch gesteuert:**
- **Gruppe A** (`charging`, `discharging`): AppMode = **1** (Force Charge/Discharge) bei Aktivierung
- **Gruppe B** (`passive_charge`, `passive_discharge`): AppMode = **3** (Passive) bei Aktivierung
- Bei Deaktivierung: Rückkehr zum vorherigen/von den States berechneten AppMode

**Number-Entities - Kein AppMode-Wechsel:**
- `passive_charge_enable`: Nur Register 0x3636 schreiben (0=Standby, 1=Discharge, 2=Charge)
- AppMode bleibt unverändert (z.B. 3 für Passive Mode)

---

## Task 1: Neue Methode `_handle_simple_passive_charge()` erstellen ✅ COMPLETED

**Datei:** `custom_components/saj_h2_modbus/charge_control.py`

### 1.1 Methode implementieren ✅ DONE

Methode wurde nach `_deactivate_passive_mode()` (Zeile 400) hinzugefügt.

**Implementierung:**
```python
async def _handle_simple_passive_charge(self, value: int) -> None:
    """Handle passive_charge_enable via number entity - NO AppMode change.
    
    This method only writes to register 0x3636 without changing AppMode.
    Used by number entities to allow free switching between 
    0=Standby, 1=Discharge, 2=Charge while staying in Passive Mode.
    """
    if value is None:
        return

    desired_int = int(value)
    addr = MODBUS_ADDRESSES["simple_settings"]["passive_charge_enable"]["address"]

    try:
        if await self._write_register_with_backoff(addr, desired_int, "passive charge enable"):
            self._update_cache({"passive_charge_enable": desired_int})
            _LOGGER.debug("Passive charge enable set to %s (no AppMode change)", desired_int)
    finally:
        self._clear_pending_state("passive_charge_enable")
        self.hub.async_set_updated_data(self.hub.inverter_data)
```

**Akzeptanzkriterien:**
- [x] Methode existiert und hat korrekte Signatur
- [x] Schreibt nur Register 0x3636
- [x] Ruft KEINE AppMode-ändernden Methoden auf
- [x] Update Cache und UI korrekt
- [x] Logging vorhanden

---

## Task 2: `_handle_simple_setting()` anpassen ✅ COMPLETED

**Datei:** `custom_components/saj_h2_modbus/charge_control.py`

### 2.1 Aufruf ändern ✅ DONE

Geändert bei Zeile 227-230:

**Alt:**
```python
if key == "passive_charge_enable":
    await self._handle_passive_mode(value)
    return
```

**Neu:**
```python
# Number entities should NOT change AppMode - only write register
if key == "passive_charge_enable":
    await self._handle_simple_passive_charge(value)
    return
```

**Akzeptanzkriterien:**
- [x] `_handle_simple_passive_charge()` wird aufgerufen
- [x] `return` statement vorhanden (verhindert doppelte Verarbeitung)
- [x] `_handle_passive_mode()` wird für Number-Entities NICHT mehr aufgerufen

---

## Task 3: Switches-Verhalten verifizieren

**Datei:** `custom_components/saj_h2_modbus/switch.py`

### 3.1 Zwei Switch-Gruppen analysieren

In `switch.py` existieren **zwei Gruppen** von Switches:

**Gruppe A: Normale Charging/Discharging** (`charging`, `discharging`)
```python
# Verwenden set_charging() / set_discharging()
setter = getattr(self._hub, f"set_{self._switch_type}", None)
await setter(desired_state)
```
- AppMode sollte auf **1** (Force Charge/Discharge) gesetzt werden
- Prüfung in `_is_power_state_active()` auf AppMode == 1 (Zeile 191)

**Gruppe B: Passive Switches** (`passive_charge`, `passive_discharge`)
```python
# Verwenden _handle_passive_mode_state() → set_passive_mode()
target_value = PASSIVE_MODE_TARGETS[self._switch_type] if desired_state else 0
await hub_method(target_value)
```
- AppMode sollte auf **3** (Passive) gesetzt werden
- `_handle_passive_mode()` in charge_control.py setzt AppMode = 3

### 3.2 Verhalten verifizieren

Beide Switch-Gruppen verwenden weiterhin ihre bestehenden Methoden und sollten AppMode automatisch steuern:

**Das ist korrekt!** Keine Änderung an der Switch-Logik nötig.

**Akzeptanzkriterien:**
- [ ] Gruppe A (charging/discharging): AppMode = 1 bei Aktivierung
- [ ] Gruppe B (passive_charge/passive_discharge): AppMode = 3 bei Aktivierung
- [ ] Bei Deaktivierung: Rückkehr zum vorherigen/von den States berechneten AppMode
- [ ] Keine Änderung an Switch-Logik nötig

---

## Task 4: Testing

### 4.1 Test-Szenarien definieren

**Test 1: Switch Gruppe A - Charging/Discharging (unverändert)**
```yaml
Action: Switch "Charging Control" einschalten
Erwartet:
  - Register charging_enabled Bit wird gesetzt
  - AppMode = 1 (Force Charge/Discharge)

Action: Switch "Charging Control" ausschalten
Erwartet:
  - Register charging_enabled Bit wird zurückgesetzt
  - AppMode = vorheriger/von States berechneter Modus
```

**Test 2: Switch Gruppe B - Passive Charge/Discharge (unverändert)**
```yaml
Action: Switch "Passive Charge" einschalten
Erwartet: 
  - Register 0x3636 = 2 (Charge)
  - AppMode = 3 (Passive)

Action: Switch "Passive Charge" ausschalten
Erwartet:
  - Register 0x3636 = 0 (Standby)
  - AppMode = vorheriger/von States berechneter Modus

**Test 3: Number-Entity (NEU - kein AppMode-Wechsel)**
```yaml
Voraussetzung: AppMode = 3 (Passive)

Action: Number "Passive Charge Enable" auf 0 setzen
Erwartet:
  - Register 0x3636 = 0
  - AppMode = 3 (unverändert!)

Action: Number "Passive Charge Enable" auf 2 setzen
Erwartet:
  - Register 0x3636 = 2
  - AppMode = 3 (unverändert!)
```

**Test 4: Benutzer-Szenario (jsjhb)**
```yaml
Automation:
  1. Setze AppMode = 3 (Passive)
  2. Setze Passive Battery Charge Power = X
  3. Setze Passive Charge Enable = 2 (Charge)
  4. Warte bis SOC 100%
  5. Setze Passive Charge Enable = 0 (Standby)

Erwartet:
  - Schritt 5 ändert AppMode NICHT
  - Inverter bleibt im Passive Mode
```

### 4.2 Log-Verifizierung

Aktiviere DEBUG-Logging in `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.saj_h2_modbus.charge_control: debug
```

**Erwartete Log-Einträge:**
- Bei Number-Änderung: `"Passive charge enable set to X (no AppMode change)"`
- Bei Switch-Aktivierung: `"Activating passive mode, capturing current AppMode"`
- Bei Switch-Deaktivierung: `"Deactivating passive mode, restoring AppMode X"`

---

## Task 5: Dokumentation

### 5.1 CHANGELOG.md aktualisieren

Füge unter "[Unreleased]" hinzu:
```markdown
### Fixed
- **Passive Charge Enable Number Entity**: Setting the number entity no longer automatically changes AppMode. Users can now freely switch between Standby (0), Discharge (1), and Charge (2) while remaining in Passive Mode (3).
- **Switch Behavior Preserved**: 
  - Charging/Discharging switches: AppMode = 1 (Force Charge/Discharge) on activation
  - Passive Charge/Discharge switches: AppMode = 3 (Passive) on activation
  - All switches restore previous mode on deactivation
```

### 5.2 README aktualisieren (optional)

Falls es eine Dokumentation für die Entitäten gibt, ergänze:
- Number `passive_charge_enable`: "Controls charging state within Passive Mode without changing AppMode"
- Switches: "Enable/disable passive charging/discharging with automatic AppMode management"

---

## Implementierungs-Reihenfolge

```
1. Task 1.1: Neue Methode _handle_simple_passive_charge() erstellen
2. Task 2.1: _handle_simple_setting() anpassen
3. Task 3.1: Switches-Verhalten verifizieren (nur prüfen, keine Änderung)
4. Task 4: Testing durchführen
5. Task 5: Dokumentation aktualisieren
```

---

## Code-Änderungen Übersicht

| Datei | Änderung | Zeilen |
|-------|----------|--------|
| `charge_control.py` | Neue Methode `_handle_simple_passive_charge()` | ~25 Zeilen hinzufügen |
| `charge_control.py` | `_handle_simple_setting()` anpassen | 2 Zeilen ändern |
| `CHANGELOG.md` | Dokumentation | ~5 Zeilen hinzufügen |

**Gesamt:** ~32 Zeilen geändert/hinzugefügt

---

## Risiken und Abhängigkeiten

**Risiken:**
- ⚠️ Number-Entity ändert sich jetzt anders als in v2.8.0/v2.8.1 (könnte Nutzer verwirren, die sich an altes Verhalten gewöhnt haben)
- ⚠️ Falls Automationen auf AppMode-Änderung nach Number-Update warten, müssen sie angepasst werden

**Abhängigkeiten:**
- Keine Breaking Changes für Switches
- Number-Entity braucht jetzt zusätzlichen Schritt (AppMode selbst setzen wenn gewünscht)

---

## Akzeptanzkriterien Gesamt

- [ ] Number-Entity `passive_charge_enable` ändert AppMode NICHT mehr
- [ ] Gruppe A Switches (`charging`/`discharging`): AppMode = 1 bei Aktivierung
- [ ] Gruppe B Switches (`passive_charge`/`passive_discharge`): AppMode = 3 bei Aktivierung
- [ ] Bei Deaktivierung aller Switches: Rückkehr zu vorherigem/von States berechnetem AppMode
- [ ] Benutzer kann im Passive Mode zwischen Standby/Charge/Discharge wechseln ohne AppMode-Reset
- [ ] Alle Tests erfolgreich
- [ ] CHANGELOG.md aktualisiert

---

**Letzte Aktualisierung:** 2026-02-13  
**Autor:** AI Assistant  
**Basierend auf:** GitHub Issue #XXX (jsjhb's Problem mit Parallel-Invertern)
