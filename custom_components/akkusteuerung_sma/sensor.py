"""Canonical and derived Opti sensors migrated from the upstream project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMAAkkuCoordinator


@dataclass(frozen=True, kw_only=True)
class OptiSensorDescription(SensorEntityDescription):
    data_key: str
    attribute_keys: dict[str, str] | None = None
    none_is_unavailable: bool = False


SENSORS: tuple[OptiSensorDescription, ...] = (
    OptiSensorDescription(key="soc", name="Opti SoC", data_key="soc", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="battery_temp", name="Opti Battery Temp", data_key="battery_temp", native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="battery_capacity_kwh", name="Opti Battery Capacity kWh", data_key="battery_capacity_kwh", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="pv_power_w", name="Opti PV Power W", data_key="pv_power_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="pv_generation_w", name="Opti PV Generation W", data_key="pv_generation_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="grid_export_w", name="Opti Grid Export W", data_key="grid_export_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="grid_import_w", name="Opti Grid Import W", data_key="grid_import_w", native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="house_consumption_w", name="Opti House Consumption W", data_key="house_consumption_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="price_current_ct_kwh", name="Opti Price Current ct kWh", data_key="price_current_ct_kwh", native_unit_of_measurement="ct/kWh", state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="price_series", name="Opti Price Series", data_key="price_series_current_ct_kwh", native_unit_of_measurement="ct/kWh", state_class=SensorStateClass.MEASUREMENT, attribute_keys={"today": "price_series_today", "tomorrow": "price_series_tomorrow"}),
    OptiSensorDescription(key="forecast_today_kwh", name="Opti Forecast Today kWh", data_key="forecast_today_kwh", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"estimate10": "forecast_today_estimate10"}),
    OptiSensorDescription(key="forecast_tomorrow_kwh", name="Opti Forecast Tomorrow kWh", data_key="forecast_tomorrow_kwh", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"estimate10": "forecast_tomorrow_estimate10"}),
    OptiSensorDescription(key="forecast_remaining_today_kwh", name="Opti Forecast Remaining Today kWh", data_key="forecast_remaining_today_kwh", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"estimate10": "forecast_remaining_today_estimate10"}),
    OptiSensorDescription(key="battery_power_w", name="Opti Battery Power W", data_key="battery_power_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"simultaneous_charge_discharge": "simultaneous_charge_discharge"}),
    OptiSensorDescription(key="forecast_effective_remaining_kwh", name="Opti Forecast Effective Remaining kWh", data_key="forecast_effective_remaining_kwh", native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"median_kwh": "forecast_effective_median_kwh", "p10_kwh": "forecast_effective_p10_kwh", "alpha": "forecast_effective_alpha"}),
    OptiSensorDescription(key="forecast_score_tomorrow", name="Opti Forecast Score Tomorrow", data_key="forecast_score_tomorrow", state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="forecast_score", name="Opti Forecast Score", data_key="forecast_score", state_class=SensorStateClass.MEASUREMENT, attribute_keys={"remaining_kwh": "forecast_score_remaining_kwh", "needed_full_kwh": "forecast_score_needed_full_kwh", "hours_to_sunset": "forecast_score_hours_to_sunset", "pv_surplus_kwh": "forecast_score_pv_surplus_kwh", "ueberschuss_ueber_voll_kwh": "forecast_score_excess_over_full_kwh", "reason": "forecast_score_reason"}),
    OptiSensorDescription(key="target_soc", name="Opti Target SoC", data_key="target_soc", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, attribute_keys={"branch": "target_soc_branch", "level": "target_soc_level", "ratio": "target_soc_ratio", "net_available_kwh": "target_soc_net_available_kwh", "remaining_hours": "target_soc_remaining_hours"}),
    OptiSensorDescription(key="charge_power_w", name="Opti Charge Power W", data_key="charge_power_w", native_unit_of_measurement=UnitOfPower.WATT, state_class=SensorStateClass.MEASUREMENT),
    OptiSensorDescription(key="price_level", name="Opti Price Level", data_key="price_level", icon="mdi:cash-clock", none_is_unavailable=True, attribute_keys={"perzentil": "price_level_percentile", "aktueller_preis": "price_current_ct_kwh", "anzahl_preise": "price_level_count"}),
    OptiSensorDescription(key="mindestentladepreis_ct_kwh", name="Opti Mindestentladepreis ct kWh", data_key="mindestentladepreis_ct_kwh", native_unit_of_measurement="ct/kWh", attribute_keys={"ladepreis_ct": "mindestentladepreis_ladepreis_ct", "differenz_ct": "mindestentladepreis_differenz_ct"}),
    OptiSensorDescription(key="runtime_h", name="Opti Runtime H", data_key="runtime_h", native_unit_of_measurement=UnitOfTime.HOURS, state_class=SensorStateClass.MEASUREMENT, none_is_unavailable=True),
    OptiSensorDescription(key="peak_reserve_soc", name="Opti Peak Reserve SoC", data_key="peak_reserve_soc", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, icon="mdi:battery-lock", none_is_unavailable=True, attribute_keys={"reserve_ve_soc": "peak_reserve_ve_soc", "peak_stunden_ve": "peak_reserve_hours_ve", "peak_stunden_exp": "peak_reserve_hours_exp", "benoetigt_kwh": "peak_reserve_required_kwh", "min_preis_vor_peak_ct": "peak_reserve_min_price_before_peak_ct", "peak_preis_avg_ct": "peak_reserve_price_avg_ct", "peak_preis_ve_avg_ct": "peak_reserve_ve_price_avg_ct", "fenster_min_ct": "peak_reserve_window_min_ct", "horizont_ende": "peak_reserve_horizon_end", "branch": "peak_reserve_branch"}),
    OptiSensorDescription(
        key="balancing_watchdog",
        name="Opti Balancing Watchdog",
        data_key="balancing_watchdog",
        icon="mdi:battery-heart-variant",
        attribute_keys={
            "grund": "balancing_reason",
            "faellig_grund": "balancing_due_reason",
            "tage_seit_voll": "balancing_days_since_full",
            "bestaetigte_minuten": "balancing_done_minutes",
            "done_soc": "balancing_done_soc",
            "letzter_abschluss": "balancing_last_completion",
        },
    ),
    OptiSensorDescription(
        key="balancing_days_since_full",
        name="Opti Balancing Tage seit Abschluss",
        data_key="balancing_days_since_full",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-refresh",
    ),
    OptiSensorDescription(
        key="balancing_last_completion",
        name="Opti Balancing Letzter Abschluss",
        data_key="balancing_last_completion",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-check",
        none_is_unavailable=True,
        attribute_keys={
            "abschluss_gueltig": "balancing_completion_valid",
            "bestaetigte_minuten": "balancing_done_minutes",
        },
    ),
    OptiSensorDescription(
        key="strategie_vorschau",
        name="Opti Strategie Vorschau",
        data_key="strategy_mode",
        icon="mdi:state-machine",
        attribute_keys={
            "grund": "strategy_reason",
            "ist_modus": "strategy_mode",
            "soc": "soc",
            "ziel_soc": "target_soc",
            "score_heute": "forecast_score",
            "score_morgen": "forecast_score_tomorrow",
            "price_level": "price_level",
            "tag": "sun_above_horizon",
            "core_valid": "strategy_core_valid",
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SMAAkkuCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(OptiSensor(coordinator, entry, description) for description in SENSORS)


class OptiSensor(CoordinatorEntity[SMAAkkuCoordinator], SensorEntity):
    entity_description: OptiSensorDescription
    _attr_has_entity_name = False

    def __init__(self, coordinator: SMAAkkuCoordinator, entry: ConfigEntry, description: OptiSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.entity_description.key == "peak_reserve_soc":
            return bool(self.coordinator.data.get("peak_reserve_valid"))
        if self.entity_description.none_is_unavailable:
            return self.native_value is not None
        return True

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        mapping = self.entity_description.attribute_keys
        if not mapping or not self.coordinator.data:
            return None
        return {attribute: self.coordinator.data.get(data_key) for attribute, data_key in mapping.items()}
