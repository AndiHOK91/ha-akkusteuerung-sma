"""Surplus gates ported from packages/opti_derived.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class DebouncedBoolean:
    """Stateful symmetric delay_on/delay_off helper."""

    state: bool = False
    pending: bool | None = None
    pending_since: datetime | None = None

    def update(self, raw_state: bool, now: datetime, delay_seconds: int) -> bool:
        """Apply the upstream template binary_sensor delay semantics."""
        if raw_state == self.state:
            self.pending = None
            self.pending_since = None
            return self.state

        if self.pending != raw_state:
            self.pending = raw_state
            self.pending_since = now
            return self.state

        if self.pending_since is not None and now - self.pending_since >= timedelta(seconds=delay_seconds):
            self.state = raw_state
            self.pending = None
            self.pending_since = None
        return self.state


@dataclass(frozen=True, slots=True)
class SurplusSignalResult:
    """One calculated surplus gate and its diagnostics."""

    state: bool
    value_without_battery_w: float
    threshold_on_w: float
    threshold_off_w: float
    scarcity_gate_open: bool | None = None


def surplus_70_raw(
    *,
    grid_export_w: float,
    battery_power_w: float,
    threshold_on_w: float,
    was_on: bool,
) -> tuple[bool, float, float]:
    """Raw state for binary_sensor.opti_ueberschuss_70_aktiv."""
    value = max(0.0, grid_export_w + battery_power_w)
    threshold_off = threshold_on_w - 1000.0
    raw = threshold_on_w > 0 and (
        value > threshold_on_w
        or (threshold_off > 0 and value >= threshold_off and was_on)
    )
    return raw, value, threshold_off


def surplus_ac_raw(
    *,
    pv_power_w: float,
    battery_power_w: float,
    threshold_on_w: float,
    was_on: bool,
) -> tuple[bool, float, float]:
    """Raw state for binary_sensor.opti_ueberschuss_ac_aktiv."""
    value = max(0.0, pv_power_w + battery_power_w)
    threshold_off = threshold_on_w - 300.0
    raw = threshold_on_w > 0 and (
        value > threshold_on_w
        or (threshold_off > 0 and value >= threshold_off and was_on)
    )
    return raw, value, threshold_off


def surplus_veto_raw(
    *,
    grid_export_w: float,
    grid_import_w: float,
    battery_power_w: float,
    threshold_on_w: float,
    threshold_off_w: float,
    forecast_surplus_kwh: float | None,
    needed_full_kwh: float | None,
    scarcity_factor: float,
    was_on: bool,
) -> tuple[bool, float, bool]:
    """Raw state for binary_sensor.opti_ueberschuss_veto_aktiv."""
    value = max(0.0, grid_export_w - grid_import_w + battery_power_w)

    if needed_full_kwh is not None and needed_full_kwh <= 0:
        scarcity_open = False
    elif forecast_surplus_kwh is None or needed_full_kwh is None:
        # Upstream deliberately fails open for forecast uncertainty: only a
        # positively proven rich day may suppress a real measured export.
        scarcity_open = True
    else:
        scarcity_open = (
            forecast_surplus_kwh < needed_full_kwh * scarcity_factor
            or was_on
            and forecast_surplus_kwh < needed_full_kwh * scarcity_factor * 1.2
        )

    raw = scarcity_open and (
        value > threshold_on_w
        or (threshold_off_w > 0 and value >= threshold_off_w and was_on)
    )
    return raw, value, scarcity_open
