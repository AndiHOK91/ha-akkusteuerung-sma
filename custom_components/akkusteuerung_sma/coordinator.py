"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .balancing import (
    BalancingPersistentState,
    balancing_watchdog,
    update_balancing_counters,
)
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
from .peak import calculate_peak_reserve, charge_ceiling_active, pv_rich_day
from .statistics import RollingMean
from .storage import BalancingStorage
from .strategy import MODE_AUTO, StrategyInput, decide_strategy
from .surplus import DebouncedBoolean, surplus_70_raw, surplus_ac_raw, surplus_veto_raw

_LOGGER = logging.getLogger(__name__)


class SMAAkkuCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Read source entities and calculate the migrated Opti layers."""

    def __init__(
        self,
        hass,
        entry,
        *,
        balancing_state: BalancingPersistentState,
        balancing_storage: BalancingStorage,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self._balancing_state = balancing_state
        self._balancing_storage = balancing_storage
        self._target_level: int | None = None
        self._pv_rich_day = False
        self._charge_ceiling_active = False
        self._charge_ceiling_max_soc: float | None = None
        self._surplus_70 = DebouncedBoolean()
        self._surplus_ac = DebouncedBoolean()
        self._surplus_veto = DebouncedBoolean()
        self._battery_mean_30m = RollingMean(timedelta(minutes=30), 360)
        self._house_mean_60m = RollingMean(timedelta(minutes=60), 1500)

    def _runtime(self) -> dict[str, Any]:
        return self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})

    def _settings(self) -> dict[str, Any]:
        return self._runtime().setdefault("settings", {})

    def _setting(self, key: str, default: Any) -> Any:
        return self._settings().get(key, default)

    def _get_state(self, config_key: str, *, optional: bool = False):
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
        default: float | None = 0.0,
    ) -> float | None:
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

    def _price_to_ct(self, value: float | None) -> float | None:
        if value is None:
            return None
        if self.entry.data.get(CONF_PRICE_UNIT, PRICE_UNIT_EUR_KWH) == PRICE_UNIT_EUR_KWH:
            return value * 100.0
        return value

    def _normalize_price_list(self, value: Any) -> list[float]:
        if not isinstance(value, (list, tuple)):
            return []
        result: list[float] = []
        for item in value:
            raw = item
            if isinstance(item, dict):
                raw = item.get("total", item.get("price", item.get("value")))
            try:
                converted = self._price_to_ct(float(raw))
            except (TypeError, ValueError):
                continue
            if converted is not None:
                result.append(converted)
        return result

    def _forecast(self, config_key: str) -> tuple[float, float | None]:
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

    def _sun_datetime(self, attribute: str):
        sun = self.hass.states.get("sun.sun")
        if sun is None:
            return None
        raw = sun.attributes.get(attribute)
        if raw is None:
            return None
        parsed = dt_util.parse_datetime(raw) if isinstance(raw, str) else raw
        return dt_util.as_local(parsed) if parsed is not None else None

    async def _async_update_data(self) -> dict[str, Any]:
        soc = self._get_float(CONF_BATTERY_SOC_ENTITY)
        battery_temp = self._get_float(
            CONF_BATTERY_TEMP_ENTITY, optional=True, default=20.0
        )
        capacity = self._get_float(CONF_BATTERY_CAPACITY_ENTITY)
        if soc is None or capacity is None:
            raise UpdateFailed("SoC oder Batteriekapazität fehlt")
        if self.entry.data.get(CONF_BATTERY_CAPACITY_UNIT, CAPACITY_UNIT_WH) == CAPACITY_UNIT_WH:
            capacity /= 1000.0

        pv_power = self._get_float(CONF_PV_POWER_ENTITY)
        pv_generation = self._get_float(CONF_PV_GENERATION_ENTITY)
        grid_export_raw = self._get_float(CONF_GRID_EXPORT_ENTITY)
        grid_import_raw = self._get_float(CONF_GRID_IMPORT_ENTITY)
        house_consumption = self._get_float(CONF_HOUSE_CONSUMPTION_ENTITY)
        charge_power = self._get_float(CONF_BATTERY_CHARGE_POWER_ENTITY)
        discharge_power = self._get_float(CONF_BATTERY_DISCHARGE_POWER_ENTITY)
        required_values = (
            pv_power,
            pv_generation,
            grid_export_raw,
            grid_import_raw,
            house_consumption,
            charge_power,
            discharge_power,
        )
        if any(value is None for value in required_values):
            raise UpdateFailed("Eine erforderliche Leistungsquelle fehlt")
        grid_export = max(0.0, grid_export_raw)
        grid_import = max(0.0, grid_import_raw)
        battery_power = charge_power - discharge_power

        # Price sources are deliberately fail-closed, not coordinator-fatal.
        # This mirrors upstream: price-dependent branches stop, while MinSOC,
        # charge ceiling, balancing/PV and target-SoC safety can keep running.
        current_price_ct = self._price_to_ct(
            self._get_float(CONF_PRICE_CURRENT_ENTITY, optional=True, default=None)
        )
        price_series_state = self._get_state(CONF_PRICE_SERIES_ENTITY, optional=True)
        price_series_current_ct: float | None = None
        price_today: list[float] = []
        price_tomorrow: list[float] = []
        if price_series_state is not None:
            try:
                price_series_current_ct = self._price_to_ct(float(price_series_state.state))
            except (TypeError, ValueError):
                price_series_current_ct = None
            price_today = self._normalize_price_list(price_series_state.attributes.get("today"))
            price_tomorrow = self._normalize_price_list(price_series_state.attributes.get("tomorrow"))

        forecast_today, forecast_today_p10 = self._forecast(CONF_FORECAST_TODAY_ENTITY)
        forecast_tomorrow, forecast_tomorrow_p10 = self._forecast(CONF_FORECAST_TOMORROW_ENTITY)
        forecast_remaining, forecast_remaining_p10 = self._forecast(CONF_FORECAST_REMAINING_ENTITY)

        now = dt_util.now()
        battery_average_30m_w = round(self._battery_mean_30m.add(now, battery_power))
        house_average_w = round(self._house_mean_60m.add(now, house_consumption))

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

        next_setting = self._sun_datetime("next_setting")
        next_rising = self._sun_datetime("next_rising")
        sun_state = self.hass.states.get("sun.sun")
        sun_above_horizon = sun_state is not None and sun_state.state == "above_horizon"
        after_sunset = next_setting is not None and next_setting.date() != now.date()

        score_result = forecast_score(
            effective_remaining_kwh=effective_remaining,
            battery_capacity_kwh=capacity,
            soc=soc,
            house_consumption_w=house_average_w,
            hours_to_sunset=hours_until(now, next_setting, fallback=0.0),
            after_sunset=after_sunset,
            tomorrow_score=tomorrow_score,
        )

        min_soc = float(self._setting("minsoc", 0.0))
        max_soc = float(self._setting("maxsoc", 0.0))
        target_result = target_soc(
            battery_capacity_kwh=capacity,
            effective_remaining_kwh=effective_remaining,
            house_consumption_w=house_average_w,
            remaining_hours=hours_until(now, next_setting, fallback=6.0),
            min_soc=min_soc,
            max_soc=max_soc,
            grid_charging=bool(self._setting("hausakku_aus_netz_laden", False)),
            previous_level=self._target_level,
        )
        self._target_level = target_result.level

        self._pv_rich_day = pv_rich_day(
            next_rising=next_rising,
            now=now,
            today_score=float(score_result.score),
            tomorrow_score=float(tomorrow_score),
            previous_state=self._pv_rich_day,
        )
        peak_result = calculate_peak_reserve(
            now=now,
            next_rising=next_rising,
            sun_above_horizon=sun_above_horizon,
            today_score=float(score_result.score),
            tomorrow_score=float(tomorrow_score),
            rich_day=self._pv_rich_day,
            prices_today=price_today,
            prices_tomorrow=price_tomorrow,
            battery_capacity_kwh=capacity,
            peak_consumption_kw=float(self._setting("opti_peak_verbrauch_kw", 0.1)),
            min_soc=min_soc,
            max_soc=max_soc,
            min_peak_markup_ct=float(self._setting("opti_peak_min_aufschlag_ct", 0.0)),
        )
        peak_active = peak_result.valid and capacity > 0 and peak_result.required_kwh > 0

        self._charge_ceiling_active = charge_ceiling_active(
            soc=soc,
            max_soc=max_soc,
            previous_state=self._charge_ceiling_active,
            previous_max_soc=self._charge_ceiling_max_soc,
        )
        self._charge_ceiling_max_soc = max_soc

        threshold_70 = float(
            self._setting("akkusteuerung_wr_70proz_ueberschuss_grenze", 0.0)
        )
        raw_70, surplus_70_w, threshold_70_off = surplus_70_raw(
            grid_export_w=grid_export,
            battery_power_w=battery_power,
            threshold_on_w=threshold_70,
            was_on=self._surplus_70.state,
        )
        surplus_70_active = self._surplus_70.update(raw_70, now, 30)

        threshold_ac = float(
            self._setting("akkusteuerung_wr_ac_ueberschuss_grenze", 0.0)
        )
        raw_ac, surplus_ac_w, threshold_ac_off = surplus_ac_raw(
            pv_power_w=pv_power,
            battery_power_w=battery_power,
            threshold_on_w=threshold_ac,
            was_on=self._surplus_ac.state,
        )
        surplus_ac_active = self._surplus_ac.update(raw_ac, now, 30)

        veto_on = float(self._setting("akkusteuerung_ueberschuss_veto_grenze", 200.0))
        veto_off = float(
            self._setting("akkusteuerung_ueberschuss_veto_aus_grenze", 100.0)
        )
        scarcity_factor = float(
            self._setting("akkusteuerung_ueberschuss_veto_knappheit_faktor", 1.0)
        )
        raw_veto, surplus_veto_w, scarcity_open = surplus_veto_raw(
            grid_export_w=grid_export,
            grid_import_w=grid_import,
            battery_power_w=battery_power,
            threshold_on_w=veto_on,
            threshold_off_w=veto_off,
            forecast_surplus_kwh=score_result.pv_surplus_kwh,
            needed_full_kwh=score_result.needed_full_kwh,
            scarcity_factor=scarcity_factor,
            was_on=self._surplus_veto.state,
        )
        surplus_veto_active = self._surplus_veto.update(raw_veto, now, 60)

        done_soc = float(self._setting("opti_balancing_done_soc", 98.5))
        balancing_changed = update_balancing_counters(
            self._balancing_state,
            now=now,
            soc=soc,
            done_soc=done_soc,
        )
        if balancing_changed:
            await self._balancing_storage.async_save(self._balancing_state)

        level, percentile, price_count = price_level(
            current_price_ct, [*price_today, *price_tomorrow]
        )
        balancing_result = balancing_watchdog(
            soc=soc,
            days_since_full=self._balancing_state.days_since_full,
            interval_days=int(self._setting("opti_balancing_intervall_tage", 0)),
            grace_days=int(self._setting("opti_balancing_karenz_tage", 0)),
            max_paid_ct=float(self._setting("opti_balancing_max_ct", 0.0)),
            current_price_ct=current_price_ct,
            feed_in_tariff_ct=float(self._setting("opti_einspeiseverguetung_ct", 0.0)),
            price_level=level,
            is_day=sun_above_horizon,
            grid_balancing_enabled=bool(
                self._setting("opti_balancing_netzladen", False)
            ),
            resting_cell_spread_mv=None,
            spread_threshold_mv=0.0,
            spread_cooldown_days=0,
        )
        balancing_active = balancing_result.mode in {"pv", "netz"}

        calculated_charge_power = charge_power_w(
            soc=soc,
            battery_temp_c=battery_temp if battery_temp is not None else 20.0,
            battery_capacity_kwh=capacity,
            max_charge_power_w=float(
                self._setting("akkusteuerung_max_ladestaerke", 0.0)
            ),
            forecast_score_value=score_result.score,
            balancing_active=balancing_active,
        )

        ladepreis = float(self._setting("ladepreis", -1.0))
        discharge_spread = float(
            self._setting("mindestpreisdifferenz_lade_entladepreis", 0.0)
        )
        min_discharge = minimum_discharge_price_ct(ladepreis, discharge_spread)
        runtime = runtime_hours(
            soc=soc,
            battery_capacity_kwh=capacity,
            house_consumption_w=house_consumption,
            pv_power_w=pv_power,
            min_soc=min_soc,
        )

        current_mode = str(self._setting("akkusteuerung_modus", MODE_AUTO))
        core_valid = 0 <= soc <= 100 and capacity > 0
        decision = decide_strategy(
            StrategyInput(
                master_enabled=bool(self._setting("akku_opti_automatik", False)),
                core_valid=core_valid,
                soc=soc,
                min_soc=min_soc,
                max_soc=max_soc,
                target_soc=target_result.target_soc,
                current_mode=current_mode,
                is_day=sun_above_horizon,
                forecast_score=float(score_result.score),
                forecast_score_tomorrow=float(tomorrow_score),
                price_level=level,
                current_price_ct=current_price_ct,
                forecast_grid_charge_enabled=bool(
                    self._setting("opti_prognose_netzladen", False)
                ),
                pv_surplus_charge_enabled=bool(
                    self._setting("opti_pv_ueberschuss_ladung", False)
                ),
                winter_charging_allowed=True,
                feed_in_tariff_ct=float(
                    self._setting("opti_einspeiseverguetung_ct", 0.0)
                ),
                grid_charge_spread_ct=float(
                    self._setting("opti_netzlade_spread_ct", 0.0)
                ),
                hold_spread_ct=float(self._setting("opti_halte_spread_ct", 0.0)),
                peak_reserve_active=peak_active,
                peak_reserve_soc=(
                    peak_result.reserve_soc if peak_result.valid else None
                ),
                peak_reserve_ve_soc=(
                    peak_result.reserve_ve_soc if peak_result.valid else None
                ),
                min_price_before_peak_ct=peak_result.min_price_before_peak_ct,
                peak_price_avg_ct=peak_result.peak_price_avg_ct,
                peak_price_ve_avg_ct=peak_result.peak_price_ve_avg_ct,
                charge_ceiling_active=self._charge_ceiling_active,
                charge_ceiling_max_soc=max_soc,
                balancing_mode=balancing_result.mode,
                surplus_70_active=surplus_70_active,
                surplus_ac_active=surplus_ac_active,
                surplus_veto_active=surplus_veto_active,
            )
        )
        self._settings()["akkusteuerung_modus"] = decision.mode

        if (
            soc > 99
            and current_price_ct is not None
            and bool(self._setting("hausakku_aus_netz_laden", False))
        ):
            self._settings()["hausakku_aus_netz_laden"] = False
            self._settings()["ladepreis"] = current_price_ct / 100.0

        return {
            "soc": soc,
            "battery_temp": battery_temp,
            "battery_capacity_kwh": capacity,
            "pv_power_w": pv_power,
            "pv_generation_w": pv_generation,
            "grid_export_w": grid_export,
            "grid_import_w": grid_import,
            "house_consumption_w": house_consumption,
            "house_consumption_60min_w": house_average_w,
            "house_consumption_60min_samples": self._house_mean_60m.count,
            "battery_load_30min_w": battery_average_30m_w,
            "battery_load_30min_samples": self._battery_mean_30m.count,
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
            "mindestentladepreis_differenz_ct": round(discharge_spread * 100.0, 2),
            "runtime_h": runtime,
            "pv_rich_day": self._pv_rich_day,
            "peak_reserve_valid": peak_result.valid,
            "peak_reserve_soc": peak_result.reserve_soc,
            "peak_reserve_ve_soc": peak_result.reserve_ve_soc,
            "peak_reserve_hours_ve": peak_result.peak_hours_ve,
            "peak_reserve_hours_exp": peak_result.peak_hours_exp,
            "peak_reserve_required_kwh": peak_result.required_kwh,
            "peak_reserve_min_price_before_peak_ct": peak_result.min_price_before_peak_ct,
            "peak_reserve_price_avg_ct": peak_result.peak_price_avg_ct,
            "peak_reserve_ve_price_avg_ct": peak_result.peak_price_ve_avg_ct,
            "peak_reserve_window_min_ct": peak_result.window_min_ct,
            "peak_reserve_horizon_end": peak_result.horizon_end.isoformat(),
            "peak_reserve_branch": peak_result.branch,
            "peak_reserve_active": peak_active,
            "charge_ceiling_active": self._charge_ceiling_active,
            "charge_ceiling_max_soc": max_soc,
            "winter_charging_allowed": True,
            "sun_above_horizon": sun_above_horizon,
            "surplus_70_active": surplus_70_active,
            "surplus_70_without_battery_w": round(surplus_70_w),
            "surplus_70_threshold_on_w": threshold_70,
            "surplus_70_threshold_off_w": threshold_70_off,
            "surplus_ac_active": surplus_ac_active,
            "surplus_ac_without_battery_w": round(surplus_ac_w),
            "surplus_ac_threshold_on_w": threshold_ac,
            "surplus_ac_threshold_off_w": threshold_ac_off,
            "surplus_veto_active": surplus_veto_active,
            "surplus_veto_without_battery_w": round(surplus_veto_w),
            "surplus_veto_threshold_on_w": veto_on,
            "surplus_veto_threshold_off_w": veto_off,
            "surplus_veto_scarcity_factor": scarcity_factor,
            "surplus_veto_scarcity_gate_open": scarcity_open,
            "balancing_watchdog": balancing_result.mode,
            "balancing_reason": balancing_result.reason,
            "balancing_due_reason": balancing_result.due_reason,
            "balancing_days_since_full": self._balancing_state.days_since_full,
            "balancing_done_minutes": self._balancing_state.done_minutes,
            "balancing_last_completion": self._balancing_state.last_completion,
            "balancing_completion_valid": self._balancing_state.completion_valid,
            "balancing_done_soc": done_soc,
            "strategy_mode": decision.mode,
            "strategy_reason": decision.reason,
            "strategy_core_valid": core_valid,
        }
