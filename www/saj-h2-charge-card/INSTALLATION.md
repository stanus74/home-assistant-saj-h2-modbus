# Installation der SAJ H2 Charge Card

Diese Anleitung beschreibt, wie Sie die SAJ H2 Charge Card in Ihrer Home Assistant Installation einrichten.

## Voraussetzungen

- Home Assistant mit der SAJ H2 Modbus Integration
- Zugriff auf das Dateisystem von Home Assistant

## Installationsschritte

### 1. Dateien kopieren

Kopieren Sie die folgenden Dateien in das Verzeichnis `/config/www/saj-h2-charge-card/` Ihrer Home Assistant Installation:

- `saj-h2-charge-card.js`
- `saj-h2-charge-card.css`

Sie können dies über die Samba-Freigabe, SSH oder den Datei-Editor in Home Assistant tun.

### 2. Ressource in Lovelace hinzufügen

Fügen Sie die JavaScript-Datei als Ressource in Ihrer Lovelace-Konfiguration hinzu:

1. Gehen Sie zu **Konfiguration** > **Lovelace-Dashboards** > **Ressourcen**
2. Klicken Sie auf **Ressource hinzufügen**
3. Geben Sie folgende Informationen ein:
   - URL: `/local/saj-h2-charge-card/saj-h2-charge-card.js`
   - Ressourcentyp: `JavaScript-Modul`
4. Klicken Sie auf **Erstellen**

### 3. Karte zum Dashboard hinzufügen

Fügen Sie die Karte zu Ihrem Dashboard hinzu:

1. Gehen Sie zu Ihrem Dashboard
2. Klicken Sie auf **Bearbeiten**
3. Klicken Sie auf **+ Karte hinzufügen**
4. Wählen Sie **Benutzerdefiniert: SAJ H2 Charge Card**
5. Konfigurieren Sie die Karte mit den entsprechenden Entitäten:

```yaml
type: 'custom:saj-h2-charge-card'
title: 'SAJ H2 Ladesteuerung'
charge_start_entity: text.saj_charge_start_time_time
charge_end_entity: text.saj_charge_end_time_time
charge_day_mask_entity: number.saj_charge_day_mask_input
charge_power_entity: number.saj_charge_power_percent_input
charging_switch_entity: switch.saj_charging_control
```

6. Klicken Sie auf **Speichern**

## Verwendung

Die Karte bietet folgende Funktionen:

- Einstellung der Ladestart- und Endezeit
- Einstellung der Ladeleistung (0-25%)
- Auswahl der Ladetage über Checkboxen
- Aktivierung/Deaktivierung des Ladens

Alle Änderungen werden automatisch an die SAJ H2 Modbus Integration übermittelt.

## Fehlerbehebung

Wenn die Karte nicht korrekt angezeigt wird:

1. Überprüfen Sie die Browser-Konsole auf JavaScript-Fehler
2. Stellen Sie sicher, dass die Ressource korrekt geladen wird
3. Überprüfen Sie, ob die angegebenen Entitäten existieren und korrekt sind
