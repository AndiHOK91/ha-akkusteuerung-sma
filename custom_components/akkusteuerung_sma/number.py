"""Number helpers migrated from packages/sma_helpers.yaml."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


@dataclass(frozen=True, slots=True)
class OptiNumberDefinition:
    """Definition of one migrated input_number helper."""

    key: str
    name: str
    minimum: float
    maximum: float
    step: float
    unit: str | None = None
    mode: NumberMode = NumberMode.BOX
    icon: str | None = None
    initial: float | None = None


NUMBERS: tuple[OptiNumberDefinition, ...] = (
    OptiNumberDefinition("akkusteuerung_ladestaerke_soll", "Akkusteuerung Ladestärke Soll", 100, 10000, 100, "W", icon="mdi:battery-arrow-up"),
    OptiNumberDefinition("akkusteuerung_min_ladestaerke", "Akkusteuerung Min Ladestärke", 0, 2000, 50, "W"),
    OptiNumberDefinition("akkusteuerung_max_ladestaerke", "Akkusteuerung Max Ladestärke", 0, 10000, 1, "W"),
    OptiNumberDefinition("akkusteuerung_entladestaerke_soll", "Akkusteuerung Entladestärke Soll", 100, 10000, 100, "W", icon="mdi:battery-arrow-down"),
    OptiNumberDefinition("akkusteuerung_min_entladestaerke", "Akkusteuerung Min Entladestärke", 0, 2000, 50, "W"),
    OptiNumberDefinition("akkusteuerung_max_entladestaerke", "Akkusteuerung Max Entladestärke", 0, 10000, 1, "W"),
    OptiNumberDefinition("akkusteuerung_wr_ac_ueberschuss_grenze", "Akkusteuerung AC-Überschuss Grenze", 0, 15000, 100, "W", icon="mdi:transmission-tower-export"),
    OptiNumberDefinition("akkusteuerung_wr_70proz_ueberschuss_grenze", "Akkusteuerung 70%-Überschuss Grenze", 0, 25000, 100, "W"),
    OptiNumberDefinition("akkusteuerung_ueberschuss_veto_grenze", "Akkusteuerung Überschuss-Veto Grenze", 200, 5000, 50, "W", icon="mdi:transmission-tower-export"),
    OptiNumberDefinition("akkusteuerung_ueberschuss_veto_aus_grenze", "Akkusteuerung Überschuss-Veto Aus-Grenze", 100, 5000, 50, "W", icon="mdi:transmission-tower-export"),
    OptiNumberDefinition("akkusteuerung_ueberschuss_veto_knappheit_faktor", "Akkusteuerung Überschuss-Veto Knappheits-Faktor", 1, 10, 0.5, icon="mdi:scale-balance"),
    OptiNumberDefinition("minsoc", "Akku Min SoC", 0, 100, 1, "%", NumberMode.SLIDER, "mdi:battery-low"),
    OptiNumberDefinition("maxsoc", "Akku Max SoC", 0, 100, 1, "%", NumberMode.SLIDER, "mdi:battery-high"),
    OptiNumberDefinition("ladepreis", "Akku Ladepreis (Referenz)", -1, 1, 0.001, "EUR/kWh", icon="mdi:currency-eur"),
    OptiNumberDefinition("mindestpreisdifferenz_lade_entladepreis", "Mindestpreisdifferenz Laden/Entladen", 0, 0.3, 0.005, "EUR/kWh", icon="mdi:cash-plus"),
    OptiNumberDefinition("opti_peak_verbrauch_kw", "Opti Peak-Verbrauch", 0.1, 5, 0.1, "kW", icon="mdi:home-lightning-bolt"),
    OptiNumberDefinition("opti_einspeiseverguetung_ct", "Opti Einspeiseverguetung", 0, 30, 0.1, "ct/kWh", icon="mdi:solar-power-variant"),
    OptiNumberDefinition("opti_netzlade_spread_ct", "Opti Netzlade-Spread", 0, 100, 0.5, "ct/kWh", icon="mdi:swap-vertical-bold"),
    OptiNumberDefinition("opti_peak_min_aufschlag_ct", "Opti Peak Mindestaufschlag", 0, 100, 0.5, "ct/kWh", icon="mdi:filter-outline"),
    OptiNumberDefinition("opti_forecast_optimismus", "Opti Forecast-Optimismus", 0, 100, 5, "%", NumberMode.SLIDER, "mdi:weather-sunny"),
    OptiNumberDefinition("opti_halte_spread_ct", "Opti Halte-Spread", 0, 50, 0.5, "ct/kWh", icon="mdi:hand-back-right-outline"),
    OptiNumberDefinition("opti_balancing_intervall_tage", "Opti Balancing Intervall", 0, 60, 1, "Tage", icon="mdi:calendar-refresh"),
    OptiNumberDefinition("opti_balancing_karenz_tage", "Opti Balancing Karenz", 0, 14, 1, "Tage", icon="mdi:timer-sand"),
    OptiNumberDefinition("opti_balancing_max_ct", "Opti Balancing Preisdeckel", 0, 50, 0.5, "ct/kWh", icon="mdi:cash-lock"),
    OptiNumberDefinition("opti_balancing_done_soc", "Opti Balancing Done-SoC", 90, 100, 0.5, "%", icon="mdi:battery-heart-variant", initial=98.5),
    OptiNumberDefinition("opti_balancing_spreizungs_schwelle", "Opti Balancing Spreizungs-Schwelle", 0, 49, 1, "mV", icon="mdi:arrow-collapse-vertical"),
    OptiNumberDefinition("opti_balancing_bedarf_cooldown_tage", "Opti Balancing Bedarf-Cooldown Tage", 0, 30, 1, "Tage", icon="mdi:timer-sand"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create migrated Opti number helpers."""
    async_add_entities(OptiNumber(entry, definition) for definition in NUMBERS)


class OptiNumber(RestoreNumber):
    """Persistent number helper matching the original input_number semantics."""

    def __init__(self, entry: ConfigEntry, definition: OptiNumberDefinition) -> None:
        self._entry_id = entry.entry_id
        self._definition = definition
        self._attr_name = definition.name
        self._attr_unique_id = f"{entry.entry_id}_{definition.key}"
        self._attr_native_min_value = definition.minimum
        self._attr_native_max_value = definition.maximum
        self._attr_native_step = definition.step
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_mode = definition.mode
        self._attr_icon = definition.icon
        self._attr_native_value = (
            definition.initial if definition.initial is not None else definition.minimum
        )
        self._attr_has_entity_name = True

    def _sync_runtime(self) -> None:
        """Expose the helper value to the in-process strategy engine."""
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        if runtime is not None:
            runtime.setdefault("settings", {})[self._definition.key] = self._attr_native_value

    async def async_added_to_hass(self) -> None:
        """Restore the previous value where the original helper had no initial:."""
        await super().async_added_to_hass()
        if self._definition.initial is None:
            last_state = await self.async_get_last_state()
            last_number_data = await self.async_get_last_number_data()
            if (
                last_state is not None
                and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                and last_number_data is not None
                and last_number_data.native_value is not None
            ):
                self._attr_native_value = last_number_data.native_value
        self._sync_runtime()

    async def async_set_native_value(self, value: float) -> None:
        """Set the helper value."""
        self._attr_native_value = value
        self._sync_runtime()
        self.async_write_ha_state()
