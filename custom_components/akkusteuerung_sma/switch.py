"""Switch helpers migrated from packages/sma_helpers.yaml."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


@dataclass(frozen=True, slots=True)
class OptiSwitchDefinition:
    """Definition of one migrated input_boolean helper."""

    key: str
    name: str
    icon: str


SWITCHES: tuple[OptiSwitchDefinition, ...] = (
    OptiSwitchDefinition("akku_opti_automatik", "Akku Opti-Automatik", "mdi:battery-sync"),
    OptiSwitchDefinition("hausakku_aus_netz_laden", "Hausakku aus Netz laden", "mdi:transmission-tower"),
    OptiSwitchDefinition("hausakku_wurde_netzgeladen", "Hausakku wurde netzgeladen (Flag)", "mdi:battery-check"),
    OptiSwitchDefinition("akku_nach_preis_laden", "Akku nach Preis laden", "mdi:currency-eur"),
    OptiSwitchDefinition("speicher_eco_netzladen", "Speicher Eco Netzladen", "mdi:leaf"),
    OptiSwitchDefinition("opti_prognose_netzladen", "Opti Reserve-halten bei schlechter Prognose", "mdi:transmission-tower"),
    OptiSwitchDefinition("opti_pv_ueberschuss_ladung", "Opti PV-Überschussladung erlauben", "mdi:solar-power"),
    OptiSwitchDefinition("opti_balancing_netzladen", "Opti Balancing darf ans Netz", "mdi:battery-heart-variant"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create migrated Opti boolean helpers."""
    async_add_entities(OptiSwitch(entry, definition) for definition in SWITCHES)


class OptiSwitch(SwitchEntity, RestoreEntity):
    """Persistent switch matching the original input_boolean semantics."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, definition: OptiSwitchDefinition) -> None:
        self._entry_id = entry.entry_id
        self._definition = definition
        self._attr_name = definition.name
        self._attr_unique_id = f"{entry.entry_id}_{definition.key}"
        self._attr_icon = definition.icon
        self._attr_is_on = False

    def _sync_runtime(self) -> None:
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if runtime is not None:
            runtime.setdefault("settings", {})[self._definition.key] = bool(self._attr_is_on)

    async def async_added_to_hass(self) -> None:
        """Restore the previous boolean state after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in (STATE_ON, STATE_OFF):
            self._attr_is_on = last_state.state == STATE_ON
        self._sync_runtime()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the helper on."""
        self._attr_is_on = True
        self._sync_runtime()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the helper off."""
        self._attr_is_on = False
        self._sync_runtime()
        self.async_write_ha_state()
