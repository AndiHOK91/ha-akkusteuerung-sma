"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BATTERY_SOC_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PV_POWER_ENTITY,
)
from .strategy import OptiState, calculate_strategy

_LOGGER = logging.getLogger(__name__)


class SMAAkkuCoordinator(DataUpdateCoordinator):
    """Coordinate Opti battery strategy calculations."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

    def _get_float_state(self, config_key: str) -> float:
        """Return a configured entity state as float.

        Required source values must be valid. Returning 0 for an unavailable
        source could create unsafe strategy decisions, so an invalid value
        fails the coordinator update instead.
        """
        entity_id = self.entry.data.get(config_key)
        if not entity_id:
            raise UpdateFailed(f"Keine Entität für {config_key} konfiguriert")

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            raise UpdateFailed(f"Entität {entity_id} ist nicht verfügbar")

        try:
            return float(state.state)
        except (TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Entität {entity_id} liefert keinen numerischen Wert: {state.state}"
            ) from err

    async def _async_update_data(self):
        """Read configured entities and calculate Opti values."""
        state = OptiState(
            soc=self._get_float_state(CONF_BATTERY_SOC_ENTITY),
            pv_power=self._get_float_state(CONF_PV_POWER_ENTITY),
            house_consumption=self._get_float_state(CONF_HOUSE_CONSUMPTION_ENTITY),
            grid_power=self._get_float_state(CONF_GRID_POWER_ENTITY),
        )

        decision = calculate_strategy(state)

        return {
            "target_soc": decision.target_soc,
            "mode": decision.mode,
            "pv_surplus": state.pv_power - state.house_consumption,
            "soc": state.soc,
        }
