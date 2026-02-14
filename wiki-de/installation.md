# Installation

> Detaillierte Installationsanleitung für die SAJ H2 Modbus Integration

---

## 📥 Voraussetzungen

### Hardware
- SAJ H2 Wechselrichter (8kW oder 10kW)
- Netzwerkverbindung zum Wechselrichter
- Home Assistant Instanz (OS, Container, Core oder Supervised)

### Software
- Home Assistant ab Version 2023.x
- [HACS](https://hacs.xyz/) (empfohlen, aber optional)
- Netzwerk-Zugriff auf Port 502 (Modbus TCP)

### Netzwerk-Konfiguration
- Statische IP-Adresse für den Wechselrichter empfohlen
- Port 502 muss erreichbar sein
- Keine Firewall-Regeln die Modbus TCP blockieren

---

## 🔧 Installationsmethoden

### Methode 1: HACS (Empfohlen)

Die einfachste Methode zur Installation:

1. **HACS öffnen**
   - Gehen Sie zu HACS im Home Assistant Seitenmenü
   - Klicken Sie auf "Integrationen"

2. **Integration suchen**
   - Klicken Sie auf das "+" Symbol unten rechts
   - Suchen Sie nach "SAJ H2 Modbus"

3. **Installieren**
   - Klicken Sie auf "SAJ H2 Inverter Modbus"
   - Wählen Sie die neueste Version
   - Klicken Sie auf "Installieren"

4. **Neu starten**
   - Starten Sie Home Assistant neu
   - Warten Sie, bis alle Dienste gestartet sind

### Methode 2: Manuelle Installation

Wenn Sie HACS nicht nutzen möchten:

1. **Neueste Version herunterladen**
   ```bash
   # Über GitHub CLI
   gh release download --repo stanus74/home-assistant-saj-h2-modbus --latest
   
   # Oder manuell von:
   # https://github.com/stanus74/home-assistant-saj-h2-modbus/releases
   ```

2. **Dateien entpacken**
   - Entpacken Sie das Archiv
   - Navigieren Sie zu `custom_components/saj_h2_modbus`

3. **In Home Assistant kopieren**
   - Kopieren Sie den Ordner `saj_h2_modbus` nach:
     - Home Assistant OS/Supervised: `/config/custom_components/`
     - Home Assistant Container: `/config/custom_components/`
     - Home Assistant Core: `.homeassistant/custom_components/`

4. **Neu starten**
   - Starten Sie Home Assistant neu

### Methode 3: Git Clone (Für Entwickler)

```bash
# Navigieren Sie zum custom_components Verzeichnis
cd /config/custom_components

# Repository klonen
git clone https://github.com/stanus74/home-assistant-saj-h2-modbus.git saj_h2_modbus

# Home Assistant neu starten
```

---

## ⚙️ Erstkonfiguration

### Schritt 1: Integration hinzufügen

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach "SAJ H2 Modbus"
4. Klicken Sie auf die Integration

### Schritt 2: Verbindungsdaten eingeben

| Parameter | Beschreibung | Standard | Beispiel |
|-----------|-------------|----------|----------|
| **Name** | Frei wählbarer Name | SAJ | Mein Wechselrichter |
| **IP-Adresse** | IP des Wechselrichters | - | 192.168.1.100 |
| **Port** | Modbus TCP Port | 502 | 502 |
| **Scan-Intervall** | Aktualisierung in Sekunden | 60 | 60 |

### Schritt 3: Erweiterte Optionen (Optional)

Nach der ersten Einrichtung können Sie weitere Optionen konfigurieren:

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Finden Sie die SAJ H2 Modbus Integration
3. Klicken Sie auf **Konfigurieren**

**Verfügbare Optionen:**

- **Schnelles Polling (10s)**: Aktiviert 10-Sekunden-Aktualisierung für wichtige Sensoren
- **MQTT aktivieren**: Publisht Daten an einen MQTT Broker
- **MQTT Broker**: Adresse des MQTT Brokers (optional)
- **MQTT Port**: Port des MQTT Brokers (Standard: 1883)
- **MQTT Topic Prefix**: Prefix für MQTT Topics

---

## ✅ Installation verifizieren

### 1. Entities prüfen

1. Gehen Sie zu **Entwickler-Tools** → **Zustände**
2. Geben Sie im Suchfeld `saj_` ein
3. Es sollten mehrere Entities erscheinen:
   - `sensor.saj_pv_power`
   - `sensor.saj_battery_soc`
   - `sensor.saj_grid_power`
   - Und viele mehr...

### 2. Protokolle prüfen

```bash
# Home Assistant Logs anzeigen
ha logs follow | grep saj_h2_modbus
```

Sie sollten Meldungen wie diese sehen:
```
INFO (MainThread) [custom_components.saj_h2_modbus] SAJ H2 Modbus integration starting
INFO (MainThread) [custom_components.saj_h2_modbus.hub] Connected to SAJ inverter at 192.168.1.100
```

### 3. Gerät anzeigen

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Klicken Sie auf die SAJ H2 Modbus Integration
3. Es sollte ein Gerät mit allen Sensoren angezeigt werden

---

## 🔄 Aktualisierung

### Über HACS

1. Gehen Sie zu HACS → Integrationen
2. Finden Sie "SAJ H2 Inverter Modbus"
3. Klicken Sie auf "Aktualisieren", falls verfügbar
4. Starten Sie Home Assistant neu

### Manuelle Aktualisierung

1. Laden Sie die neueste Version herunter
2. Ersetzen Sie den Ordner `custom_components/saj_h2_modbus`
3. Starten Sie Home Assistant neu

---

## ❌ Deinstallation

### Über HACS

1. Gehen Sie zu HACS → Integrationen
2. Finden Sie "SAJ H2 Inverter Modbus"
3. Klicken Sie auf das Menü (⋮) → "Löschen"
4. Starten Sie Home Assistant neu

### Manuell

1. Löschen Sie den Ordner `custom_components/saj_h2_modbus`
2. Starten Sie Home Assistant neu

---

## 🐛 Bekannte Installationsprobleme

### Problem: "Integration nicht gefunden"

**Lösung:**
- Browser-Cache leeren
- Home Assistant neu starten
- Prüfen, ob der Ordner korrekt kopiert wurde

### Problem: "Verbindung fehlgeschlagen"

**Lösung:**
- IP-Adresse und Port prüfen
- Ping zum Wechselrichter testen: `ping 192.168.1.100`
- Firewall-Regeln prüfen
- Modbus TCP am Wechselrichter aktivieren

### Problem: "Keine Entities angezeigt"

**Lösung:**
- 2-3 Minuten warten (erste Abfrage dauert länger)
- Logs prüfen auf Fehlermeldungen
- Wechselrichter-Modell prüfen (nur H2/HS2 unterstützt)

---

## 📞 Support

Bei Installationsproblemen:
- [GitHub Issues erstellen](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
- [Home Assistant Forum](https://community.home-assistant.io/)
- [Fehlerbehebungs-Guide →](troubleshooting.md)
