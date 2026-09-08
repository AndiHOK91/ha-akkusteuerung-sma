"""Config flow for SMA Akku Steuerung."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_HOST,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_INVERTER_LIMIT_ENTITY,
    CONF_INVERTER_STATUS_ENTITY,
    CONF_INVERTER_TEMPERATURE_ENTITY,
    CONF_MODBUS_ID,
    CONF_PORT,
    CONF_PV_POWER_ENTITY,
    DEFAULT_MODBUS_ID,
    DEFAULT_PORT,
    DOMAIN,
)


class SMAAkkuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input:
            return self.async_create_entry(
                title="SMA Akku Steuerung",
                data=user_input,
            )

        power_sensor = selector.EntitySelectorConfig(
            domain="sensor",
            device_class="power",
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_MODBUS_ID, default=DEFAULT_MODBUS_ID): int,
                    vol.Required(CONF_BATTERY_CAPACITY_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_BATTERY_SOC_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_BATTERY_POWER_ENTITY): selector.EntitySelector(power_sensor),
                    vol.Required(CONF_PV_POWER_ENTITY): selector.EntitySelector(power_sensor),
                    vol.Required(CONF_GRID_POWER_ENTITY): selector.EntitySelector(power_sensor),
                    vol.Required(CONF_HOUSE_CONSUMPTION_ENTITY): selector.EntitySelector(power_sensor),
                    vol.Required(CONF_INVERTER_LIMIT_ENTITY): selector.EntitySelector(power_sensor),
                    vol.Required(CONF_INVERTER_STATUS_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_INVERTER_TEMPERATURE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )
