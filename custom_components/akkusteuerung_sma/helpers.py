"""Helper defaults migrated from sma_helpers.yaml."""

from __future__ import annotations


DEFAULT_MIN_SOC = 20
DEFAULT_MAX_SOC = 100
DEFAULT_MAX_CHARGE_POWER = 5000


class AkkuSettings:
    """Runtime settings used by the strategy."""

    def __init__(
        self,
        minimum_soc: float = DEFAULT_MIN_SOC,
        maximum_soc: float = DEFAULT_MAX_SOC,
        maximum_charge_power: float = DEFAULT_MAX_CHARGE_POWER,
    ) -> None:
        self.minimum_soc = minimum_soc
        self.maximum_soc = maximum_soc
        self.maximum_charge_power = maximum_charge_power
