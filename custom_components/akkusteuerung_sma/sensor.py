"""Sensors for SMA Akku Steuerung."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMAAkkuCoordinator


@dataclass(frozen=True, kw_only=True)
class OptiSensorDescription(SensorEntityDescription):
    """Describe an Opti sensor."""

    data_key: str


SENSORS: tuple[OptiSensorDescription, ...] = (
    OptiSensorDescription(
        key="target_soc",
        name="Ziel SOC",
        data_key="target_soc",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-sync",
    ),
    OptiSensorDescription(
        key="pv_surplus",
        name="PV Überschuss",
        data_key="pv_surplus",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
    ),
    OptiSensorDescription(
        key="mode",
        name="Strategie Modus",
        data_key="mode",
        icon="mdi:state-machine",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create Opti sensors for a config entry."""
    coordinator: SMAAkkuCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        OptiSensor(coordinator, entry, description) for description in SENSORS
    )


class OptiSensor(CoordinatorEntity[SMAAkkuCoordinator], SensorEntity):
    """Representation of a calculated Opti value."""

    entity_description: OptiSensorDescription

    def __init__(
        self,
        coordinator: SMAAkkuCoordinator,
        entry: ConfigEntry,
        description: OptiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def native_value(self):
        """Return the latest coordinator value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)
