"""Service implementations for Gree Climate Extended."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_FORCE_FAN_OFF
from .coordinator import GreeExtRuntimeData

_LOGGER = logging.getLogger(__name__)

SERVICE_FORCE_FAN_OFF_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_ids,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom services for Gree Climate Extended."""

    async def handle_force_fan_off(call: ServiceCall) -> None:
        """Handle the force_fan_off service call.

        Turns off the HVAC unit entirely to kill the fan.  This is the safest
        approach that works across all Gree/Tosot model variants — sending
        Pow=0 stops the fan and compressor immediately.

        Called by automations when the compressor has stopped (idle sensor is
        True) but the fan is still running.  The automation can optionally
        re-enable the unit afterwards in the desired mode.
        """
        target_entity_ids: list[str] | None = call.data.get("entity_id")

        # Walk all config entries for our domain.
        for entry_id, entry in hass.config_entries.async_entries(DOMAIN):
            pass  # not needed — we iterate runtime_data below

        for entry in hass.config_entries.async_entries(DOMAIN):
            runtime_data: GreeExtRuntimeData | None = getattr(
                entry, "runtime_data", None
            )
            if runtime_data is None:
                continue

            for coordinator in runtime_data.coordinators:
                mac = coordinator.device.device_info.mac
                # If entity_ids were specified, check whether this device's
                # climate entity matches.
                if target_entity_ids:
                    climate_entity_id = f"climate.{DOMAIN}_{mac}"
                    # Also accept the entity_id format HA actually assigns.
                    matches = any(
                        eid == climate_entity_id
                        or eid.endswith(mac)
                        or eid.endswith(mac.replace(":", ""))
                        for eid in target_entity_ids
                    )
                    if not matches:
                        continue

                _LOGGER.info(
                    "force_fan_off: Sending power-off to %s (%s)",
                    coordinator.device.device_info.name,
                    mac,
                )
                coordinator.device.power = False
                await coordinator.push_state_update()
                coordinator.async_set_updated_data(
                    coordinator.device.raw_properties
                )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_FAN_OFF,
        handle_force_fan_off,
        schema=SERVICE_FORCE_FAN_OFF_SCHEMA,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services when the last config entry is removed."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_FORCE_FAN_OFF)
