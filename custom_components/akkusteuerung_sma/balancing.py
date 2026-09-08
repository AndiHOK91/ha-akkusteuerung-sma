"""Balancing/deep-charge logic ported from upstream YAML."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class BalancingPersistentState:
    days_since_full: int = 0
    done_minutes: int = 0
    last_completion: datetime | None = None
    completion_valid: bool = False
    last_daily_increment: date | None = None
    last_minute_tick: tuple[int, int, int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class BalancingWatchdogResult:
    mode: str
    reason: str
    due_reason: str


def update_balancing_counters(
    state: BalancingPersistentState,
    *,
    now: datetime,
    soc: float | None,
    done_soc: float | None,
) -> bool:
    """Update persistent counters; return whether persistent data changed."""
    changed = False

    # Daily increment once per local day at/after 23:59 if no completion today.
    completed_today = (
        state.completion_valid
        and state.last_completion is not None
        and state.last_completion.date() == now.date()
    )
    if (
        now.hour == 23
        and now.minute >= 59
        and state.last_daily_increment != now.date()
    ):
        if not completed_today:
            state.days_since_full += 1
        state.last_daily_increment = now.date()
        changed = True

    # Only one count per minute may advance the 30-minute confirmation.
    minute_key = (now.year, now.month, now.day, now.hour, now.minute)
    if state.last_minute_tick != minute_key:
        state.last_minute_tick = minute_key
        changed = True

        if soc is None or done_soc is None or soc <= done_soc or completed_today:
            if state.done_minutes != 0:
                state.done_minutes = 0
                changed = True
        else:
            if state.done_minutes > 28:
                state.days_since_full = 0
                state.done_minutes = 0
                state.last_completion = now
                state.completion_valid = True
                changed = True
            else:
                state.done_minutes += 1
                changed = True

    return changed


def balancing_watchdog(
    *,
    soc: float | None,
    days_since_full: int,
    interval_days: int,
    grace_days: int,
    max_paid_ct: float,
    current_price_ct: float | None,
    feed_in_tariff_ct: float,
    price_level: str | None,
    is_day: bool,
    grid_balancing_enabled: bool,
    resting_cell_spread_mv: float | None,
    spread_threshold_mv: float,
    spread_cooldown_days: int,
) -> BalancingWatchdogResult:
    """Port sensor.opti_balancing_watchdog."""
    spread = resting_cell_spread_mv if resting_cell_spread_mv is not None else -1.0
    demand = (
        spread_threshold_mv > 0
        and spread >= 0
        and spread >= spread_threshold_mv
        and days_since_full >= spread_cooldown_days
    )
    due = (
        interval_days > 0
        and soc is not None
        and soc >= 0
        and (days_since_full >= interval_days or demand)
    )

    if not due:
        if interval_days <= 0:
            reason = "Watchdog aus (Intervall 0)"
        elif soc is None or soc < 0:
            reason = "opti_soc fehlt"
        else:
            reason = (
                f"nicht faellig ({days_since_full}/{interval_days} Tage, "
                f"Spreizung {spread:g}/{spread_threshold_mv:g}mV)"
            )
        return BalancingWatchdogResult("aus", reason, "keiner")

    due_reason = "zeit" if days_since_full >= interval_days else "spreizung"
    if is_day:
        return BalancingWatchdogResult(
            "pv",
            f"PV-Vollladung ({'Zeit' if due_reason == 'zeit' else f'Spreizung {spread:g}mV'}, {days_since_full} Tage seit voll)",
            due_reason,
        )

    if (
        grid_balancing_enabled
        and current_price_ct is not None
        and current_price_ct < feed_in_tariff_ct
    ):
        return BalancingWatchdogResult(
            "netz",
            f"Gratis-Netz ({current_price_ct:g}ct < EEG {feed_in_tariff_ct:g}ct)",
            due_reason,
        )

    paid_window = (
        days_since_full >= interval_days + grace_days
        and current_price_ct is not None
        and price_level in {"VERY_CHEAP", "CHEAP"}
        and max_paid_ct > 0
        and current_price_ct <= max_paid_ct
    )
    if grid_balancing_enabled and paid_window:
        return BalancingWatchdogResult(
            "netz",
            f"Bezahltes Netz ({current_price_ct:g}ct <= Deckel {max_paid_ct:g}ct, nach Karenz)",
            due_reason,
        )
    if not grid_balancing_enabled and (
        (current_price_ct is not None and current_price_ct < feed_in_tariff_ct)
        or paid_window
    ):
        return BalancingWatchdogResult(
            "aus",
            "Netz-Balancing gesperrt (opti_balancing_netzladen aus)",
            due_reason,
        )
    return BalancingWatchdogResult("aus", "warte auf besseres Fenster", due_reason)
