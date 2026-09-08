"""Strategy decision ladder ported from automations/opti_strategie.yaml."""

from __future__ import annotations

from dataclasses import dataclass

MODE_AUTO = "Akku Automatisch"
MODE_FAST_CHARGE = "Akku schnell Laden"
MODE_FAST_DISCHARGE = "Akku schnell Entladen"
MODE_PAUSE = "Akku Pause"
MODE_CHARGE_ONLY = "Akku nur Laden"
MODE_GRID_CHARGE = "Akku Netzladen"
MODE_DISCHARGE_ONLY = "Akku nur Entladen"
MODE_DYNAMIC = "Akku Dynamisch"
MODE_02C_CHARGE = "Akku 0.2C Laden"

PASSIVE_PRICE_FAILSAFE_MODES = {MODE_DYNAMIC, MODE_DISCHARGE_ONLY}
PRICE_TO_EXPENSIVE = {"VERY_CHEAP", "CHEAP", "NORMAL", "EXPENSIVE"}
PRICE_TO_NORMAL = {"VERY_CHEAP", "CHEAP", "NORMAL"}
PRICE_CHEAP = {"VERY_CHEAP", "CHEAP"}


@dataclass(frozen=True, slots=True)
class StrategyInput:
    master_enabled: bool
    core_valid: bool
    soc: float
    min_soc: float
    max_soc: float
    target_soc: float
    current_mode: str
    is_day: bool
    forecast_score: float | None
    forecast_score_tomorrow: float | None
    price_level: str | None
    current_price_ct: float | None
    forecast_grid_charge_enabled: bool
    pv_surplus_charge_enabled: bool
    winter_charging_allowed: bool
    feed_in_tariff_ct: float
    grid_charge_spread_ct: float
    hold_spread_ct: float
    peak_reserve_active: bool
    peak_reserve_soc: float | None
    peak_reserve_ve_soc: float | None
    min_price_before_peak_ct: float | None
    peak_price_avg_ct: float | None
    peak_price_ve_avg_ct: float | None
    charge_ceiling_active: bool
    charge_ceiling_max_soc: float | None
    balancing_mode: str = "aus"
    ev_pause_enabled: bool = False
    ev_fast_charge_active: bool = False
    surplus_70_active: bool = False
    surplus_ac_active: bool = False
    surplus_veto_active: bool = False


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    mode: str
    reason: str


def _ev_blocking(value: StrategyInput) -> bool:
    return value.ev_pause_enabled and value.ev_fast_charge_active


def _charge_window_ok(value: StrategyInput) -> bool:
    return (
        value.min_price_before_peak_ct is None
        or value.current_price_ct is not None
        and value.current_price_ct <= value.min_price_before_peak_ct + 0.5
    )


def decide_strategy(value: StrategyInput) -> StrategyDecision:
    """Mirror the upstream first-match ``choose`` chain."""
    if not value.master_enabled:
        return StrategyDecision(MODE_PAUSE, "Fail-safe: Opti-Automatik aus")
    if not value.core_valid:
        return StrategyDecision(MODE_PAUSE, "Fail-safe: Core-Daten ungueltig")

    score = value.forecast_score
    tomorrow = value.forecast_score_tomorrow
    price = value.price_level
    ev = _ev_blocking(value)
    stopband = 0.0 if value.current_mode == MODE_GRID_CHARGE else 3.0
    reserve_band = 5.0 if value.current_mode == MODE_CHARGE_ONLY else 3.0

    if value.soc < value.min_soc:
        return StrategyDecision(MODE_CHARGE_ONLY, f"MinSOC-Schutz (SoC<{value.min_soc:g})")

    if (
        value.forecast_grid_charge_enabled
        and value.current_price_ct is not None
        and score is not None
        and score < 3
        and value.soc < value.max_soc - stopband
        and value.current_price_ct < value.feed_in_tariff_ct
        and _charge_window_ok(value)
    ):
        return StrategyDecision(
            MODE_GRID_CHARGE,
            f"Negativpreis-Laden ({value.current_price_ct:g}ct < EEG {value.feed_in_tariff_ct:g}ct)",
        )

    if (
        value.forecast_grid_charge_enabled
        and value.peak_reserve_active
        and value.current_price_ct is not None
        and value.peak_reserve_soc is not None
        and value.peak_price_avg_ct is not None
        and value.soc < value.peak_reserve_soc - stopband
        and value.peak_price_avg_ct - value.current_price_ct >= value.grid_charge_spread_ct
        and _charge_window_ok(value)
    ):
        return StrategyDecision(
            MODE_GRID_CHARGE,
            f"Peak-Vorladen (Spread {value.peak_price_avg_ct - value.current_price_ct:.1f}ct, bis {value.peak_reserve_soc:g}%)",
        )

    if value.peak_reserve_active and price == "VERY_EXPENSIVE" and not ev:
        return StrategyDecision(MODE_DISCHARGE_ONLY, "Peak-Leiter L1 (VE entladen)")

    if (
        value.peak_reserve_active
        and price == "EXPENSIVE"
        and value.peak_reserve_ve_soc is not None
        and value.soc > value.peak_reserve_ve_soc + reserve_band
        and not ev
    ):
        return StrategyDecision(
            MODE_DISCHARGE_ONLY,
            f"Peak-Leiter L2 (EXP entladen, ueber VE-Reserve {value.peak_reserve_ve_soc:g}%)",
        )

    if value.balancing_mode == "pv":
        return StrategyDecision(MODE_CHARGE_ONLY, "Balancing-Watchdog (PV-Vollladung)")
    if value.balancing_mode == "netz":
        return StrategyDecision(MODE_GRID_CHARGE, "Balancing-Watchdog (Netz-Vollladung)")

    ceiling_band = 3.0 if (
        value.charge_ceiling_active and value.charge_ceiling_max_soc == value.max_soc
    ) else 0.0
    if not value.peak_reserve_active and not ev and value.soc >= value.max_soc - ceiling_band:
        return StrategyDecision(MODE_DISCHARGE_ONLY, "Ladedeckel (maxsoc erreicht)")

    if (
        value.forecast_grid_charge_enabled
        and value.winter_charging_allowed
        and score is not None
        and tomorrow is not None
        and value.soc < 20
        and score < 3
        and tomorrow < 3
        and price in PRICE_TO_EXPENSIVE
    ):
        return StrategyDecision(MODE_CHARGE_ONLY, "SOC<20 Prognose (heute+morgen schlecht)")

    if (
        value.forecast_grid_charge_enabled
        and score is not None
        and tomorrow is not None
        and value.soc < 75
        and score < 3
        and tomorrow < 3
        and price in PRICE_TO_NORMAL
    ):
        return StrategyDecision(MODE_CHARGE_ONLY, "SOC<75 Prognose (Preis bis NORMAL)")

    if (
        value.forecast_grid_charge_enabled
        and value.winter_charging_allowed
        and score is not None
        and tomorrow is not None
        and value.soc < 80
        and score < 3
        and tomorrow < 3
        and price in PRICE_TO_EXPENSIVE
    ):
        return StrategyDecision(MODE_CHARGE_ONLY, "SOC<80 Wintermodus")

    if (
        value.forecast_grid_charge_enabled
        and score is not None
        and value.soc < 15
        and score < 3
        and price in PRICE_TO_EXPENSIVE
    ):
        return StrategyDecision(MODE_CHARGE_ONLY, "SOC<15 Notfall")

    if (
        value.forecast_grid_charge_enabled
        and score is not None
        and value.soc < 45
        and score < 3
        and price in PRICE_CHEAP
    ):
        return StrategyDecision(MODE_CHARGE_ONLY, "SOC<45 sehr guenstig")

    if ev:
        return StrategyDecision(MODE_CHARGE_ONLY, "EV-Sperre (Schnellladung, Entladesperre)")

    if value.pv_surplus_charge_enabled and value.is_day and value.surplus_70_active and value.soc < 100:
        return StrategyDecision(MODE_DYNAMIC, "70% Ueberschuss (tag, entprellt)")

    if value.pv_surplus_charge_enabled and value.is_day and value.surplus_ac_active and value.soc < 100:
        return StrategyDecision(MODE_DYNAMIC, "AC Ueberschuss (tag, entprellt)")

    if value.soc > 99:
        return StrategyDecision(MODE_DYNAMIC, "Akku voll")

    if (
        value.peak_reserve_active
        and price == "EXPENSIVE"
        and value.peak_reserve_ve_soc is not None
        and value.soc <= value.peak_reserve_ve_soc + reserve_band
        and value.peak_price_ve_avg_ct is not None
        and value.current_price_ct is not None
        and value.peak_price_ve_avg_ct - value.current_price_ct >= value.hold_spread_ct
    ):
        return StrategyDecision(
            MODE_CHARGE_ONLY,
            f"Peak-Leiter L3 (halten fuer VE, Reserve {value.peak_reserve_ve_soc:g}%, Spread {value.peak_price_ve_avg_ct - value.current_price_ct:.1f}ct)",
        )

    if (
        value.peak_reserve_active
        and price in PRICE_TO_NORMAL
        and value.peak_reserve_soc is not None
        and value.soc <= value.peak_reserve_soc + reserve_band
    ):
        return StrategyDecision(
            MODE_CHARGE_ONLY,
            f"Peak-Leiter L4 (halten fuer Peaks, Reserve {value.peak_reserve_soc:g}%)",
        )

    if (
        value.pv_surplus_charge_enabled
        and value.is_day
        and value.surplus_veto_active
        and value.soc < value.max_soc
    ):
        return StrategyDecision(MODE_DYNAMIC, f"Ueberschuss-Veto (sticht Ziel-SoC {value.target_soc:g}%)")

    if value.soc > value.min_soc and value.soc < value.target_soc - 3.0 and value.is_day:
        return StrategyDecision(MODE_DYNAMIC, "dyn bis Ziel (tag)")

    target_band = 0.0 if value.current_mode == MODE_DISCHARGE_ONLY else 3.0
    if value.soc > value.target_soc + target_band:
        return StrategyDecision(MODE_DISCHARGE_ONLY, "ueber Ziel-SoC")

    if price is None and value.current_mode in PASSIVE_PRICE_FAILSAFE_MODES:
        return StrategyDecision(value.current_mode, "Preisniveau fehlt (passiver Modus gehalten)")

    return StrategyDecision(MODE_DYNAMIC, "Default (Nacht/keine Aktion)")
