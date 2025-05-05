# SAJ H2 Charge Card

Eine benutzerdefinierte Karte für Home Assistant zur Steuerung der Ladeeinstellungen für SAJ H2 Wechselrichter.

## Funktionen

- Einfache Einstellung von Ladestart- und Endezeit
- Slider zur Einstellung der Ladeleistung (0-25%)
- Benutzerfreundliche Auswahl der Ladetage mit Checkboxen
- Anzeige des berechneten Daymask-Wertes
- Button zum Aktivieren/Deaktivieren des Ladens
- Statusanzeige für den Ladezustand

## Installation

1. Kopieren Sie die Datei `saj-h2-charge-card.js` in das Verzeichnis `/config/www/saj-h2-charge-card/` Ihrer Home Assistant Installation.

2. Fügen Sie die Ressource in Ihrer Lovelace-Konfiguration hinzu:
   ```yaml
   resources:
     - url: /local/saj-h2-charge-card/saj-h2-charge-card.js
       type: module
   ```

3. Fügen Sie die Karte zu Ihrem Dashboard hinzu:
   ```yaml
   type: 'custom:saj-h2-charge-card'
   title: 'SAJ H2 Ladesteuerung'
   charge_start_entity: text.saj_charge_start_time_time
   charge_end_entity: text.saj_charge_end_time_time
   charge_day_mask_entity: number.saj_charge_day_mask_input
   charge_power_entity: number.saj_charge_power_percent_input
   charging_switch_entity: switch.saj_charging_control
   ```

## Konfigurationsoptionen

| Option | Typ | Erforderlich | Beschreibung |
|--------|-----|-------------|-------------|
| `title` | Zeichenkette | Nein | Titel der Karte (Standard: "SAJ H2 Ladesteuerung") |
| `charge_start_entity` | Zeichenkette | Ja | Entity-ID der Ladestart-Zeit (text) |
| `charge_end_entity` | Zeichenkette | Ja | Entity-ID der Ladeend-Zeit (text) |
| `charge_day_mask_entity` | Zeichenkette | Ja | Entity-ID der Ladetage-Maske (number) |
| `charge_power_entity` | Zeichenkette | Ja | Entity-ID der Ladeleistung (number) |
| `charging_switch_entity` | Zeichenkette | Ja | Entity-ID des Lade-Schalters (switch) |

## Beispiel-Konfiguration

```yaml
type: 'custom:saj-h2-charge-card'
title: 'SAJ H2 Ladesteuerung'
charge_start_entity: text.saj_charge_start_time_time
charge_end_entity: text.saj_charge_end_time_time
charge_day_mask_entity: number.saj_charge_day_mask_input
charge_power_entity: number.saj_charge_power_percent_input
charging_switch_entity: switch.saj_charging_control
```

## Hinweise zur Daymask

Die Daymask ist ein binärer Wert, der die Tage repräsentiert, an denen der Ladevorgang aktiv sein soll:

- Montag = Bit 0 = Wert 1
- Dienstag = Bit 1 = Wert 2
- Mittwoch = Bit 2 = Wert 4
- Donnerstag = Bit 3 = Wert 8
- Freitag = Bit 4 = Wert 16
- Samstag = Bit 5 = Wert 32
- Sonntag = Bit 6 = Wert 64

Die Karte berechnet diesen Wert automatisch basierend auf den ausgewählten Tagen.

## Fehlerbehebung

Wenn die Karte nicht korrekt angezeigt wird oder Fehler auftreten:

1. Überprüfen Sie, ob die JavaScript-Datei korrekt in das `/config/www/saj-h2-charge-card/` Verzeichnis kopiert wurde.
2. Stellen Sie sicher, dass die Ressource korrekt in Ihrer Lovelace-Konfiguration hinzugefügt wurde.
3. Überprüfen Sie, ob alle erforderlichen Entity-IDs in der Konfiguration korrekt angegeben sind.
4. Überprüfen Sie die Browser-Konsole auf JavaScript-Fehler.
