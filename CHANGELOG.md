# Changelog

## 0.4.0 — 2026-09-08

Erster veröffentlichungsreifer Stand der Kernintegration.

### Enthalten

- UI-basierter Config Flow für das Canonical-Mapping
- native Canonical-, Derived-, Statistik-, Peak-, Überschuss- und Balancing-Logik
- Strategie-Vorschau mit paritätsgeprüfter Entscheidungsleiter
- persistente Home-Assistant-Helfer für die Kernsteuerung
- Peak-Reserve und Ladedeckel inklusive Hysterese
- Preis-Fail-safe: Ausfall der Preisreihe stoppt nicht die gesamte Strategie
- optionale Strompreis-Reihe mit Fallback auf die aktuelle Strompreis-Entität
- ausführliche deutschsprachige Hilfetexte im Einrichtungsdialog
- HACS-Grundstruktur und GitHub-Actions-Tests

### Bewusst nicht enthalten

- KI-Analyse
- BYD-Monitoring / BYD-Modul-Frühwarnung
- EV-/evcc-Sperrlogik
- direkte Modbus-Schreiblogik; die Hardware-Ansteuerung bleibt gemäß Single-Writer-Prinzip im separaten Adapter

### Hinweis

Vor produktiver Akku-Steuerung sollte der reale End-to-End-Test in der jeweiligen Home-Assistant-Instanz mit den konkret gemappten SMA-, Preis- und Solcast-Entitäten sowie dem separaten Hardware-Adapter erfolgen.
