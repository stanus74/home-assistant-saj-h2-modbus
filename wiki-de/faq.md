# FAQ - Häufig gestellte Fragen

> Antworten auf die häufigsten Fragen zur SAJ H2 Modbus Integration

---

## 🚀 Allgemeine Fragen

### Q: Ist diese Integration offiziell von SAJ?

**A:** Nein, dies ist eine **inoffizielle Community-Integration**. Sie wurde durch Reverse Engineering der Modbus-Register entwickelt und ist nicht von SAJ autorisiert oder unterstützt. Die Nutzung erfolgt auf eigene Gefahr.

### Q: Welche Wechselrichter werden unterstützt?

**A:** Die Integration unterstützt:
- **SAJ H2** Inverter (8kW, 10kW)
- **SAJ HS2** Inverter
- **Ampere Solar** (EKD-Solar) - nutzen SAJ HS2 Hardware

**Nicht unterstützt:**
- Andere SAJ Serien (R5, Sununo, etc.)
- Nicht-SAJ Wechselrichter

### Q: Ist die Nutzung kostenlos?

**A:** Ja, die Integration ist Open Source und kostenlos unter der MIT Lizenz verfügbar. Es gibt keine versteckten Kosten oder Abonnements.

### Q: Werde ich durch Updates ausgesperrt?

**A:** Nein, da dies eine lokale Integration ist, gibt es keine Cloud-Abhängigkeiten. Sie haben volle Kontrolle über die Software.

---

## ⚙️ Technische Fragen

### Q: Wie oft werden die Daten aktualisiert?

**A:** Die Integration verwendet ein 3-Stufen System:

| Modus | Intervall | Sensoren |
|-------|-----------|----------|
| **Standard** | 60 Sekunden | Alle 390+ Sensoren |
| **Schnell** | 10 Sekunden | 6 wichtige Sensoren (optional) |
| **Ultra-Fast** | 1 Sekunde | MQTT-Publishing (optional) |

### Q: Kann ich mehrere Wechselrichter nutzen?

**A:** Ja, Sie können die Integration mehrfach installieren:
1. Erste Integration mit IP 192.168.1.100
2. Zweite Integration mit IP 192.168.1.101
3. Jede Integration hat eigenen Namen und Entities

### Q: Was passiert bei Verbindungsverlust?

**A:** Die Integration hat einen robusten Wiederverbindungsmechanismus:
- Automatische Wiederverbindung nach Verbindungsverlust
- Retry-Logik mit exponentiellem Backoff
- Entities zeigen "unavailable" während der Unterbrechung
- Nach Wiederverbindung: normale Aktualisierung

### Q: Ist Modbus TCP sicher?

**A:** Modbus TCP selbst hat keine Verschlüsselung. Für zusätzliche Sicherheit:
- Nutzen Sie ein separates IoT-VLAN
- Firewall-Regeln für Port 502
- VPN für Fernzugriff

---

## 🔋 Lade-Management Fragen

### Q: Was ist der Unterschied zwischen Time-of-Use und Passive Mode?

**A:**

| Feature | Time-of-Use | Passive Mode |
|---------|-------------|--------------|
| **Steuerung** | Zeitbasiert | Direkte Leistungsvorgabe |
| **Nutzen** | Automatisches Nachtladen | Dynamische Steuerung |
| **AppMode** | 1 (Active) | 3 (Passive) |
| **Szenario** | Günstiger Nachtstrom | PV-Überschuss, Grid-Support |

### Q: Was bedeutet "AppMode"?

**A:** AppMode bestimmt den Betriebsmodus des Wechselrichters:

- **0**: Standby
- **1**: Active Mode (Time-of-Use, normale Operation)
- **2**: Standby
- **3**: Passive Mode (Direkte Leistungssteuerung)

**Wichtig:** Für aktives Laden muss AppMode = 1 sein, für Passive Mode AppMode = 3.

### Q: Wie funktioniert der Passive Mode?

**A:** Passive Mode erlaubt direkte Vorgabe der Lade-/Entladeleistung:

1. **Leistung einstellen**:
   - `number.saj_passive_bat_charge_power` = 800 (80%)
   
2. **Mode aktivieren**:
   - AppMode auf 3 setzen
   - `switch.saj_passive_charge_control` = ON

3. **Ergebnis**: Batterie lädt mit 80% der maximalen Leistung

**Anwendungsfälle:**
- Dynamische Strompreis-Optimierung
- Grid-Support (Netzstabilisierung)
- PV-Überschuss-Steuerung

### Q: Was ist der Unterschied zwischen 0x3604 und 0x3605?

**A:**

| Register | Name | Funktion |
|----------|------|----------|
| **0x3604** | Charge Time Enable | Bitmaske für Lade-Zeitslots |
| **0x3605** | Discharge Time Enable | Bitmaske für Entlade-Zeitslots |

**Bit-Layout** (für beide Register):
```
Bit 0: Charging/Discharging State (1 = aktiv)
Bit 1-6: Slot 1-7 Enable (1 = aktiviert)
Bit 7: Reserved

Beispiel: 0x0F = Slots 1,2,3,4 aktiviert
```

### Q: Warum werden manche Sensoren als "unavailable" angezeigt?

**A:** Mögliche Ursachen:

1. **Initialisierung**: Nach Neustart 1-2 Minuten warten
2. **Nicht unterstützt**: Ihr Wechselrichter unterstützt diesen Sensor nicht
3. **Lesefehler**: Temporäre Modbus-Kommunikationsprobleme
4. **Deaktiviert**: Entity ist in Home Assistant deaktiviert

---

## 🔧 Konfigurations-Fragen

### Q: Wie finde ich die IP-Adresse meines Wechselrichters?

**A:** Mehrere Methoden:

1. **Router-Webinterface**: Nach "SAJ" oder der MAC-Adresse suchen
2. **SAJ App**: Netzwerkeinstellungen im Menü
3. **Display**: Am Wechselrichter → Netzwerk → IP-Adresse
4. **Netzwerk-Scanner**: Tools wie Fing, nmap

### Q: Was ist die beste Scan-Rate?

**A:** Empfehlungen:

- **Standard-Nutzung**: 60 Sekunden (Standard)
- **Live-Monitoring**: 60s Standard + 10s Schnell-Polling
- **Echtzeit-Daten**: + 1s MQTT für ausgewählte Sensoren
- **Fernzugriff/VPN**: 120 Sekunden (weniger Last)

### Q: Kann ich Sensoren deaktivieren, die ich nicht brauche?

**A:** Ja:
1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Wählen Sie die SAJ Integration
3. Klicken Sie auf **Entities**
4. Wählen Sie das Entity aus
5. Klicken Sie auf **Einstellungen** (Zahnrad)
6. Deaktivieren Sie "Entity aktiviert"

---

## 📊 Daten-Fragen

### Q: Welche Daten werden gespeichert?

**A:** Alle Sensor-Daten werden in der Home Assistant Datenbank gespeichert:
- Standardmäßig 10 Tage (recorder Konfiguration)
- Konfigurierbar in `configuration.yaml`
- Langzeitspeicherung mit InfluxDB möglich

### Q: Kann ich die Daten exportieren?

**A:** Ja, mehrere Möglichkeiten:

1. **Home Assistant**: Entwickler-Tools → Statistiken → Export
2. **MariaDB**: Direkter Datenbankzugriff
3. **InfluxDB**: Zeitserien-Datenbank
4. **MQTT**: Echtzeit-Export an externe Systeme

### Q: Wie genau sind die Daten?

**A:** Die Genauigkeit hängt vom Sensor ab:

- **Spannung/Ströme**: ±0.1% (hochgenau)
- **Leistung**: ±1% (gut)
- **Energie**: ±2% (akkumulierte Werte)
- **Temperaturen**: ±1°C

---

## 🏠 Home Assistant Fragen

### Q: Funktioniert die Integration mit Home Assistant Cloud?

**A:** Ja, alle Features funktionieren mit Home Assistant Cloud:
- Fernzugriff auf alle Sensoren
- Alexa/Google Assistant Integration
- Mobile App Anzeige

**Hinweis:** Modbus-Kommunikation bleibt lokal!

### Q: Kann ich die Integration in Automatisierungen nutzen?

**A:** Absolut! Beispiele:

```yaml
# Nachtladung
automation:
  - alias: "SAJ Nachtladung"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.saj_charge_power_percent
        data:
          value: 80
```

[→ Mehr Automatisierungsbeispiele](advanced/automations.md)

### Q: Gibt es ein fertiges Dashboard?

**A:** Ja, mehrere Optionen:

1. **Custom Lovelace Card**: [saj-h2-lovelace-card](https://github.com/stanus74/saj-h2-lovelace-card)
2. **ApexCharts**: Für detaillierte Diagramme
3. **Standard Entities Card**: Schnell eingerichtet
4. **Community Dashboards**: Im Forum zu finden

---

## 🆘 Fehlerbehebung

### Q: Wie debugge ich Verbindungsprobleme?

**A:** Schritt-für-Schritt:

1. **Ping testen**:
   ```bash
   ping 192.168.1.100
   ```

2. **Port testen**:
   ```bash
   nc -zv 192.168.1.100 502
   ```

3. **Logs prüfen**:
   ```bash
   ha logs | grep saj_h2_modbus
   ```

4. **Modbus direkt testen** (optional):
   ```bash
   python -c "from pymodbus.client import ModbusTcpClient; c=ModbusTcpClient('192.168.1.100'); c.connect(); print(c.read_holding_registers(0x100, 1).registers)"
   ```

[→ Detaillierte Fehlerbehebung](troubleshooting.md)

### Q: Wo finde ich die Logs?

**A:** Mehrere Wege:

1. **Terminal**:
   ```bash
   ha logs follow | grep saj_h2_modbus
   ```

2. **Home Assistant UI**:
   - Einstellungen → System → Logs
   - Nach "saj_h2_modbus" filtern

3. **Datei** (Container/Core):
   ```
   /config/home-assistant.log
   ```

---

## 🤝 Community & Support

### Q: Wie kann ich zur Entwicklung beitragen?

**A:** Mehrere Möglichkeiten:

1. **Bug Reports**: [GitHub Issues](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
2. **Feature Requests**: [Discussions](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
3. **Code**: Pull Requests willkommen!
4. **Dokumentation**: Wiki verbessern
5. **Testen**: Neue Versionen testen und Feedback geben

### Q: Gibt es ein Forum oder Chat?

**A:** Ja:
- [GitHub Discussions](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
- [Home Assistant Forum](https://community.home-assistant.io/)

### Q: Ist kommerzieller Support verfügbar?

**A:** Nein, dies ist ein rein Community-getriebenes Projekt. Es gibt keinen kommerziellen Support. Für professionelle Unterstützung empfehlen wir:
- Elektrofachbetriebe
- SAJ direkt (für Hardware-Probleme)
- Home Assistant Dienstleister

---

## 💡 Tipps & Tricks

### Q: Was sind die besten Einstellungen für Anfänger?

**A:** Empfohlene Startkonfiguration:
- Scan-Intervall: 60 Sekunden
- Schnelles Polling: EIN (für bessere UX)
- MQTT: AUS (erst wenn benötigt)
- Time-of-Use: Ein Slot für Nachtladung konfigurieren

### Q: Wie optimiere ich die Performance?

**A:** Tipps:
- LAN statt WLAN verwenden
- Statische IP für den Wechselrichter
- Schnelles Polling nur bei Bedarf
- Nicht benötigte Entities deaktivieren
- Home Assistant auf SSD statt SD-Karte

### Q: Was ist der beste Weg, um Stromkosten zu sparen?

**A:** Strategien:
1. **Time-of-Use**: Nachtladung mit günstigem Strom
2. **PV-Überschuss**: Selbstverbrauch maximieren
3. **Dynamische Tarife**: Tibber/Awattar Integration
4. **Passive Mode**: Grid-Support für Vergütung

---

Ihre Frage nicht gefunden? [Stellen Sie sie in den Discussions!](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)

[← Zurück zur Übersicht](README.md)
