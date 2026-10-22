# Konfiguration

> Konfigurationsoptionen und Einstellungen für die SAJ H2 Modbus Integration

---

## 🎛️ Grundkonfiguration

### Ersteinrichtung

Beim ersten Hinzufügen der Integration müssen Sie folgende Pflichtfelder ausfüllen:

| Parameter | Beschreibung | Standardwert | Pflicht |
|-----------|-------------|--------------|---------|
| **Name** | Anzeigename in Home Assistant | SAJ | Nein |
| **IP-Adresse** | IP-Adresse des Wechselrichters | - | Ja |
| **Port** | Modbus TCP Port | 502 | Ja |
| **Scan-Intervall** | Standard-Aktualisierungsintervall (Sekunden) | 60 | Ja |

### IP-Adresse ermitteln

Die IP-Adresse Ihres Wechselrichters finden Sie:

1. **Im Router**: Nach "SAJ" oder der MAC-Adresse suchen
2. **Über die SAJ App**: In den Netzwerkeinstellungen
3. **Via Display**: Am Wechselrichter unter Netzwerk → IP

### Port-Informationen

- **Standard**: 502 (Modbus TCP)
- **Nur ändern**, wenn der Wechselrichter auf einem anderen Port konfiguriert ist
- Port 502 ist der offizielle Modbus TCP Port

---

## ⚡ Erweiterte Konfiguration

Nach der Ersteinrichtung können Sie über **Einstellungen** → **Geräte & Dienste** → **SAJ H2 Modbus** → **Konfigurieren** weitere Optionen festlegen.

### Schnelles Polling (10 Sekunden)

Aktiviert eine schnellere Aktualisierung für kritische Sensoren.

**Wo die 10-Sekunden-Werte erscheinen:** in eigenen *Fast*-Sensoren, z. B.
`sensor.saj_fast_pv_power`, `sensor.saj_fast_battery_power`,
`sensor.saj_fast_grid_load_power`, `sensor.saj_fast_total_load_power`,
`sensor.saj_fast_inverter_power` (insgesamt 21). Die normalen Sensoren wie
`sensor.saj_pv_power` aktualisieren weiter im Haupt-Abfrageintervall und
behalten ihre Langzeitstatistik.

Bei Neuinstallationen sind die Fast-Sensoren **standardmäßig deaktiviert** –
benötigte unter *Einstellungen → Geräte & Dienste → SAJ H2 Modbus → Entitäten*
aktivieren.

**Recorder:** Fast-Sensoren haben keine Langzeitstatistik, ihre Zustände landen
aber wie bei jeder Entität in der Historie-Datenbank – bei aktivem Fast-Polling
alle 10 Sekunden. Wer sie nur für Live-Dashboards braucht, schließt sie aus:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.saj_fast_*
```

(`saj` anpassen, falls die Integration anders benannt wurde.) Die normalen
Sensoren (`sensor.saj_pv_power` …) **nicht** ausschließen – sonst fehlen ihre
Historie und Statistik, auch im Energie-Dashboard.

**Vorteile:**
- Echtzeit-Überwachung
- Schnellere Reaktion in Automatisierungen
- Bessere Visualisierung

**Nachteile:**
- Höhere Netzwerklast
- Mehr CPU-Last auf Home Assistant

**Empfohlene Einstellung:** Aktivieren für Live-Dashboards

### Ultra-Fast MQTT (1 Sekunde)

Publisht Daten an einen MQTT Broker mit 1-Sekunden-Intervall.

**Konfigurationsoptionen:**

| Option | Beschreibung | Standard |
|--------|-------------|----------|
| **MQTT aktivieren** | MQTT-Publishing ein-/ausschalten | Aus |
| **MQTT Broker** | IP/Hostname des MQTT Brokers | - |
| **MQTT Port** | Port des MQTT Brokers | 1883 |
| **MQTT Topic Prefix** | Prefix für alle Topics | `saj_h2/inverter` |

**Topic-Format:**
```
{prefix}/{sensor_name}
# Beispiel:
saj_h2/inverter/pvPower
saj_h2/inverter/batterySOC
```

**Wichtig:** Ultra-Fast wird während Schreiboperationen pausiert, um Datenkonsistenz zu gewährleisten.

---

## 🔋 Ladeeinstellungen

### Time-of-Use Konfiguration

Die Time-of-Use Einstellungen steuern, wann Ihr Wechselrichter aus dem Netz lädt.

**Zugriff über:**
1. **Einstellungen** → **Geräte & Dienste**
2. SAJ H2 Modbus Integration öffnen
3. **Ladeeinstellungen konfigurieren**

**Verfügbare Parameter:**

| Parameter | Beschreibung | Bereich | Standard |
|-----------|-------------|---------|----------|
| **Charge Power Percent** | Ladeleistung in % | 0-100 | 50 |
| **Charge Start Time** | Startzeit (HH:MM) | 00:00-23:59 | 22:00 |
| **Charge End Time** | Endzeit (HH:MM) | 00:00-23:59 | 06:00 |
| **Charge Day Mask** | Wochentage (Bitmask) | 0-127 | 127 |

**Day Mask Berechnung:**
```
Bit 0 = Montag
Bit 1 = Dienstag
Bit 2 = Mittwoch
Bit 3 = Donnerstag
Bit 4 = Freitag
Bit 5 = Samstag
Bit 6 = Sonntag

Beispiel: 127 = Alle Tage (1+2+4+8+16+32+64)
Beispiel: 31 = Werktage (1+2+4+8+16)
```

### Passive Mode Einstellungen

**Wichtige Entities:**

| Entity | Beschreibung | Bereich |
|--------|-------------|---------|
| `number.saj_passive_bat_charge_power` | Batterie Ladeleistung | 0-1000 |
| `number.saj_passive_bat_discharge_power` | Batterie Entladeleistung | 0-1000 |
| `number.saj_passive_grid_charge_power` | Netz Ladeleistung | 0-1000 |
| `number.saj_passive_grid_discharge_power` | Netz Entladeleistung | 0-1000 |
| `switch.saj_passive_charge_control` | Passive Ladung aktivieren | On/Off |
| `switch.saj_passive_discharge_control` | Passive Entladung aktivieren | On/Off |

**Hinweis:** Power-Werte sind in Promille (1000 = 100%) des maximalen Wechselrichter-Outputs.

---

## 🌐 Netzwerk-Konfiguration

### Modbus TCP Verbindung

**Optimale Einstellungen:**
- **Timeout**: 10 Sekunden (Standard)
- **Retries**: 3 Versuche
- **Retry-Delay**: 1 Sekunde

**Diese Einstellungen sind fest codiert und können nicht geändert werden.**

### Verbindungs-Cache

Die Integration verwendet einen Verbindungs-Cache:
- **Cache-TTL**: 60 Sekunden
- **Automatische Wiederverbindung** bei Verbindungsverlust
- **Retry-Logik** mit exponentiellem Backoff

---

## 📊 Polling-Strategie

Die Integration verwendet ein 3-Stufen Polling-System:

### Stufe 1: Standard (60s)
- **Alle Sensoren** werden aktualisiert
- Umfasst alle 390+ Register
- Höchste Datenmenge

### Stufe 2: Fast (10s)
- Nur **FAST_POLL_SENSORS**
- Live-Daten für wichtige Metriken
- Optional aktivierbar

### Stufe 3: Ultra-Fast (1s)
- Nur **FAST_POLL_SENSORS**
- MQTT-Publishing
- Optional, nur wenn MQTT aktiviert

### Priorisierung

**Schreiboperationen haben immer Priorität:**
1. Schreiben (höchste Priorität)
2. Ultra-Fast MQTT
3. Fast Polling
4. Standard Polling

---

## 🔄 Konfiguration ändern

### Optionen nachträglich ändern

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Finden Sie die SAJ H2 Modbus Integration
3. Klicken Sie auf **Konfigurieren**
4. Ändern Sie die gewünschten Optionen
5. Klicken Sie auf **Speichern**

### Integration neu konfigurieren

Falls Sie die IP-Adresse oder andere grundlegende Einstellungen ändern müssen:

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Finden Sie die SAJ H2 Modbus Integration
3. Klicken Sie auf das Menü (⋮) → **Löschen**
4. Fügen Sie die Integration erneut hinzu

**Hinweis:** Alle Historiendaten bleiben erhalten, da sie in der Home Assistant Datenbank gespeichert sind.

---

## 🐛 Fehlerbehebung bei Konfiguration

### Problem: Änderungen werden nicht übernommen

**Lösung:**
- Home Assistant neu starten
- Browser-Cache leeren
- Überprüfen, ob die Änderung in `config_entry` gespeichert wurde

### Problem: Schnelles Polling funktioniert nicht

**Prüfung:**
```bash
# Logs prüfen
ha logs | grep saj_h2_modbus
```

**Mögliche Ursachen:**
- Lock-Konflikte mit Schreiboperationen
- Netzwerk-Latenz zu hoch
- Wechselrichter antwortet zu langsam

### Problem: MQTT Daten kommen nicht an

**Checkliste:**
- [ ] MQTT Broker erreichbar?
- [ ] Port 1883 (oder konfigurierter Port) offen?
- [ ] Topic Prefix korrekt?
- [ ] Home Assistant MQTT Integration eingerichtet?

**Test:**
```bash
# MQTT Subscriber starten
mosquitto_sub -h {broker_ip} -t "saj_h2/inverter/#" -v
```

---

## 📋 Konfigurations-Beispiele

### Beispiel 1: Standard-Setup

```yaml
Name: SAJ
IP-Adresse: 192.168.1.100
Port: 502
Scan-Intervall: 60
Schnelles Polling: Aus
MQTT: Aus
```

### Beispiel 2: Live-Monitoring Setup

```yaml
Name: SAJ Live
IP-Adresse: 192.168.1.100
Port: 502
Scan-Intervall: 60
Schnelles Polling: Ein
MQTT: Ein
MQTT Broker: 192.168.1.10
MQTT Port: 1883
MQTT Topic Prefix: home/saj
```

### Beispiel 3: Nachtladung Setup

```yaml
# Time-of-Use Einstellungen
Charge Start Time: 22:00
Charge End Time: 06:00
Charge Day Mask: 31  # Mo-Fr
Charge Power Percent: 80
```

---

[← Zurück zur Übersicht](README.md) | [Weiter zu Sensoren →](sensors.md)
