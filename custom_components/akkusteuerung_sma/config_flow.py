"""Config flow for SMA Akku Steuerung."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CAPACITY_UNIT_KWH,
    CAPACITY_UNIT_WH,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_UNIT,
    CONF_BATTERY_CHARGE_POWER_ENTITY,
    CONF_BATTERY_DISCHARGE_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_TEMP_ENTITY,
    CONF_BYD_CELL_SPREAD_ENTITY,
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
    PRICE_UNIT_CT_KWH,
    PRICE_UNIT_EUR_KWH,
)


def _sensor_selector() -> selector.EntitySelector:
    """Return a generic sensor entity selector."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))


def _power_selector() -> selector.EntitySelector:
    """Return a power sensor selector."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="power")
    )


class SMAAkkuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the original Opti canonical mapping through the UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._config_data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None):
        """Select the energy and battery source entities."""
        if user_input is not None:
            self._config_data.update(user_input)
            return await self.async_step_market()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_SOC_ENTITY): _sensor_selector(),
                    vol.Optional(CONF_BATTERY_TEMP_ENTITY): _sensor_selector(),
                    vol.Required(CONF_BATTERY_CAPACITY_ENTITY): _sensor_selector(),
                    vol.Required(
                        CONF_BATTERY_CAPACITY_UNIT,
                        default=CAPACITY_UNIT_WH,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[CAPACITY_UNIT_WH, CAPACITY_UNIT_KWH]
                        )
                    ),
                    vol.Required(CONF_PV_POWER_ENTITY): _power_selector(),
                    vol.Required(CONF_PV_GENERATION_ENTITY): _power_selector(),
                    vol.Required(CONF_GRID_EXPORT_ENTITY): _power_selector(),
                    vol.Required(CONF_GRID_IMPORT_ENTITY): _power_selector(),
                    vol.Required(CONF_HOUSE_CONSUMPTION_ENTITY): _power_selector(),
                    vol.Required(CONF_BATTERY_CHARGE_POWER_ENTITY): _power_selector(),
                    vol.Required(CONF_BATTERY_DISCHARGE_POWER_ENTITY): _power_selector(),
                    vol.Optional(CONF_BYD_CELL_SPREAD_ENTITY): _sensor_selector(),
                }
            ),
        )

    async def async_step_market(self, user_input=None):
        """Select price and Solcast source entities."""
        if user_input is not None:
            self._config_data.update(user_input)
            await self.async_set_unique_id("default")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="SMA Akku Steuerung",
                data=self._config_data,
            )

        return self.async_show_form(
            step_id="market",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_CURRENT_ENTITY): _sensor_selector(),
                    vol.Required(CONF_PRICE_SERIES_ENTITY): _sensor_selector(),
                    vol.Required(
                        CONF_PRICE_UNIT,
                        default=PRICE_UNIT_EUR_KWH,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[PRICE_UNIT_EUR_KWH, PRICE_UNIT_CT_KWH]
                        )
                    ),
                    vol.Required(CONF_FORECAST_TODAY_ENTITY): _sensor_selector(),
                    vol.Required(CONF_FORECAST_TOMORROW_ENTITY): _sensor_selector(),
                    vol.Required(CONF_FORECAST_REMAINING_ENTITY): _sensor_selector(),
                }
            ),
        )
