"""Config flow for SMA Akku Steuerung."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_HOST,
    CONF_MODBUS_ID,
    CONF_PORT,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MODBUS_ID,
    DEFAULT_PORT,
    DOMAIN,
)


class SMAAkkuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle user setup."""
        if user_input:
            return self.async_create_entry(
                title="SMA Akku Steuerung",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_MODBUS_ID, default=DEFAULT_MODBUS_ID): int,
                    vol.Optional(
                        CONF_BATTERY_CAPACITY,
                        default=DEFAULT_BATTERY_CAPACITY,
                    ): vol.Coerce(float),
                }
            ),
        )
