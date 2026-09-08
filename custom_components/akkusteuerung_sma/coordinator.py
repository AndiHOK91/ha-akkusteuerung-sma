"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BATTERY_SOC_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PV_POWER_ENTITY,
)
from .strategy import OptiState, calculate_strategy


class SMAAkkuCoordinator(DataUpdateCoordinator):
    """Coordinate Opti battery strategy calculations."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=None,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.hass = hass
        self.entry = entry

    async def _async_update_data(self):
        """Read configured entities and calculate Opti values."""
        data = self.entry.data

        def get_value(key):
            entity = data.get(key)
            if not entity:
                return 0.0
            state = self.hass.states.get(entity)
            if state is None:
                return 0.0
            return float(state.state or 0)

        state = OptiState(
            soc=get_value(CONF_BATTERY_SOC_ENTITY),
            pv_power=get_value(CONF_PV_POWER_ENTITY),
            house_consumption=get_value(CONF_HOUSE_CONSUMPTION_ENTITY),
            grid_power=get_value(CONF_GRID_POWER_ENTITY),
        )

        decision = calculate_strategy(state)

        return {
            "target_soc": decision.target_soc,
            "mode": decision.mode,
            "pv_surplus": state.pv_power - state.house_consumption,
            "soc": state.soc,
        }
