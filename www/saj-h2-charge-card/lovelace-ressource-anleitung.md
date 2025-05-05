# Hinzufügen einer Ressource in Lovelace

Diese Anleitung erklärt, wie Sie eine benutzerdefinierte JavaScript-Ressource zu Ihrer Lovelace-Konfiguration in Home Assistant hinzufügen.

## Methode 1: Über die Benutzeroberfläche (empfohlen)

1. Öffnen Sie Home Assistant in Ihrem Browser
2. Klicken Sie auf **Konfiguration** in der Seitenleiste (Zahnrad-Symbol)
3. Wählen Sie **Lovelace-Dashboards**
4. Klicken Sie auf den Tab **Ressourcen**
5. Klicken Sie auf den Button **+ RESSOURCE HINZUFÜGEN** in der unteren rechten Ecke
6. Geben Sie folgende Informationen ein:
   - URL: `/local/saj-h2-charge-card/saj-h2-charge-card.js`
   - Ressourcentyp: `JavaScript-Modul`
7. Klicken Sie auf **ERSTELLEN**
8. Laden Sie die Seite neu, um die Änderungen zu übernehmen

## Methode 2: Über die Konfigurationsdatei

Wenn Sie Lovelace im YAML-Modus verwenden, können Sie die Ressource in Ihrer `ui-lovelace.yaml` Datei hinzufügen:

1. Öffnen Sie Ihre `ui-lovelace.yaml` Datei
2. Fügen Sie die Ressource im `resources`-Abschnitt hinzu:

```yaml
resources:
  - url: /local/saj-h2-charge-card/saj-h2-charge-card.js
    type: module
```

3. Speichern Sie die Datei
4. Laden Sie Home Assistant neu, um die Änderungen zu übernehmen

## Methode 3: Über die Ressourcen-Datei

Wenn Sie mehrere Dashboards haben, können Sie die Ressource in der `lovelace-resources.yaml` Datei hinzufügen:

1. Erstellen oder öffnen Sie die Datei `.storage/lovelace_resources` in Ihrem Home Assistant-Konfigurationsverzeichnis
2. Fügen Sie die Ressource hinzu:

```json
{
  "data": {
    "items": [
      {
        "id": "saj_h2_charge_card",
        "type": "module",
        "url": "/local/saj-h2-charge-card/saj-h2-charge-card.js"
      }
    ]
  },
  "key": "lovelace_resources",
  "version": 1
}
```

3. Speichern Sie die Datei
4. Starten Sie Home Assistant neu, um die Änderungen zu übernehmen

## Überprüfen der Installation

Nach dem Hinzufügen der Ressource sollten Sie in der Lage sein, die benutzerdefinierte Karte zu Ihrem Dashboard hinzuzufügen:

1. Gehen Sie zu einem Dashboard
2. Klicken Sie auf **Bearbeiten**
3. Klicken Sie auf **+ Karte hinzufügen**
4. Scrollen Sie nach unten zu **Benutzerdefiniert**
5. Wählen Sie **SAJ H2 Charge Card**

Wenn die Karte nicht in der Liste erscheint, überprüfen Sie, ob die Ressource korrekt hinzugefügt wurde und laden Sie die Seite neu.
