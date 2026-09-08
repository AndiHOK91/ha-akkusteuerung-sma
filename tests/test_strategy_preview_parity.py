"""Parity tests for the native strategy preview against upstream behaviour."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).parents[1] / "custom_components" / "akkusteuerung_sma" / "strategy.py"
MODULE_NAME = "akkusteuerung_strategy_preview"
spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE)
strategy = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = strategy
assert spec.loader is not None
spec.loader.exec_module(strategy)


def base(**overrides):
    values = dict(
        master_enabled=True,
        core_valid=True,
        soc=40.0,
        min_soc=10.0,
        max_soc=95.0,
        target_soc=60.0,
        current_mode=strategy.MODE_DYNAMIC,
        is_day=False,
        forecast_score=5.0,
        forecast_score_tomorrow=5.0,
        price_level="NORMAL",
        current_price_ct=30.0,
        forecast_grid_charge_enabled=True,
        pv_surplus_charge_enabled=True,
        winter_charging_allowed=True,
        feed_in_tariff_ct=8.0,
        grid_charge_spread_ct=10.0,
        hold_spread_ct=0.0,
        peak_reserve_active=False,
        peak_reserve_soc=None,
        peak_reserve_ve_soc=None,
        min_price_before_peak_ct=None,
        peak_price_avg_ct=None,
        peak_price_ve_avg_ct=None,
        charge_ceiling_active=False,
        charge_ceiling_max_soc=95.0,
        balancing_mode="aus",
        surplus_70_active=False,
        surplus_ac_active=False,
        surplus_veto_active=False,
    )
    values.update(overrides)
    return strategy.StrategyInput(**values)


def test_minsoc_precedes_negative_price_charging():
    decision = strategy.decide_strategy(base(soc=5, forecast_score=1, current_price_ct=3))
    assert decision.mode == strategy.MODE_CHARGE_ONLY
    assert "MinSOC" in decision.reason


def test_negative_price_charges_when_no_cheaper_window_exists():
    decision = strategy.decide_strategy(base(soc=40, forecast_score=1, current_price_ct=3))
    assert decision.mode == strategy.MODE_GRID_CHARGE
    assert "Negativpreis" in decision.reason


def test_negative_price_waits_for_cheaper_window():
    decision = strategy.decide_strategy(base(
        soc=40,
        forecast_score=1,
        current_price_ct=3,
        min_price_before_peak_ct=-2,
    ))
    assert decision.mode != strategy.MODE_GRID_CHARGE
    assert "Negativpreis" not in decision.reason


def test_peak_precharge_and_stopband_match_upstream():
    common = dict(
        forecast_score=1,
        forecast_score_tomorrow=1,
        current_price_ct=50,
        peak_reserve_active=True,
        peak_reserve_soc=35,
        peak_reserve_ve_soc=25,
        min_price_before_peak_ct=50,
        peak_price_avg_ct=200,
        peak_price_ve_avg_ct=200,
    )
    charging = strategy.decide_strategy(base(soc=34, current_mode=strategy.MODE_GRID_CHARGE, **common))
    assert charging.mode == strategy.MODE_GRID_CHARGE
    assert "Peak-Vorladen" in charging.reason

    not_charging = strategy.decide_strategy(base(soc=34, current_mode=strategy.MODE_DYNAMIC, **common))
    assert "Peak-Vorladen" not in not_charging.reason


def test_peak_l1_and_l2_precede_old_forecast_charge_blocks():
    l1 = strategy.decide_strategy(base(
        soc=55,
        forecast_score=1,
        forecast_score_tomorrow=1,
        price_level="VERY_EXPENSIVE",
        peak_reserve_active=True,
        peak_reserve_soc=45,
        peak_reserve_ve_soc=30,
        peak_price_avg_ct=200,
        peak_price_ve_avg_ct=200,
    ))
    assert l1.mode == strategy.MODE_DISCHARGE_ONLY
    assert "L1" in l1.reason

    l2 = strategy.decide_strategy(base(
        soc=55,
        forecast_score=1,
        forecast_score_tomorrow=1,
        price_level="EXPENSIVE",
        peak_reserve_active=True,
        peak_reserve_soc=45,
        peak_reserve_ve_soc=30,
        peak_price_avg_ct=200,
        peak_price_ve_avg_ct=200,
    ))
    assert l2.mode == strategy.MODE_DISCHARGE_ONLY
    assert "L2" in l2.reason


def test_balancing_still_works_without_price_level():
    decision = strategy.decide_strategy(base(price_level=None, balancing_mode="pv"))
    assert decision.mode == strategy.MODE_CHARGE_ONLY
    assert "Balancing" in decision.reason


def test_charge_ceiling_still_works_without_price_level():
    decision = strategy.decide_strategy(base(
        price_level=None,
        soc=97,
        charge_ceiling_active=True,
        charge_ceiling_max_soc=95,
    ))
    assert decision.mode == strategy.MODE_DISCHARGE_ONLY
    assert "Ladedeckel" in decision.reason


def test_above_target_still_discharges_without_price_level():
    decision = strategy.decide_strategy(base(
        price_level=None,
        soc=80,
        target_soc=60,
        is_day=False,
    ))
    assert decision.mode == strategy.MODE_DISCHARGE_ONLY
    assert "Ziel-SoC" in decision.reason


def test_missing_price_holds_passive_mode_in_neutral_band():
    for passive in (strategy.MODE_DYNAMIC, strategy.MODE_DISCHARGE_ONLY):
        decision = strategy.decide_strategy(base(
            price_level=None,
            soc=60,
            target_soc=95,
            current_mode=passive,
            is_day=False,
        ))
        assert decision.mode == passive
        assert "passiver Modus gehalten" in decision.reason


def test_missing_price_releases_forced_modes_to_dynamic():
    for forced in (
        strategy.MODE_GRID_CHARGE,
        strategy.MODE_CHARGE_ONLY,
        strategy.MODE_PAUSE,
        strategy.MODE_FAST_CHARGE,
    ):
        decision = strategy.decide_strategy(base(
            price_level=None,
            soc=60,
            target_soc=95,
            current_mode=forced,
            is_day=False,
        ))
        assert decision.mode == strategy.MODE_DYNAMIC
        assert "Default" in decision.reason


def test_surplus_veto_precedes_target_soc_discharge():
    decision = strategy.decide_strategy(base(
        soc=70,
        target_soc=60,
        is_day=True,
        surplus_veto_active=True,
    ))
    assert decision.mode == strategy.MODE_DYNAMIC
    assert "Ueberschuss-Veto" in decision.reason
