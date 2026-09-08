"""Select helpers migrated from packages/sma_helpers.yaml."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity


OPTIONS = [
    "Akku Automatisch",
    "Akku schnell Laden",
    "Akku schnell Entladen",
    "Akku Pause",
    "Akku nur Laden",
    "Akku Netzladen",
    "Akku nur Entladen",
    "Akku Dynamisch",
    "Akku 0.2C Laden",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the migrated battery mode selector."""
    async_add_entities([OptiModeSelect(entry)])


class OptiModeSelect(SelectEntity, RestoreEntity):
    """Persistent selector matching input_select.akkusteuerung_modus."""

    _attr_name = "Akkusteuerung Modus"
    _attr_options = OPTIONS
    _attr_icon = "mdi:battery-charging"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_akkusteuerung_modus"
        self._attr_current_option = OPTIONS[0]

    async def async_added_to_hass(self) -> None:
        """Restore the last selected mode after restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if (
            last_state is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_state.state in self.options
        ):
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Select the battery operating mode."""
        self._attr_current_option = option
        self.async_write_ha_state()
