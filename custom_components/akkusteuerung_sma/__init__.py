"""SMA Akku Steuerung Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SMAAkkuCoordinator
from .storage import BalancingStorage

PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    storage = BalancingStorage(hass, entry.entry_id)
    balancing_state = await storage.async_load()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "settings": {},
        "balancing_storage": storage,
        "balancing_state": balancing_state,
    }

    coordinator = SMAAkkuCoordinator(
        hass,
        entry,
        balancing_state=balancing_state,
        balancing_storage=storage,
    )
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator
    await coordinator.async_config_entry_first_refresh()

    # Helper platforms restore their persistent states and mirror them into the
    # runtime settings store. Refresh once afterwards so calculations use those
    # restored values immediately.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_request_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)
