"""Binary decision sensors migrated from upstream opti_derived.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SMAAkkuCoordinator


@dataclass(frozen=True, kw_only=True)
class OptiBinaryDescription(BinarySensorEntityDescription):
    data_key: str
    attribute_keys: dict[str, str] | None = None


BINARY_SENSORS: tuple[OptiBinaryDescription, ...] = (
    OptiBinaryDescription(
        key="winter_charging_allowed",
        name="Opti Winter Charging Allowed",
        data_key="winter_charging_allowed",
    ),
    OptiBinaryDescription(
        key="pv_rich_day",
        name="Opti PV Reichtag",
        data_key="pv_rich_day",
        icon="mdi:weather-sunny",
    ),
    OptiBinaryDescription(
        key="peak_reserve_active",
        name="Opti Peak Reserve Aktiv",
        data_key="peak_reserve_active",
        icon="mdi:shield-lock",
    ),
    OptiBinaryDescription(
        key="charge_ceiling_active",
        name="Opti Ladedeckel Aktiv",
        data_key="charge_ceiling_active",
        icon="mdi:battery-lock",
        attribute_keys={"maxsoc": "charge_ceiling_max_soc"},
    ),
    OptiBinaryDescription(
        key="surplus_70_active",
        name="Opti Ueberschuss 70 Aktiv",
        data_key="surplus_70_active",
        icon="mdi:transmission-tower-export",
        attribute_keys={
            "export_ohne_akku_w": "surplus_70_without_battery_w",
            "grenze_ein_w": "surplus_70_threshold_on_w",
            "grenze_aus_w": "surplus_70_threshold_off_w",
        },
    ),
    OptiBinaryDescription(
        key="surplus_ac_active",
        name="Opti Ueberschuss AC Aktiv",
        data_key="surplus_ac_active",
        icon="mdi:sine-wave",
        attribute_keys={
            "ac_ohne_akku_w": "surplus_ac_without_battery_w",
            "grenze_ein_w": "surplus_ac_threshold_on_w",
            "grenze_aus_w": "surplus_ac_threshold_off_w",
        },
    ),
    OptiBinaryDescription(
        key="surplus_veto_active",
        name="Opti Ueberschuss Veto Aktiv",
        data_key="surplus_veto_active",
        icon="mdi:battery-plus-variant",
        attribute_keys={
            "export_ohne_akku_w": "surplus_veto_without_battery_w",
            "grenze_ein_w": "surplus_veto_threshold_on_w",
            "grenze_aus_w": "surplus_veto_threshold_off_w",
            "knappheit_faktor": "surplus_veto_scarcity_factor",
            "knappheit_gate_offen": "surplus_veto_scarcity_gate_open",
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SMAAkkuCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        OptiBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class OptiBinarySensor(CoordinatorEntity[SMAAkkuCoordinator], BinarySensorEntity):
    entity_description: OptiBinaryDescription
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: SMAAkkuCoordinator,
        entry: ConfigEntry,
        description: OptiBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        return bool(self.coordinator.data.get(self.entity_description.data_key))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        mapping = self.entity_description.attribute_keys
        if not mapping or not self.coordinator.data:
            return None
        return {
            attribute: self.coordinator.data.get(data_key)
            for attribute, data_key in mapping.items()
        }
