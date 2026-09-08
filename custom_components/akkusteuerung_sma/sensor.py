"""Canonical Opti sensors migrated from opti_mapping.example.yaml."""

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
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMAAkkuCoordinator


@dataclass(frozen=True, kw_only=True)
class OptiSensorDescription(SensorEntityDescription):
    """Describe one canonical Opti sensor."""

    data_key: str
    attribute_keys: dict[str, str] | None = None


SENSORS: tuple[OptiSensorDescription, ...] = (
    OptiSensorDescription(
        key="soc",
        name="Opti SoC",
        data_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="battery_temp",
        name="Opti Battery Temp",
        data_key="battery_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="battery_capacity_kwh",
        name="Opti Battery Capacity kWh",
        data_key="battery_capacity_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="pv_power_w",
        name="Opti PV Power W",
        data_key="pv_power_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="pv_generation_w",
        name="Opti PV Generation W",
        data_key="pv_generation_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="grid_export_w",
        name="Opti Grid Export W",
        data_key="grid_export_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="grid_import_w",
        name="Opti Grid Import W",
        data_key="grid_import_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="house_consumption_w",
        name="Opti House Consumption W",
        data_key="house_consumption_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="price_current_ct_kwh",
        name="Opti Price Current ct kWh",
        data_key="price_current_ct_kwh",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OptiSensorDescription(
        key="price_series",
        name="Opti Price Series",
        data_key="price_series_current_ct_kwh",
        native_unit_of_measurement="ct/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        attribute_keys={
            "today": "price_series_today",
            "tomorrow": "price_series_tomorrow",
        },
    ),
    OptiSensorDescription(
        key="forecast_today_kwh",
        name="Opti Forecast Today kWh",
        data_key="forecast_today_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_keys={"estimate10": "forecast_today_estimate10"},
    ),
    OptiSensorDescription(
        key="forecast_tomorrow_kwh",
        name="Opti Forecast Tomorrow kWh",
        data_key="forecast_tomorrow_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_keys={"estimate10": "forecast_tomorrow_estimate10"},
    ),
    OptiSensorDescription(
        key="forecast_remaining_today_kwh",
        name="Opti Forecast Remaining Today kWh",
        data_key="forecast_remaining_today_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_keys={"estimate10": "forecast_remaining_today_estimate10"},
    ),
    OptiSensorDescription(
        key="battery_power_w",
        name="Opti Battery Power W",
        data_key="battery_power_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        attribute_keys={
            "simultaneous_charge_discharge": "simultaneous_charge_discharge"
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the original canonical Opti sensor layer."""
    coordinator: SMAAkkuCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        OptiSensor(coordinator, entry, description) for description in SENSORS
    )


class OptiSensor(CoordinatorEntity[SMAAkkuCoordinator], SensorEntity):
    """Representation of one canonical Opti sensor."""

    entity_description: OptiSensorDescription
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: SMAAkkuCoordinator,
        entry: ConfigEntry,
        description: OptiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the latest canonical value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose attributes required by the original downstream logic."""
        mapping = self.entity_description.attribute_keys
        if not mapping or not self.coordinator.data:
            return None
        return {
            attribute: self.coordinator.data.get(data_key)
            for attribute, data_key in mapping.items()
        }
