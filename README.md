# SMA Akku Steuerung

Home-Assistant-Custom-Integration auf Basis von [Optic00/ha-opti-akkusteuerung](https://github.com/Optic00/ha-opti-akkusteuerung).

Ziel dieses Repositories ist es, die dort vorhandene YAML-/Package-Lösung als einfach installierbare Integration bereitzustellen, ohne die fachliche Opti-Logik neu zu erfinden.

## Umfang

Diese Integration übernimmt den Kern der Akku-Optimierung. Die folgenden optionalen Pakete des Ursprungsprojekts werden bewusst **nicht** übernommen:

- `packages/opti_ki_analyse.yaml`
- `packages/byd_monitoring.yaml`
- `packages/byd_modul2_fruehwarnung.yaml`
- `packages/opti_ev_sperre.yaml`

Damit gibt es in dieser Integration vorerst keine KI-Analyse, kein BYD-Monitoring bzw. keine BYD-Modul-Frühwarnung und keine EV-/evcc-Sperrlogik.

## Stand der Kernmigration

Der Kern der ursprünglichen Opti-Lösung ist nativ in die Integration übertragen. Umgesetzt sind:

- UI-basierter Config Flow für das Canonical-Mapping
- Auswahl der Energie-, Batterie-, Strompreis- und Solcast-Entitäten
- Canonical-Sensoren mit den ursprünglichen Namen `sensor.opti_*`
- persistente Number-, Select- und Switch-Helfer aus `packages/sma_helpers.yaml`
- Forecast-Score heute/morgen und Forecast-Optimismus
- Ziel-SoC mit Schmitt-Hysterese
- dynamische Ladeleistung
- Preisniveau mit Midrank-Perzentilen und fail-closed Preisquellenbehandlung
- Peak-Reserve inklusive Stunden-/15-Minuten-Raster, DST-Fällen, Reichtag-Horizont und Preisaufschlag
- Peak-Leiter und Peak-Vorladen
- 70-%-, AC- und wirtschaftliches Überschuss-Gate mit Hysterese/Entprellung
- Ladedeckel mit 3-%-Hysterese und Neustart-Wiederherstellung
- 30-Minuten-Batterieleistungs- und 60-Minuten-Hausverbrauchsmittelwerte aus `packages/sma_statistik.yaml`
- persistenter Balancing-/Deep-Charge-Watchdog ohne BYD-Zellspreizungs-Erweiterung
- Strategie-Vorschau mit Entscheidungsgrund
- Kern-Strategie mit Fail-safe und Prioritätsleiter
- HACS-Grundstruktur und GitHub-Actions-Tests

Die Kernlogik ist mit Unit-/Paritätstests gegen wesentliche Randfälle des Ursprungsprojekts abgesichert. Dazu gehören unter anderem Preisquellen-Ausfälle, Peak-Reserve, Ladedeckel, Balancing, Überschuss-Gates und Strategie-Prioritäten.

## Hardware-Adapter bleibt bewusst getrennt

Wie im Ursprungsprojekt schreibt diese Integration **nicht direkt** auf SMA-Modbus-Register. Sie berechnet und setzt den Strategiemodus; die eigentliche Wechselrichter-Ansteuerung bleibt Aufgabe des separaten Hardware-Adapters:

- [Optic00/ha-modbus-akku-adapter](https://github.com/Optic00/ha-modbus-akku-adapter)

Damit bleibt die ursprüngliche Sicherheitsarchitektur erhalten:

```text
Strategie / Integration
        ↓
Akkusteuerung-Modus
        ↓
Hardware-Adapter
        ↓
SMA Modbus
```

**Single-Writer-Regel:** Es darf immer nur eine Instanz/Automation den Wechselrichter per Modbus steuern.

Für `Akku Netzladen` muss der verwendete Adapter den dynamischen Netzlade-Modus des Ursprungsprojekts unterstützen.

## `packages/sma_templates.yaml`

Der Kern aus `packages/sma_templates.yaml` wird **nicht noch einmal als Legacy-Template-Satz erzeugt**, weil die entsprechenden Funktionen bereits nativ in der Integration vorhanden sind:

- `House Battery Runtime Raw` → durch die native Laufzeitberechnung ersetzt
- `Akkusteuerung Dynamische Ladestaerke` → durch `sensor.opti_charge_power_w` ersetzt
- `PV Forecast Bewertung Heute/Morgen` → fachlich durch `sensor.opti_forecast_score` und `sensor.opti_forecast_score_tomorrow` ersetzt
- `Akku Target SoC Intelligent` → durch `sensor.opti_target_soc` ersetzt
- `Ueberschuss PV Watt` → durch Canonical-Netzeinspeisung und die nativen Überschuss-Gates ersetzt
- `Akku Net Verfügbare Energie` und `Verbleibende Sonnenstunden` → Bestandteil der Ziel-SoC-/Forecast-Berechnung und deren Diagnoseattribute
- `Strompreis Niveau` → durch `sensor.opti_price_level` ersetzt

Die beiden im Original ausdrücklich nur für **Observability/Vorbereitung** vorgesehenen Sensoren `Akku Soll-SoC Kurve` und `Akkusteuerung Dynamische Ladestaerke (P-Regler)` werden nicht übernommen, da sie weder von Strategie noch Adapter konsumiert werden.

Die Abregelungs-Sensoren `Akku MaxGen Erzeugungsgrenze vor Abregelung` und `Akku Abregelungsleistung` werden ebenfalls nicht in den Kern aufgenommen. Sie benötigen zusätzliche, anlagenspezifische Eingänge für WR-Leistungslimit und installierte PV-Peakleistung und sind für die aktuelle Kernstrategie nicht erforderlich.

## Installation

1. Dieses Repository als benutzerdefiniertes Repository in HACS hinzufügen.
2. Kategorie: Integration.
3. `SMA Akku Steuerung` installieren.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** `SMA Akku Steuerung` auswählen.
6. Im Assistenten die vorhandenen Sensoren entsprechend dem ursprünglichen `opti_mapping.example.yaml` zuordnen.
7. Die erzeugten `sensor.opti_*`-Entitäten und die Strategie-Vorschau prüfen.
8. Erst danach den separaten Hardware-Adapter anbinden.
9. Vor Aktivierung sicherstellen, dass kein zweiter Modbus-Schreiber parallel aktiv ist.

## Vor der ersten produktiven Aktivierung

Die Code-/Paritätstests sind grün. Vor einer produktiven Akku-Steuerung sollte trotzdem ein realer Inbetriebnahmetest in Home Assistant erfolgen:

- alle ausgewählten Quell-Entitäten liefern plausible Werte
- `sensor.opti_price_level` reagiert bei Preisquellen-Ausfall mit `unavailable`
- `sensor.opti_strategie_vorschau` zeigt plausible Modi und Gründe
- MinSOC- und maxSOC/Ladedeckel-Verhalten testen
- Hardware-Adapter zunächst ohne konkurrierende Modbus-Automation prüfen
- erst danach `Akku Opti Automatik` aktivieren

## Canonical-Layer

Die Integration erzeugt unter anderem die vom Originalprojekt erwarteten Entitäten:

- `sensor.opti_soc`
- `sensor.opti_battery_temp`
- `sensor.opti_battery_capacity_kwh`
- `sensor.opti_pv_power_w`
- `sensor.opti_pv_generation_w`
- `sensor.opti_grid_export_w`
- `sensor.opti_grid_import_w`
- `sensor.opti_house_consumption_w`
- `sensor.opti_house_consumption_60min_w`
- `sensor.opti_price_current_ct_kwh`
- `sensor.opti_price_series`
- `sensor.opti_forecast_today_kwh`
- `sensor.opti_forecast_tomorrow_kwh`
- `sensor.opti_forecast_remaining_today_kwh`
- `sensor.opti_battery_power_w`
- `sensor.opti_target_soc`
- `sensor.opti_charge_power_w`
- `sensor.opti_price_level`
- `sensor.opti_peak_reserve_soc`
- `sensor.opti_balancing_watchdog`
- `sensor.opti_strategie_vorschau`
- `binary_sensor.opti_ladedeckel_aktiv`

## Quelle und Lizenz

Die zugrunde liegende Opti-Logik stammt aus:

- https://github.com/Optic00/ha-opti-akkusteuerung

Das Ursprungsprojekt steht unter MIT-Lizenz. Der Copyright- und Lizenzhinweis von Optic00 ist in `LICENSE` erhalten.

Dieses Projekt wird nicht von SMA begleitet oder unterstützt. Nutzung auf eigene Gefahr.
