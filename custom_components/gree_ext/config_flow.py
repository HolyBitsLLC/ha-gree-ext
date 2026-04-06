"""Config flow for Gree Climate Extended integration.

Supports both auto-discovery via UDP broadcast and manual IP entry for
devices on different VLANs or behind firewalls that block broadcast.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from greeclimate.device import Device, DeviceInfo
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_IP_ADDRESSES = "ip_addresses"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_IP_ADDRESSES, default=""): str,
    }
)


async def _try_bind(ip: str, port: int = 7000, timeout: int = 10) -> DeviceInfo | None:
    """Attempt to scan/bind a Gree device at the given IP.

    Returns DeviceInfo on success, None on failure.
    """
    from greeclimate.discovery import Discovery

    found: list[DeviceInfo] = []

    class _Collector:
        async def device_found(self, device_info: DeviceInfo) -> None:
            found.append(device_info)

        async def device_update(self, device_info: DeviceInfo) -> None:
            pass

    disc = Discovery(timeout)
    collector = _Collector()
    disc.add_listener(collector)

    try:
        await disc.scan(0, bcast_ifaces=[ip])
        # Give the device a moment to respond
        await asyncio.sleep(3)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Scan failed for %s", ip, exc_info=True)

    if found:
        return found[0]

    # Fallback: try direct bind with a synthetic DeviceInfo
    _LOGGER.debug("Broadcast scan got no response from %s, trying direct bind", ip)
    info = DeviceInfo(ip, port, "unknown", "unknown")
    device = Device(info, timeout=timeout, bind_timeout=5)
    try:
        await device.bind()
        return device.device_info
    except (DeviceNotBoundError, DeviceTimeoutError, OSError):
        _LOGGER.debug("Direct bind also failed for %s", ip)
    finally:
        device.close()

    return None


class GreeExtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gree Climate Extended."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> GreeExtOptionsFlow:
        """Return the options flow handler."""
        return GreeExtOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — optional manual IP entry.

        Users can enter one or more IP addresses (comma-separated) for
        devices that can't be discovered via UDP broadcast.  Leave blank
        to rely purely on auto-discovery.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_ips = user_input.get(CONF_IP_ADDRESSES, "").strip()
            ip_list: list[str] = []

            if raw_ips:
                for ip in raw_ips.split(","):
                    ip = ip.strip()
                    if not ip:
                        continue
                    # Validate the IP is reachable by attempting a bind
                    info = await _try_bind(ip)
                    if info is None:
                        errors["base"] = "cannot_connect"
                        _LOGGER.warning(
                            "Could not reach Gree device at %s", ip
                        )
                        break
                    ip_list.append(ip)
                    _LOGGER.info(
                        "Validated Gree device at %s: %s", ip, info.name
                    )

            if not errors:
                return self.async_create_entry(
                    title="Gree Climate Extended",
                    data={CONF_IP_ADDRESSES: ip_list},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class GreeExtOptionsFlow(OptionsFlow):
    """Options flow to add/remove device IPs after initial setup."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_ips = user_input.get(CONF_IP_ADDRESSES, "").strip()
            ip_list: list[str] = []

            if raw_ips:
                for ip in raw_ips.split(","):
                    ip = ip.strip()
                    if not ip:
                        continue
                    info = await _try_bind(ip)
                    if info is None:
                        errors["base"] = "cannot_connect"
                        break
                    ip_list.append(ip)

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_IP_ADDRESSES: ip_list},
                )
                return self.async_create_entry(title="", data={})

        current_ips = self.config_entry.data.get(CONF_IP_ADDRESSES, [])
        default = ", ".join(current_ips) if current_ips else ""

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_IP_ADDRESSES, default=default): str,
                }
            ),
            errors=errors,
        )
