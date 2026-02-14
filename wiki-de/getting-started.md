# Schnellstart-Guide

> In 5 Minuten zur ersten Verbindung mit Ihrem SAJ H2 Wechselrichter

---

## ✅ Voraussetzungen

Bevor Sie beginnen, stellen Sie sicher, dass:

- [ ] Sie einen **SAJ H2 Wechselrichter** (8-10 kW) besitzen
- [ ] Der Wechselrichter über **Modbus TCP** erreichbar ist
- [ ] Sie die **IP-Adresse** des Wechselrichters kennen
- [ ] Home Assistant installiert und läuft
- [ ] [HACS](https://hacs.xyz/) ist installiert (empfohlen)

---

## 🚀 Installation in 3 Schritten

### Schritt 1: Integration installieren

**Option A: Über HACS (empfohlen)**
1. Öffnen Sie HACS in Home Assistant
2. Klicken Sie auf "Integrationen"
3. Suchen Sie nach "SAJ H2 Modbus"
4. Klicken Sie auf "Installieren"
5. Starten Sie Home Assistant neu

**Option B: Manuelle Installation**
1. Laden Sie die neueste Version von [GitHub Releases](https://github.com/stanus74/home-assistant-saj-h2-modbus/releases) herunter
2. Entpacken Sie den Ordner `custom_components/saj_h2_modbus`
3. Kopieren Sie ihn in Ihr Home Assistant `custom_components` Verzeichnis
4. Starten Sie Home Assistant neu

### Schritt 2: Integration konfigurieren

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach "SAJ H2 Modbus"
4. Geben Sie die folgenden Daten ein:
   - **IP-Adresse**: z.B. `192.168.1.100`
   - **Port**: `502` (Standard)
   - **Aktualisierungsintervall**: `60` Sekunden (Standard)

### Schritt 3: Verbindung testen

1. Nach der Konfiguration sollten die ersten Sensoren erscheinen
2. Prüfen Sie unter **Entwickler-Tools** → **Zustände**
3. Suchen Sie nach `sensor.saj_` Entities
4. Wenn Werte angezeigt werden → **Erfolg!** 🎉

---

## 📊 Erste Schritte

### Wichtige Sensoren finden

Die wichtigsten Sensoren für den Einstieg:

| Sensor | Entity ID | Bedeutung |
|--------|-----------|-----------|
| PV Leistung | `sensor.saj_pv_power` | Aktuelle PV-Produktion in Watt |
| Batterie SOC | `sensor.saj_battery_soc` | Ladezustand in % |
| Batterie Leistung | `sensor.saj_battery_power` | Laden/Entladen in Watt |
| Netz Leistung | `sensor.saj_grid_power` | Bezug/Einspeisung in Watt |
| Last Leistung | `sensor.saj_total_load_power` | Hausverbrauch in Watt |

### Dashboard erstellen

Erstellen Sie eine neue Lovelace-Karte:

```yaml
type: entities
title: SAJ H2 Übersicht
entities:
  - entity: sensor.saj_pv_power
    name: PV Produktion
  - entity: sensor.saj_battery_soc
    name: Batterie SOC
  - entity: sensor.saj_battery_power
    name: Batterie Leistung
  - entity: sensor.saj_grid_power
    name: Netz Leistung
  - entity: sensor.saj_total_load_power
    name: Hausverbrauch
```

---

## ⚡ Schnelle Konfigurationen

### 1. Schnelles Polling aktivieren (10 Sekunden)

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Finden Sie die SAJ H2 Modbus Integration
3. Klicken Sie auf **Konfigurieren**
4. Aktivieren Sie **Schnelles Polling (10s)**
5. Speichern Sie

**Wichtige Sensoren mit schnellem Polling:**
- PV Power
- Battery Power
- Grid Power
- Total Load Power

### 2. MQTT für Echtzeit-Daten (1 Sekunde)

Wenn Sie MQTT in Home Assistant eingerichtet haben:

1. Konfigurieren Sie den MQTT-Broker in der Integration
2. Die Daten werden automatisch gepublisht
3. Topic-Format: `saj_h2/inverter/{sensor_name}`

---

## 🎯 Nächste Schritte

- [Lernen Sie das Lademanagement kennen →](charging.md)
- [Alle Sensoren erkunden →](sensors.md)
- [Erste Automatisierung erstellen →](advanced/automations.md)

---

## ❓ Probleme?

Wenn etwas nicht funktioniert:

1. **Keine Verbindung?** → Prüfen Sie IP-Adresse und Port
2. **Keine Sensoren?** → Warten Sie 1-2 Minuten nach dem Start
3. **Falsche Werte?** → Überprüfen Sie das Inverter-Modell

[→ Zur Fehlerbehebung](troubleshooting.md)

---

## 📚 Weiterführende Links

- [Ausführliche Installationsanleitung](installation.md)
- [Vollständige Konfigurationsoptionen](configuration.md)
- [Alle verfügbaren Sensoren](sensors.md)
