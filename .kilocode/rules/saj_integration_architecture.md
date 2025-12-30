# SAJ H2 Modbus Integration Architecture & Logic

Du bist der Hauptentwickler für die SAJ H2 Modbus Integration. Du musst dich strikt an die folgende Architektur halten, wenn du Code änderst oder erweiterst.

## Kern-Komponenten & Verantwortlichkeiten
* **Hub (`hub.py`)**: Zentraler State-Manager und Koordinator. Er verwaltet `inverter_data` und steuert die Intervalle (Normal: 60s, Fast: 10s, Ultra-Fast: 1s MQTT).
* **Modbus Communication (`modbus_utils.py`)**: Alle Modbus-Operationen MÜSSEN über `_retry_with_backoff` und `hass.async_add_executor_job` laufen, um den Event-Loop nicht zu blockieren.
* **Data Decoding (`modbus_readers.py`)**: Nutzt statische Maps zur Dekodierung. Neue Register müssen hier in die entsprechenden Blöcke (`_read_modbus_data`) integriert werden.
* **Charge Control (`charge_control.py`)**: Enthält die Geschäftslogik für Zeitpläne. Nutzt ein Factory-Pattern für Handler. Änderungen an Ladeeinstellungen werden hier validiert.

## Spezielle Features (Nicht verändern ohne Rücksprache)
* **Ultra-Fast MQTT**: Wenn `ultra_fast_enabled` aktiv ist, werden Daten im 1s-Takt NUR via MQTT gesendet, NICHT an die HA-Entitäten (Vermeidung von DB-Bloat).
* **Pending Settings**: Der Hub puffert Benutzereingaben (Schalter/Zahlen) und schreibt sie gesammelt über den `ChargeSettingHandler`.
* **Frontend**: Die Lovelace-Card (`saj-discharge-schedule-card.js`) parst die Bitmasken der Wochentage aus den Sensoren.


