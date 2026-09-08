"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        self.entry = entry

    async def _async_update_data(self):
        """Read configured entities and calculate Opti values."""
        data = self.hass.data.get("akkusteuerung_sma", {}).get(
            self.entry.entry_id, {}
        )

        def get_value(key):
            entity = data.get(key)
            if not entity:
                return 0.0
            return float(self.hass.states.get(entity).state or 0)

        state = OptiState(
            soc=get_value("soc"),
            pv_power=get_value("pv_power"),
            house_consumption=get_value("house_consumption"),
            grid_power=get_value("grid_power"),
        )

        decision = calculate_strategy(state)

        return {
            "target_soc": decision.target_soc,
            "mode": decision.mode,
            "pv_surplus": state.pv_power - state.house_consumption,
        }
