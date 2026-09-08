"""Peak-reserve calculations ported from upstream opti_derived.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PeakReserveResult:
    """Calculated reserve for upcoming expensive price slots."""

    valid: bool
    reserve_ve_soc: float
    reserve_soc: float
    peak_hours_ve: float
    peak_hours_exp: float
    required_kwh: float
    min_price_before_peak_ct: float | None
    peak_price_avg_ct: float | None
    peak_price_ve_avg_ct: float | None
    window_min_ct: float | None
    horizon_end: datetime
    branch: str


def pv_rich_day(
    *,
    next_rising: datetime | None,
    now: datetime,
    today_score: float | None,
    tomorrow_score: float | None,
    previous_state: bool,
) -> bool:
    """Port binary_sensor.opti_pv_reichtag.

    Gate opens only for April-August sunrises before 06:30 local time. Score 10
    turns it on, 9 holds an existing on state, and <=8 turns it off. Missing
    score preserves the previous state exactly like the template sensor.
    """
    if next_rising is None:
        return False
    if not 4 <= next_rising.month <= 8:
        return False
    if next_rising.hour * 60 + next_rising.minute >= 6 * 60 + 30:
        return False

    score = today_score if next_rising.date() == now.date() else tomorrow_score
    if score is None:
        return previous_state
    return score >= 10 or (previous_state and score >= 9)


def _valid_raster(length: int) -> bool:
    return 20 <= length <= 27 or 80 <= length <= 108


def calculate_peak_reserve(
    *,
    now: datetime,
    next_rising: datetime | None,
    sun_above_horizon: bool,
    today_score: float,
    tomorrow_score: float,
    rich_day: bool,
    prices_today: Sequence[float],
    prices_tomorrow: Sequence[float],
    battery_capacity_kwh: float,
    peak_consumption_kw: float,
    min_soc: float,
    max_soc: float,
    min_peak_markup_ct: float,
) -> PeakReserveResult:
    """Port sensor.opti_peak_reserve_soc and its active gate."""
    lists = (prices_today, prices_tomorrow)
    raster_ok = all(not arr or _valid_raster(len(arr)) for arr in lists)

    local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    all_prices: list[float] = []
    future: list[tuple[datetime, float, float]] = []
    if raster_ok:
        for index, arr in enumerate(lists):
            if not arr:
                continue
            slot_h = 24.0 / len(arr)
            base = local_midnight + timedelta(days=index)
            for slot, raw_price in enumerate(arr):
                price = float(raw_price)
                all_prices.append(price)
                future.append((base + timedelta(hours=slot * slot_h), price, slot_h))

    n = len(all_prices) if raster_ok else 0
    horizon_max = now + timedelta(hours=36)
    start = now.replace(minute=0, second=0, microsecond=0)

    if sun_above_horizon and today_score > 2:
        horizon_end = start
    elif next_rising is not None:
        rise_score = today_score if next_rising.date() == now.date() else tomorrow_score
        if rise_score > 2:
            buffer_h = 1 if rich_day else 3
            horizon_end = min(next_rising + timedelta(hours=buffer_h), horizon_max)
        else:
            horizon_end = horizon_max
    else:
        horizon_end = horizon_max

    window_prices = [
        price for timestamp, price, _slot_h in future
        if start <= timestamp < horizon_end
    ] if n >= 4 else []
    window_min = min(window_prices) if window_prices else None

    ve_hours = 0.0
    exp_hours = 0.0
    min_before_peak: float | None = None
    peak_sum = 0.0
    peak_count = 0
    ve_sum = 0.0
    ve_count = 0
    peak_seen = False

    if n >= 4:
        for timestamp, price, slot_h in future:
            if not start <= timestamp < horizon_end:
                continue

            lower = sum(1 for candidate in all_prices if candidate < price)
            equal = sum(1 for candidate in all_prices if candidate == price)
            percentile = (lower + 0.5 * equal) / n
            economic_peak = (
                window_min is None or price >= window_min + min_peak_markup_ct
            )

            if percentile >= 0.80 and economic_peak:
                ve_hours += slot_h
                peak_sum += price
                peak_count += 1
                ve_sum += price
                ve_count += 1
                peak_seen = True
            elif percentile >= 0.60 and economic_peak:
                exp_hours += slot_h
                peak_sum += price
                peak_count += 1
                peak_seen = True
            elif not peak_seen:
                min_before_peak = (
                    price if min_before_peak is None else min(min_before_peak, price)
                )

    eta = 0.9
    ve_kwh = ve_hours * peak_consumption_kw / eta
    required_kwh = (ve_hours + exp_hours) * peak_consumption_kw / eta
    if battery_capacity_kwh > 0:
        reserve_ve_soc = min(
            min_soc + ve_kwh / battery_capacity_kwh * 100.0,
            max_soc,
        )
        reserve_soc = min(
            min_soc + required_kwh / battery_capacity_kwh * 100.0,
            max_soc,
        )
    else:
        reserve_ve_soc = max_soc
        reserve_soc = max_soc

    return PeakReserveResult(
        valid=n >= 4,
        reserve_ve_soc=round(reserve_ve_soc, 1),
        reserve_soc=round(reserve_soc, 1),
        peak_hours_ve=round(ve_hours, 2),
        peak_hours_exp=round(exp_hours, 2),
        required_kwh=round(required_kwh, 2),
        min_price_before_peak_ct=(
            round(min_before_peak, 2) if min_before_peak is not None else None
        ),
        peak_price_avg_ct=(round(peak_sum / peak_count, 2) if peak_count else None),
        peak_price_ve_avg_ct=(round(ve_sum / ve_count, 2) if ve_count else None),
        window_min_ct=(round(window_min, 2) if window_min is not None else None),
        horizon_end=horizon_end,
        branch=(
            f"ve={ve_hours} exp={exp_hours} n={n} "
            f"ende={horizon_end.strftime('%d.%m %H:%M')}"
        ),
    )


def charge_ceiling_active(
    *,
    soc: float,
    max_soc: float,
    previous_state: bool,
    previous_max_soc: float | None,
) -> bool:
    """Port binary_sensor.opti_ladedeckel_aktiv state memory."""
    held = previous_state and previous_max_soc == max_soc
    return soc >= max_soc or (held and soc >= max_soc - 3.0)
