"""Core derived calculations ported from packages/opti_derived.yaml.

The functions in this module intentionally mirror the upstream thresholds and
unit conventions. Hardware communication does not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Iterable


PRICE_LEVELS = (
    "VERY_CHEAP",
    "CHEAP",
    "NORMAL",
    "EXPENSIVE",
    "VERY_EXPENSIVE",
)


@dataclass(frozen=True, slots=True)
class ForecastScoreResult:
    """Forecast score plus upstream diagnostic attributes."""

    score: int
    remaining_kwh: float
    needed_full_kwh: float
    hours_to_sunset: float
    pv_surplus_kwh: float
    excess_over_full_kwh: float
    reason: str


@dataclass(frozen=True, slots=True)
class TargetSocResult:
    """Target SoC plus Schmitt-hysteresis state."""

    target_soc: float
    level: int
    ratio: float
    net_available_kwh: float
    remaining_hours: float
    branch: str


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def effective_forecast_remaining(
    median_kwh: float,
    estimate10_kwh: float | None,
    optimism_percent: float,
) -> float:
    """Port sensor.opti_forecast_effective_remaining_kwh.

    alpha=0 means conservative min(median, P10); alpha=100 means median.
    """
    p10 = estimate10_kwh if estimate10_kwh is not None and estimate10_kwh > 0 else median_kwh
    alpha = _clamp(optimism_percent, 0.0, 100.0) / 100.0
    blended = alpha * median_kwh + (1.0 - alpha) * p10
    return min(median_kwh, blended)


def forecast_score_tomorrow(
    forecast_kwh: float,
    estimate10_kwh: float | None,
    house_consumption_w: float,
    optimism_percent: float,
) -> int:
    """Port sensor.opti_forecast_score_tomorrow."""
    consumption_w = max(house_consumption_w, 1.0)
    denominator_kwh = consumption_w * 24.0 / 1000.0
    p10 = estimate10_kwh if estimate10_kwh is not None and estimate10_kwh > 0 else forecast_kwh
    alpha = _clamp(optimism_percent, 0.0, 100.0) / 100.0
    blended = alpha * forecast_kwh + (1.0 - alpha) * p10
    effective = min(forecast_kwh, blended)
    ratio = _clamp(effective / denominator_kwh, 0.0, 1.0)
    return int(round(ratio * 10.0))


def forecast_score(
    *,
    effective_remaining_kwh: float,
    battery_capacity_kwh: float,
    soc: float,
    house_consumption_w: float,
    hours_to_sunset: float,
    after_sunset: bool,
    tomorrow_score: int,
) -> ForecastScoreResult:
    """Port sensor.opti_forecast_score."""
    needed = battery_capacity_kwh * (1.0 - soc / 100.0)
    consumption_kwh = house_consumption_w / 1000.0 * max(hours_to_sunset, 0.0)
    surplus = max(effective_remaining_kwh - consumption_kwh, 0.0)

    if after_sunset:
        score = tomorrow_score
        reason = "Abend -> Morgen-Score"
    elif hours_to_sunset <= 0:
        score = 0
        reason = "Nacht"
    elif needed <= 0:
        score = 10
        reason = "Akku voll"
    else:
        score = int(round(min(surplus / needed, 1.0) * 10.0))
        reason = "PV-Fit"

    return ForecastScoreResult(
        score=score,
        remaining_kwh=round(effective_remaining_kwh, 2),
        needed_full_kwh=round(needed, 2),
        hours_to_sunset=round(hours_to_sunset, 1),
        pv_surplus_kwh=round(surplus, 2),
        excess_over_full_kwh=round(max(surplus - needed, 0.0), 2),
        reason=reason,
    )


def target_soc(
    *,
    battery_capacity_kwh: float,
    effective_remaining_kwh: float,
    house_consumption_w: float,
    remaining_hours: float,
    min_soc: float,
    max_soc: float,
    grid_charging: bool,
    previous_level: int | None,
) -> TargetSocResult:
    """Port sensor.opti_target_soc including its Schmitt hysteresis."""
    remaining_hours = _clamp(remaining_hours, 0.5, 12.0)

    if grid_charging:
        return TargetSocResult(
            target_soc=round(max_soc),
            level=0,
            ratio=0.0,
            net_available_kwh=0.0,
            remaining_hours=remaining_hours,
            branch="netzladen -> maxsoc",
        )

    net_available = max(
        0.0,
        effective_remaining_kwh - house_consumption_w / 1000.0 * remaining_hours,
    )
    ratio = 0.0 if battery_capacity_kwh <= 0 else net_available / battery_capacity_kwh

    margin = 0.10
    bounds = (0.375, 0.875, 1.375, 1.875, 2.875)
    targets = (max_soc, 90.0, 80.0, 70.0, 60.0, 50.0)
    plain = sum(1 for bound in bounds if bound <= ratio)
    level = plain if previous_level is None else int(_clamp(previous_level, 0, 5))

    # Same iterative Schmitt logic as the Jinja template: crossing several
    # bands in one update is deliberately possible.
    for _ in bounds:
        if level < 5 and ratio >= bounds[level] + margin:
            level += 1
    for _ in bounds:
        if level > 0 and ratio < bounds[level - 1] - margin:
            level -= 1

    raw_target = targets[level]
    result = round(max(min_soc, min(max_soc, raw_target)))
    held = " (gehalten)" if level != plain else ""
    branch = f"ratio={ratio:.2f} plain={plain} -> level {level} -> {raw_target:.0f}%{held}"
    return TargetSocResult(
        target_soc=result,
        level=level,
        ratio=round(ratio, 3),
        net_available_kwh=round(net_available, 2),
        remaining_hours=round(remaining_hours, 1),
        branch=branch,
    )


def charge_power_w(
    *,
    soc: float,
    battery_temp_c: float,
    battery_capacity_kwh: float,
    max_charge_power_w: float,
    forecast_score_value: int,
    balancing_active: bool = False,
) -> float:
    """Port sensor.opti_charge_power_w with upstream score bands."""
    if battery_temp_c >= 50 or battery_temp_c <= -5:
        return 0.0

    if battery_temp_c >= 45:
        temp_factor = 0.5
    elif battery_temp_c <= 0:
        temp_factor = 0.25
    else:
        temp_factor = 1.0

    capacity_w = battery_capacity_kwh * 1000.0
    score = forecast_score_value

    if score <= 1:
        if soc < 40:
            c_rate = 0.40
        elif soc < 70:
            c_rate = 0.30
        elif soc < 90:
            c_rate = 0.20
        elif soc < 97:
            c_rate = 0.10
        else:
            c_rate = 0.05
    elif score <= 4:
        if soc < 35:
            c_rate = 0.35
        elif soc < 65:
            c_rate = 0.25
        elif soc < 87:
            c_rate = 0.15
        elif soc < 97:
            c_rate = 0.08
        else:
            c_rate = 0.05
    else:
        if soc < 30:
            c_rate = 0.30
        elif soc < 60:
            c_rate = 0.20
        elif soc < 85:
            c_rate = 0.15
        elif soc < 97:
            c_rate = 0.08
        else:
            c_rate = 0.05

    power = min(capacity_w * c_rate * temp_factor, max_charge_power_w)
    if balancing_active and soc >= 96:
        power = min(power, capacity_w * 0.02)
    elif balancing_active and soc >= 92:
        power = min(power, capacity_w * 0.05)
    return float(round(power))


def price_level(current_ct_kwh: float, prices: Iterable[float]) -> tuple[str | None, float | None, int]:
    """Port sensor.opti_price_level including midrank tie handling."""
    parsed = [float(value) for value in prices if isfinite(float(value))]
    if len(parsed) < 4:
        return None, None, len(parsed)

    lower = sum(1 for value in parsed if value < current_ct_kwh)
    equal = sum(1 for value in parsed if value == current_ct_kwh)
    percentile = (lower + 0.5 * equal) / len(parsed)

    if percentile < 0.20:
        level = PRICE_LEVELS[0]
    elif percentile < 0.40:
        level = PRICE_LEVELS[1]
    elif percentile < 0.60:
        level = PRICE_LEVELS[2]
    elif percentile < 0.80:
        level = PRICE_LEVELS[3]
    else:
        level = PRICE_LEVELS[4]
    return level, round(percentile * 100.0, 1), len(parsed)


def minimum_discharge_price_ct(ladepreis_eur: float, spread_eur: float) -> float:
    """Port sensor.opti_mindestentladepreis_ct_kwh."""
    return round((ladepreis_eur + spread_eur) * 100.0, 2)


def runtime_hours(
    *,
    soc: float,
    battery_capacity_kwh: float,
    house_consumption_w: float,
    pv_power_w: float,
    min_soc: float,
) -> float | None:
    """Port sensor.opti_runtime_h."""
    if not (0 <= soc <= 100 and battery_capacity_kwh > 0 and house_consumption_w >= 0 and 0 <= min_soc <= 100):
        return None
    if pv_power_w >= 100:
        return 0.0
    if house_consumption_w == 0:
        return 999.0
    energy_kwh = max(0.0, soc - min_soc) * battery_capacity_kwh / 100.0
    return round(min(24.0, energy_kwh / (house_consumption_w / 1000.0)), 2)


def hours_until(now: datetime, target: datetime | None, fallback: float = 6.0) -> float:
    """Return hours to a target datetime using the upstream fallback."""
    if target is None:
        return fallback
    return (target - now).total_seconds() / 3600.0
