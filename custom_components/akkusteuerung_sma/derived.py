"""Derived values migrated from opti_derived.yaml.

This module contains calculated values only. Hardware communication stays
outside of this layer.
"""

from __future__ import annotations


def calculate_surplus(pv_power: float, house_consumption: float) -> float:
    """Return available PV surplus."""
    return max(0.0, pv_power - house_consumption)


def calculate_target_soc(
    current_soc: float,
    surplus: float,
    minimum_soc: float = 20.0,
    maximum_soc: float = 100.0,
) -> float:
    """Calculate a first target SOC value."""
    if surplus > 0:
        return maximum_soc
    return max(minimum_soc, current_soc)


def calculate_price_level(price: float | None) -> str:
    """Classify electricity price level."""
    if price is None:
        return "unknown"
    if price < 0:
        return "negative"
    if price < 0.20:
        return "cheap"
    if price > 0.40:
        return "expensive"
    return "normal"
