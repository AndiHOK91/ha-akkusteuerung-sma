"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CAPACITY_UNIT_WH,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_UNIT,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_TEMP_ENTITY,
    CONF_FORECAST_REMAINING_ENTITY,
    CONF_FORECAST_TODAY_ENTITY,
    CONF_FORECAST_TOMORROW_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_CURRENT_ENTITY,
    CONF_PRICE_SERIES_ENTITY,
    CONF_PRICE_UNIT,
    CONF_PV_GENERATION_ENTITY,
    CONF_PV_POWER_ENTITY,
    PRICE_UNIT_EUR_KWH,
)
from .strategy import OptiState, calculate_strategy

_LOGGER = logging.getLogger(__name__)


class SMAAkkuCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read source entities and build the original Opti canonical layer."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

    def _get_state(self, config_key: str, *, optional: bool = False):
        """Return the state object configured for a source key."""
        entity_id = self.entry.data.get(config_key)
        if not entity_id:
            if optional:
                return None
            raise UpdateFailed(f"Keine Entität für {config_key} konfiguriert")

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            if optional:
                return None
            raise UpdateFailed(f"Entität {entity_id} ist nicht verfügbar")
        return state

    def _get_float(self, config_key: str, *, optional: bool = False, default: float = 0.0) -> float:
        """Return a configured source state as float."""
        state = self._get_state(config_key, optional=optional)
        if state is None:
            return default
        try:
            return float(state.state)
        except (TypeError, ValueError) as err:
            if optional:
                return default
            raise UpdateFailed(
                f"Entität {state.entity_id} liefert keinen numerischen Wert: {state.state}"
            ) from err

    def _price_to_ct(self, value: float) -> float:
        """Normalize configured price units to ct/kWh like opti_mapping."""
        if self.entry.data.get(CONF_PRICE_UNIT, PRICE_UNIT_EUR_KWH) == PRICE_UNIT_EUR_KWH:
            return value * 100.0
        return value

    def _normalize_price_list(self, value: Any) -> list[float]:
        """Normalize a today/tomorrow price attribute to ct/kWh."""
        if not isinstance(value, (list, tuple)):
            return []

        result: list[float] = []
        for item in value:
            raw = item
            if isinstance(item, dict):
                raw = item.get("total", item.get("price", item.get("value")))
            try:
                result.append(self._price_to_ct(float(raw)))
            except (TypeError, ValueError):
                continue
        return result

    def _forecast(self, config_key: str) -> tuple[float, float | None]:
        """Return forecast state and optional estimate10 attribute."""
        state = self._get_state(config_key)
        try:
            value = float(state.state)
        except (TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Entität {state.entity_id} liefert keinen numerischen Wert: {state.state}"
            ) from err

        estimate10 = state.attributes.get("estimate10")
        try:
            p10 = float(estimate10) if estimate10 is not None else None
        except (TypeError, ValueError):
            p10 = None
        return value, p10

    async def _async_update_data(self) -> dict[str, Any]:
        """Build canonical values and run the migrated strategy layer."""
        soc = self._get_float(CONF_BATTERY_SOC_ENTITY)
        battery_temp = self._get_float(
            CONF_BATTERY_TEMP_ENTITY, optional=True, default=20.0
        )

        capacity = self._get_float(CONF_BATTERY_CAPACITY_ENTITY)
        if self.entry.data.get(CONF_BATTERY_CAPACITY_UNIT, CAPACITY_UNIT_WH) == CAPACITY_UNIT_WH:
            capacity /= 1000.0

        pv_power = self._get_float(CONF_PV_POWER_ENTITY)
        pv_generation = self._get_float(CONF_PV_GENERATION_ENTITY)
        grid_export = max(0.0, self._get_float(CONF_GRID_EXPORT_ENTITY))
        grid_import = max(0.0, self._get_float(CONF_GRID_IMPORT_ENTITY))
        house_consumption = self._get_float(CONF_HOUSE_CONSUMPTION_ENTITY)

        current_price_ct = self._price_to_ct(self._get_float(CONF_PRICE_CURRENT_ENTITY))
        price_series_state = self._get_state(CONF_PRICE_SERIES_ENTITY)
        try:
            price_series_current_ct = self._price_to_ct(float(price_series_state.state))
        except (TypeError, ValueError) as err:
            raise UpdateFailed(
                f"Entität {price_series_state.entity_id} liefert keinen numerischen Wert"
            ) from err
        price_today = self._normalize_price_list(price_series_state.attributes.get("today"))
        price_tomorrow = self._normalize_price_list(price_series_state.attributes.get("tomorrow"))

        forecast_today, forecast_today_p10 = self._forecast(CONF_FORECAST_TODAY_ENTITY)
        forecast_tomorrow, forecast_tomorrow_p10 = self._forecast(CONF_FORECAST_TOMORROW_ENTITY)
        forecast_remaining, forecast_remaining_p10 = self._forecast(CONF_FORECAST_REMAINING_ENTITY)

        charge_power = self._get_float(CONF_BATTERY_CHARGE_POWER_ENTITY)
        discharge_power = self._get_float(CONF_BATTERY_DISCHARGE_POWER_ENTITY)
        battery_power = charge_power - discharge_power

        state = OptiState(
            soc=soc,
            pv_power=pv_power,
            house_consumption=house_consumption,
            grid_power=grid_import - grid_export,
        )
        decision = calculate_strategy(state)

        return {
            # Canonical values from opti_mapping.example.yaml
            "soc": soc,
            "battery_temp": battery_temp,
            "battery_capacity_kwh": capacity,
            "pv_power_w": pv_power,
            "pv_generation_w": pv_generation,
            "grid_export_w": grid_export,
            "grid_import_w": grid_import,
            "house_consumption_w": house_consumption,
            "price_current_ct_kwh": current_price_ct,
            "price_series_current_ct_kwh": price_series_current_ct,
            "price_series_today": price_today,
            "price_series_tomorrow": price_tomorrow,
            "forecast_today_kwh": forecast_today,
            "forecast_today_estimate10": forecast_today_p10,
            "forecast_tomorrow_kwh": forecast_tomorrow,
            "forecast_tomorrow_estimate10": forecast_tomorrow_p10,
            "forecast_remaining_today_kwh": forecast_remaining,
            "forecast_remaining_today_estimate10": forecast_remaining_p10,
            "battery_power_w": battery_power,
            "simultaneous_charge_discharge": charge_power > 0 and discharge_power > 0,
            # Current migration outputs; replaced by full opti_derived/strategy parity later.
            "target_soc": decision.target_soc,
            "mode": decision.mode,
            "pv_surplus": pv_power - house_consumption,
        }
