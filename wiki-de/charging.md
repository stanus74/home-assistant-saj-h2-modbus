# Lademanagement

> Umfassende Anleitung zu allen Lademodi und -funktionen der SAJ H2 Integration

---

## 🎯 Übersicht

Die SAJ H2 Integration bietet zwei Haupt-Lademodi:

| Modus | Beschreibung | Anwendungsfall |
|-------|-------------|----------------|
| **Time-of-Use** | Zeitbasierte Ladesteuerung | Nachtladung mit günstigem Strom |
| **Passive Mode** | Direkte Leistungsvorgabe | Dynamische PV-Überschuss-Steuerung |

---

## ⚡ Time-of-Use Modus (Self-Consumption)

### Was ist Time-of-Use?

Time-of-Use (ToU) ermöglicht automatisches Laden der Batterie basierend auf konfigurierten Zeitplänen. Ideal für:
- **Nachtladung** mit günstigem Strom
- **Automatisierte Ladezyklen**
- **Zeitvariable Tarife** (z.B. Tibber, Awattar)

Für die Programmierung von Lade-/Entladezeiten empfehle ich die Inverter Loveace Card
> im www Ordner , Install Readme >


### Slot-System (7 Slots)

Der Wechselrichter unterstützt **7 unabhängige Ladezeitpläne**:

```
Slot 1: 22:00 - 06:00 (Nachtladung) - Mo-Fr
Slot 2: 12:00 - 14:00 (Mittagsboost) - Sa,So  
Slot 3: 02:00 - 05:00 (Super-Offpeak) - Täglich
...
```




### Konfiguration

#### Entities für Time-of-Use 

z.b. bei Verwendung in Automationen

| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| `text.saj_charge_start_time` | Text | Startzeit Slot 1 (HH:MM) |
| `text.saj_charge_end_time` | Text | Endzeit Slot 1 (HH:MM) |
| `number.saj_charge_day_mask` | Number | Wochentage Slot 1 (Bitmask) |
| `number.saj_charge_power_percent` | Number | Ladeleistung Slot 1 (0-100%) |
| `text.saj_charge_2_start_time` | Text | Startzeit Slot 2 |
| ... | ... | Slots 3-7 analog |
| `number.saj_charge_time_enable_bitmask` | Number | Master-Enable für alle Charge Slots |
| `number.saj_discharge_time_enable_bitmask` | Number | Master-Enable für alle Discharge Slots |

#### Day Mask Berechnung

Die Day Mask bestimmt, an welchen Wochentagen ein Slot aktiv ist:

```
Bit 0 (Wert 1)   = Montag
Bit 1 (Wert 2)   = Dienstag
Bit 2 (Wert 4)   = Mittwoch
Bit 3 (Wert 8)   = Donnerstag
Bit 4 (Wert 16)  = Freitag
Bit 5 (Wert 32)  = Samstag
Bit 6 (Wert 64)  = Sonntag
```

**Berechnung:**
```python
# Werktage (Mo-Fr)
mask = 1 + 2 + 4 + 8 + 16  # = 31

# Wochenende (Sa-So)
mask = 32 + 64  # = 96

# Jeden Tag
mask = 1 + 2 + 4 + 8 + 16 + 32 + 64  # = 127
```

### Beispielkonfigurationen

#### Beispiel 1: Nachtladung (günstiger Strom)

**Szenario**: Jeden Tag von 22:00 bis 06:00 mit 80% Leistung laden

```yaml
# Slot 1 Konfiguration
text.saj_charge_start_time: "22:00"
text.saj_charge_end_time: "06:00"
number.saj_charge_day_mask: 127  # Jeden Tag
number.saj_charge_power_percent: 80

# Aktivieren
number.saj_charge_time_enable_bitmask: 2  # Bit 1 = Slot 1
```

#### Beispiel 2: Mittagsladung (PV-Überschuss)

**Szenario**: Am Wochenende von 12:00 bis 14:00 mit 100% laden

```yaml
# Slot 2 Konfiguration
text.saj_charge_2_start_time: "12:00"
text.saj_charge_2_end_time: "14:00"
number.saj_charge_2_day_mask: 96  # Sa + So
number.saj_charge_2_power_percent: 100

# Aktivieren (Slot 1 + Slot 2)
number.saj_charge_time_enable_bitmask: 6  # Bits 1+2 = 2+4
```

#### Beispiel 3: Super-Offpeak (sehr günstig)

**Szenario**: In der tieferen Nacht (02:00-05:00) mit maximaler Leistung

```yaml
# Slot 3 Konfiguration
text.saj_charge_3_start_time: "02:00"
text.saj_charge_3_end_time: "05:00"
number.saj_charge_3_day_mask: 31  # Mo-Fr (Werktage)
number.saj_charge_3_power_percent: 100

# Aktivieren
number.saj_charge_time_enable_bitmask: 14  # Slots 1+2+3
```

### AppMode

Für Time-of-Use muss der **AppMode auf 1** (Active Mode) stehen:

- **AppMode = 1**: Time-of-Use aktiv
- **AppMode = 3**: Passive Mode (Time-of-Use wird ignoriert)

Entity: `sensor.saj_app_mode`

---

## 🔋 Passive Mode

### Was ist Passive Mode?

Passive Mode ermöglicht **direkte Leistungssteuerung** ohne Zeitpläne. Sie geben eine feste Leistung vor, die der Wechselrichter einhält.

**Anwendungsfälle:**
- **PV-Überschuss-Steuerung**: Lade nur mit PV-Überschuss
- **Grid-Support**: Unterstützen Sie das Stromnetz
- **Dynamische Tarife**: Reagieren Sie auf Strompreise
- **Notfallmodi**: Manuelle Steuerung in kritischen Situationen

### Entities im Passive Mode

| Entity | Typ | Bereich | Beschreibung |
|--------|-----|---------|-------------|
| `number.saj_passive_bat_charge_power` | Number | 0-1000 | Batterie Ladeleistung |
| `number.saj_passive_bat_discharge_power` | Number | 0-1000 | Batterie Entladeleistung |
| `number.saj_passive_grid_charge_power` | Number | 0-1000 | Netz Ladeleistung |
| `number.saj_passive_grid_discharge_power` | Number | 0-1000 | Netz Entladeleistung |
| `switch.saj_passive_charge_control` | Switch | On/Off | Passive Ladung aktivieren |
| `switch.saj_passive_discharge_control` | Switch | On/Off | Passive Entladung aktivieren |
| `sensor.saj_app_mode` | Sensor | 0-3 | AppMode (muss 3 sein) |

**Wichtig:** Die Werte sind in **Promille** (1000 = 100% der Maximalleistung).

**Bei Verwendung von "sensor.saj_app_mode" werden die Switches nicht benötigt**

### Aktivierung

**Schritt-für-Schritt:**

1. **Leistungswerte setzen** (vor dem Aktivieren!)
   ```yaml
   number.saj_passive_bat_charge_power: 800  # 80% Ladeleistung
   ```

2. **AppMode auf 3 setzen**
   - Der Wechselrichter wechselt in den Passive Mode

3. **Schalter aktivieren**
   ```yaml
   switch.saj_passive_charge_control: on
   ```

### Beispiele

#### Beispiel 1: Konstantes Laden mit 50%

```yaml
number.saj_passive_bat_charge_power: 500  # 50%
switch.saj_passive_charge_control: on
# AppMode automatisch auf 3
```

#### Beispiel 2: Batterie-Entladung für Grid-Support

```yaml
number.saj_passive_bat_discharge_power: 700  # 70% Entladung
switch.saj_passive_discharge_control: on
# AppMode = 3
```




---

## 📊 Ladezustands-Anzeigen

### Wichtige Monitoring-Entities

| Entity | Beschreibung | Hinweis |
|--------|-------------|---------|
| `sensor.saj_battery_soc` | Batterie Ladezustand | 0-100% |
| `sensor.saj_battery_power` | Aktuelle Batterieleistung | Positiv = Laden, Negativ = Entladen |
| `sensor.saj_charge_time_enable` | Aktive Charge Slots | Bitmask-Anzeige |
| `sensor.saj_discharge_time_enable` | Aktive Discharge Slots | Bitmask-Anzeige |
| `sensor.saj_app_mode` | Aktueller AppMode | 1=Active, 3=Passive |

---



## 🔧 Erweiterte Konfiguration

### Export-Limitierung (Anti-Reflux)

Neben dem Lademanagement können Sie auch die Einspeisung ins Netz steuern:

| Entity | Beschreibung |
|--------|-------------|
| `number.saj_export_limit_input` | Export-Limit in % (z.B. 500 = 50%) |


**Anwendung:** Zero-Export oder dynamische Grid-Limits

### Batterie-Limits

Batterie schonen mit Lade-/Entladelimits:

| Entity | Beschreibung |
|--------|-------------|
| `number.saj_battery_charge_power_limit_input` | Max. Ladeleistung |
| `number.saj_battery_discharge_power_limit_input_input` | Max. Entladeleistung |
| `number.saj_battery_on_grid_discharge_depth_input` | Entladetiefe am Netz |
| `number.saj_battery_off_grid_discharge_depth_input` | Entladetiefe Inselbetrieb |

---

## 💡 Best Practices

#
---

[← Zurück zur Übersicht](README.md) | [Weiter zu Fehlerbehebung →](troubleshooting.md)
