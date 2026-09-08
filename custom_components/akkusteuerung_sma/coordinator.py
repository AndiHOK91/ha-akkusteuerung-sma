"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    DOMAIN,
    PRICE_UNIT_EUR_KWH,
)
from .derived import (
    charge_power_w,
    effective_forecast_remaining,
    forecast_score,
    forecast_score_tomorrow,
    hours_until,
    minimum_discharge_price_ct,
    price_level,
    runtime_hours,
    target_soc,
)

_LOGGER = logging.getLogger(__name__)


class SMAAkkuCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read source entities and calculate the migrated Opti core layer."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            logger=_LOGGER,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self._target_level: int | None = None

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

    def _get_float(
        self,
        config_key: str,
        *,
        optional: bool = False,
        default: float = 0.0,
    ) -> float:
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

    def _setting(self, key: str, default: Any) -> Any:
        """Return a migrated helper value without relying on its entity_id."""
        runtime = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        return runtime.get("settings", {}).get(key, default)

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

    def _next_setting(self):
        """Return sun.sun next_setting as a local datetime."""
        sun = self.hass.states.get("sun.sun")
        if sun is None:
            return None
        raw = sun.attributes.get("next_setting")
        if raw is None:
            return None
        if isinstance(raw, str):
            parsed = dt_util.parse_datetime(raw)
        else:
            parsed = raw
        return dt_util.as_local(parsed) if parsed is not None else None

    async def _async_update_data(self) -> dict[str, Any]:
        """Build canonical values and the first fully ported derived sensors."""
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

        # The upstream statistics sensor is a preferred input but all core
        # templates explicitly fall back to current house consumption. Until the
        # rolling statistics entity is ported, use that documented fallback.
        house_average_w = house_consumption

        optimism = float(self._setting("opti_forecast_optimismus", 0.0))
        effective_remaining = effective_forecast_remaining(
            forecast_remaining, forecast_remaining_p10, optimism
        )
        tomorrow_score = forecast_score_tomorrow(
            forecast_tomorrow,
            forecast_tomorrow_p10,
            house_average_w,
            optimism,
        )

        now = dt_util.now()
        next_setting = self._next_setting()
        after_sunset = (
            next_setting is not None and next_setting.date() != now.date()
        )
        score_hours = hours_until(now, next_setting, fallback=0.0)
        score_result = forecast_score(
            effective_remaining_kwh=effective_remaining,
            battery_capacity_kwh=capacity,
            soc=soc,
            house_consumption_w=house_average_w,
            hours_to_sunset=score_hours,
            after_sunset=after_sunset,
            tomorrow_score=tomorrow_score,
        )

        target_hours = hours_until(now, next_setting, fallback=6.0)
        target_result = target_soc(
            battery_capacity_kwh=capacity,
            effective_remaining_kwh=effective_remaining,
            house_consumption_w=house_average_w,
            remaining_hours=target_hours,
            min_soc=float(self._setting("minsoc", 0.0)),
            max_soc=float(self._setting("maxsoc", 0.0)),
            grid_charging=bool(self._setting("hausakku_aus_netz_laden", False)),
            previous_level=self._target_level,
        )
        self._target_level = target_result.level

        calculated_charge_power = charge_power_w(
            soc=soc,
            battery_temp_c=battery_temp,
            battery_capacity_kwh=capacity,
            max_charge_power_w=float(
                self._setting("akkusteuerung_max_ladestaerke", 0.0)
            ),
            forecast_score_value=score_result.score,
            balancing_active=False,
        )

        level, percentile, price_count = price_level(
            current_price_ct, [*price_today, *price_tomorrow]
        )
        ladepreis = float(self._setting("ladepreis", -1.0))
        price_spread = float(
            self._setting("mindestpreisdifferenz_lade_entladepreis", 0.0)
        )
        min_discharge = minimum_discharge_price_ct(ladepreis, price_spread)
        runtime = runtime_hours(
            soc=soc,
            battery_capacity_kwh=capacity,
            house_consumption_w=house_consumption,
            pv_power_w=pv_power,
            min_soc=float(self._setting("minsoc", 0.0)),
        )

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
            # Ported derived core
            "forecast_effective_remaining_kwh": effective_remaining,
            "forecast_effective_median_kwh": forecast_remaining,
            "forecast_effective_p10_kwh": (
                forecast_remaining_p10
                if forecast_remaining_p10 is not None and forecast_remaining_p10 > 0
                else forecast_remaining
            ),
            "forecast_effective_alpha": max(0.0, min(100.0, optimism)) / 100.0,
            "forecast_score_tomorrow": tomorrow_score,
            "forecast_score": score_result.score,
            "forecast_score_remaining_kwh": score_result.remaining_kwh,
            "forecast_score_needed_full_kwh": score_result.needed_full_kwh,
            "forecast_score_hours_to_sunset": score_result.hours_to_sunset,
            "forecast_score_pv_surplus_kwh": score_result.pv_surplus_kwh,
            "forecast_score_excess_over_full_kwh": score_result.excess_over_full_kwh,
            "forecast_score_reason": score_result.reason,
            "target_soc": target_result.target_soc,
            "target_soc_level": target_result.level,
            "target_soc_ratio": target_result.ratio,
            "target_soc_net_available_kwh": target_result.net_available_kwh,
            "target_soc_remaining_hours": target_result.remaining_hours,
            "target_soc_branch": target_result.branch,
            "charge_power_w": calculated_charge_power,
            "price_level": level,
            "price_level_percentile": percentile,
            "price_level_count": price_count,
            "mindestentladepreis_ct_kwh": min_discharge,
            "mindestentladepreis_ladepreis_ct": round(ladepreis * 100.0, 2),
            "mindestentladepreis_differenz_ct": round(price_spread * 100.0, 2),
            "runtime_h": runtime,
        }
