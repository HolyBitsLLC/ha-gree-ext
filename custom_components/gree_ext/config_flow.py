"""Config flow for Gree Climate Extended integration.

Auto-discovery based — same zero-config UX as the upstream gree integration.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class GreeExtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gree Climate Extended."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step — auto-discovery, no user input needed."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Gree Climate Extended", data={}
            )

        return self.async_show_form(step_id="user")
