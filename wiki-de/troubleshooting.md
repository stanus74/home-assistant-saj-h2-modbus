# Fehlerbehebung (Troubleshooting)

> Lösungen für häufige Probleme mit der SAJ H2 Modbus Integration

---

## 🔍 Schnell-Diagnose

Bevor Sie mit der Fehlerbehebung beginnen, sammeln Sie folgende Informationen:

1. **Home Assistant Version**: Einstellungen → Info
2. **Integrations-Version**: HACS → Integrationen
3. **Wechselrichter-Modell**: Ist es ein SAJ H2 oder HS2?
4. **Netzwerk-Verbindung**: Funktioniert ein Ping zur IP?
5. **Fehlermeldungen**: Was steht in den Logs?

**Logs anzeigen:**
```bash
ha logs follow | grep saj_h2_modbus
```

---

## ❌ Verbindungsprobleme

### Problem: "Connection refused"

**Symptome:**
- Integration zeigt "Nicht verfügbar"
- Logs zeigen "Connection refused"

**Ursachen & Lösungen:**

1. **Falsche IP-Adresse**
   ```bash
   # IP-Adresse prüfen
   ping 192.168.1.100
   
   # Port erreichbar?
   nc -zv 192.168.1.100 502
   ```

2. **Modbus TCP nicht aktiviert**
   - Überprüfen Sie die Wechselrichter-Einstellungen
   - Modbus TCP muss aktiviert sein
   - Port 502 muss offen sein

3. **Firewall blockiert**
   - Router-Firewall prüfen
   - Port 502 freigeben
   - VLAN-Konfiguration checken

### Problem: "Timeout"

**Symptome:**
- Verbindung wird hergestellt, aber Daten kommen nicht
- Zeitüberschreitung bei Modbus-Abfragen

**Lösungen:**

1. **Netzwerk-Latenz prüfen**
   ```bash
   ping 192.168.1.100 -c 10
   ```
   - Akzeptabel: < 50ms
   - Problem ab: > 100ms

2. **Scan-Intervall erhöhen**
   - Gehen Sie zu den Integrations-Einstellungen
   - Erhöhen Sie das Scan-Intervall auf 120 Sekunden
   - Testen Sie die Verbindung

3. **Wechselrichter überlastet**
   - Reduzieren Sie die Anzahl der parallelen Abfragen
   - Deaktivieren Sie schnelles Polling temporär

### Problem: "No route to host"

**Symptome:**
- Ping funktioniert nicht
- Keine Netzwerk-Verbindung

**Lösungen:**

1. **Netzwerk-Verbindung prüfen**
   - Ist der Wechselrichter mit dem Netzwerk verbunden?
   - Netzwerk-Kabel prüfen
   - WLAN-Verbindung (falls genutzt) testen

2. **IP-Konfiguration**
   - Statische IP empfohlen
   - DHCP-Leases prüfen
   - IP-Adresse am Display des Wechselrichters verifizieren

---

## 📊 Daten-Probleme

### Problem: "Unknown" Werte bei Sensoren

**Symptome:**
- Einige Sensoren zeigen "unbekannt"
- Andere Sensoren funktionieren normal

**Ursachen:**

1. **Nicht unterstütztes Register**
   - Ihr Wechselrichter-Modell unterstützt dieses Register nicht
   - Firmware-Version prüfen

2. **Falsche Register-Adresse**
   - Register-Map des Wechselrichters prüfen
   - Firmware-Unterschiede beachten

3. **Lesefehler**
   - Einzelne Register können nicht gelesen werden
   - Retry-Mechanismus greift

**Lösung:**
- Nicht kritisch, wenn nur wenige Sensoren betroffen
- Logs prüfen für spezifische Fehler
- Bei vielen "Unknown": Wechselrichter-Modell prüfen

### Problem: Falsche Werte

**Symptome:**
- Werte sind offensichtlich falsch (z.B. negative PV-Produktion)
- Einheiten stimmen nicht

**Ursachen:**

1. **Falscher Faktor/Datentyp**
   - Register wird mit falschem Multiplikator gelesen
   - 16-bit vs 32-bit Verwechslung

2. **Byte-Order falsch**
   - Modbus Little Endian vs Big Endian
   - Firmware-spezifische Unterschiede

**Lösung:**
- [GitHub Issue erstellen](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues)
- Register-Adresse und erwarteten Wert angeben
- Firmware-Version des Wechselrichters mitteilen

### Problem: Fehlende Sensoren

**Symptome:**
- Erwartete Sensoren werden nicht angezeigt
- Weniger als 390 Entities

**Ursachen:**

1. **Inaktive Sensoren**
   - Einige Sensoren sind standardmäßig deaktiviert
   - Über Einstellungen → Entities aktivieren

2. **Falsches Wechselrichter-Modell**
   - Nicht alle Sensoren sind für alle Modelle verfügbar
   - HS2 hat weniger Sensoren als H2

3. **Initialisierung nicht abgeschlossen**
   - Erster Start kann 2-3 Minuten dauern
   - Alle Register müssen einmal gelesen werden

---

## 🔋 Charge Control Probleme

### Problem: Slots werden nicht aktiviert

**Symptome:**
- Zeitplan ist konfiguriert, aber Laden findet nicht statt
- `charge_time_enable` zeigt falsche Werte

**Checkliste:**

1. **AppMode prüfen**
   - Muss auf 1 stehen für aktives Laden
   - `sensor.saj_app_mode` prüfen

2. **Slot-Maske prüfen**
   - `number.saj_charge_time_enable_bitmask`
   - Korrekte Bits gesetzt?

3. **Zeitformat**
   - Format: HH:MM
   - 24-Stunden-Format verwenden

4. **Day Mask**
   - `number.saj_charge_day_mask`
   - Heutiger Tag in der Maske enthalten?

### Problem: Passive Mode funktioniert nicht

**Symptome:**
- Schalter werden umgelegt, aber Leistung ändert sich nicht

**Lösungen:**

1. **AppMode prüfen**
   - Passive Mode benötigt AppMode = 3
   - `sensor.saj_app_mode` muss 3 anzeigen

2. **Power-Werte prüfen**
   - `number.saj_passive_bat_charge_power`
   - Wert > 0?
   - Wert in Promille (1000 = 100%)

3. **Schalter-Reihenfolge**
   ```
   1. Power-Werte setzen
   2. Passive Mode Schalter aktivieren
   3. AppMode auf 3 setzen
   ```

### Problem: Zeitpläne werden nicht ausgeführt

**Symptome:**
- Zeit ist erreicht, aber Laden startet nicht

**Ursachen:**

1. **Day Mask falsch**
   - Heutiger Tag nicht in Maske enthalten
   - Beispiel: Heute ist Montag, aber Maske = 126 (Di-So)

2. **Überlappende Zeitpläne**
   - Mehrere Slots zur gleichen Zeit aktiv
   - Konflikte bei der Priorisierung

3. **Uhrzeit falsch**
   - Wechselrichter-Uhrzeit prüfen
   - Zeitzone beachten

---

## ⚡ Performance-Probleme

### Problem: Langsame Updates

**Symptome:**
- Sensoren aktualisieren sich nur alle mehreren Minuten
- UI fühlt sich träge an

**Lösungen:**

1. **Scan-Intervall anpassen**
   - Standard: 60 Sekunden
   - Reduzieren auf 30 Sekunden (Achtung: Höhere Last)

2. **Schnelles Polling aktivieren**
   - Nur für wichtige Sensoren
   - 10-Sekunden-Intervall

3. **Netzwerk optimieren**
   - WLAN → LAN wechseln
   - Latenz reduzieren
   - Bandbreite prüfen

### Problem: Hohe CPU-Last

**Symptome:**
- Home Assistant CPU-Auslastung ist hoch
- System reagiert langsam

**Lösungen:**

1. **Schnelles Polling deaktivieren**
   - Reduziert CPU-Last erheblich
   - Nur bei Bedarf aktivieren

2. **MQTT deaktivieren**
   - Falls nicht benötigt
   - Reduziert Netzwerk- und CPU-Last

3. **Scan-Intervall erhöhen**
   - 60 Sekunden → 120 Sekunden
   - Weniger Modbus-Abfragen

### Problem: MQTT-Verzögerungen

**Symptome:**
- MQTT-Daten kommen verzögert an
- Topics werden nicht aktualisiert

**Ursachen:**

1. **Broker überlastet**
   - Zu viele Nachrichten pro Sekunde
   - Broker-Logs prüfen

2. **Netzwerk-Probleme**
   - Latenz zwischen HA und Broker
   - Paketverluste

3. **QoS-Einstellungen**
   - Standardmäßig QoS 0
   - Bei hoher Last auf QoS 1 wechseln

---

## 🐛 Bekannte Probleme

### Issue #1: Entities zeigen nach Neustart "unavailable"

**Status:** Normal
**Lösung:** 1-2 Minuten warten, bis alle Register gelesen wurden

### Issue #2: Schreiboperationen dauern lange

**Status:** Normal
**Ursache:** Command Queue Serialisierung
**Lösung:** Keine, arbeitet wie designed

### Issue #3: Werte springen kurzzeitig auf 0

**Status:** Bekannt
**Ursache:** Lock-Konflikte während Schreiboperationen
**Lösung:** Ultra-Fast MQTT deaktivieren während Schreiben

---

## 📞 Debug-Informationen sammeln

Für Support-Anfragen benötigen wir:

1. **Home Assistant Logs:**
   ```bash
   ha logs | grep saj_h2_modbus > saj_logs.txt
   ```

2. **System-Information:**
   - Home Assistant Version
   - Integrations-Version
   - Wechselrichter-Modell
   - Firmware-Version

3. **Netzwerk-Test:**
   ```bash
   ping {wechselrichter_ip} -c 10
   nc -zv {wechselrichter_ip} 502
   ```

4. **Modbus-Test (optional):**
   ```bash
   # Modbus-Client installieren
   pip install pymodbus
   
   # Register lesen testen
   python -c "from pymodbus.client import ModbusTcpClient; c=ModbusTcpClient('{ip}'); c.connect(); print(c.read_holding_registers(0x100, 10).registers)"
   ```

---

## 🆘 Support kontaktieren

Wenn das Problem weiterhin besteht:

1. **GitHub Issue erstellen:**
   - [Neues Issue](https://github.com/stanus74/home-assistant-saj-h2-modbus/issues/new)
   - Alle Debug-Informationen anhängen
   - Problem detailliert beschreiben

2. **Home Assistant Forum:**
   - [Community Thread](https://community.home-assistant.io/)
   - Andere Nutzer um Hilfe bitten

3. **Discussions:**
   - [Q&A Bereich](https://github.com/stanus74/home-assistant-saj-h2-modbus/discussions)
   - Fragen stellen

---

[← Zurück zur Übersicht](README.md)
