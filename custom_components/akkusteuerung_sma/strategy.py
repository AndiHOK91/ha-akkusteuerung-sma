"""Opti battery strategy layer.

This module is the future home of the migrated logic from
ha-opti-akkusteuerung. The strategy intentionally does not contain
hardware specific code. It consumes canonical values and produces
strategy decisions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OptiState:
    """Canonical input values used by the strategy."""

    soc: float = 0.0
    pv_power: float = 0.0
    house_consumption: float = 0.0
    grid_power: float = 0.0


@dataclass(slots=True)
class OptiDecision:
    """Result of a strategy calculation."""

    target_soc: float = 0.0
    mode: str = "idle"


def calculate_strategy(state: OptiState) -> OptiDecision:
    """Calculate a first strategy result.

    The detailed Opti YAML logic will be migrated here step by step.
    """

    surplus = state.pv_power - state.house_consumption

    if surplus > 0:
        return OptiDecision(target_soc=100.0, mode="pv_charge")

    return OptiDecision(target_soc=state.soc, mode="idle")
