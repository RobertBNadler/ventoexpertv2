"""Config flow for VentoExpertV2 integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
)

DEFAULT_PORT = 4000
DEFAULT_DEVICE_ID = "DEFAULT_DEVICEID"
DEFAULT_PASSWORD = "1111"
DEFAULT_UPDATE_INTERVAL = 10


class VentoExpertConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VentoExpertV2."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title="VentoExpertV2", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
