"""Data coordinator for SMA Akku Steuerung."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class SMAAkkuCoordinator(DataUpdateCoordinator):
    """Coordinate SMA battery data updates."""

    def __init__(self, hass, api):
        super().__init__(
            hass,
            logger=None,
            name="SMA Akku Steuerung",
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        return await self.api.async_read_data()
