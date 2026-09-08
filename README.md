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

## Aktueller Stand

Die Integration befindet sich noch in der Migration. Bereits umgesetzt sind:

- UI-basierter Config Flow für das Canonical-Mapping
- Auswahl der Energie-, Batterie-, Strompreis- und Solcast-Entitäten
- Canonical-Sensoren mit den ursprünglichen Namen `sensor.opti_*`
- persistente Number-, Select- und Switch-Helfer aus `packages/sma_helpers.yaml`
- Kernlogik für Forecast, Ziel-SoC, Preisniveau, Peak-Reserve und Überschusssteuerung
- Kern-Strategie mit Fail-safe und Prioritätsleiter
- HACS-Grundstruktur

Noch nicht vollständig abgeschlossen sind insbesondere:

- die restliche Paritätsprüfung von `packages/opti_derived.yaml`
- die restliche Paritätsprüfung von `automations/opti_strategie.yaml`
- persistente Balancing-Counter/Automationen
- abschließende Home-Assistant- und Adapter-Integrationstests

**Die Integration ist deshalb noch nicht für produktive Akku-Steuerung freigegeben.**

## Installation während der Entwicklung

1. Dieses Repository als benutzerdefiniertes Repository in HACS hinzufügen.
2. Kategorie: Integration.
3. `SMA Akku Steuerung` installieren.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** `SMA Akku Steuerung` auswählen.
6. Im Assistenten die vorhandenen Sensoren entsprechend dem ursprünglichen `opti_mapping.example.yaml` zuordnen.

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
- `sensor.opti_price_current_ct_kwh`
- `sensor.opti_price_series`
- `sensor.opti_forecast_today_kwh`
- `sensor.opti_forecast_tomorrow_kwh`
- `sensor.opti_forecast_remaining_today_kwh`
- `sensor.opti_battery_power_w`

## Quelle und Lizenz

Die zugrunde liegende Opti-Logik stammt aus:

- https://github.com/Optic00/ha-opti-akkusteuerung

Das Ursprungsprojekt steht unter MIT-Lizenz. Der Copyright- und Lizenzhinweis von Optic00 ist in `LICENSE` erhalten.

Dieses Projekt wird nicht von SMA begleitet oder unterstützt. Nutzung auf eigene Gefahr.
