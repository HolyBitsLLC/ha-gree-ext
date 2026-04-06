"""Diagnostics support for Gree Climate Extended."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import GreeExtConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GreeExtConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {"devices": []}

    for coordinator in entry.runtime_data.coordinators:
        dev = coordinator.device
        device_diag: dict[str, Any] = {
            "name": dev.device_info.name,
            "mac": dev.device_info.mac,
            "ip": dev.device_info.ip,
            "port": dev.device_info.port,
            "firmware_version": dev.version,
            "hid": dev.hid,
            "power": dev.power,
            "mode": dev.mode,
            "target_temperature": dev.target_temperature,
            "current_temperature": dev.current_temperature,
            "fan_speed": dev.fan_speed,
            "standard_properties": dict(dev.raw_properties),
            "extended_properties": dict(coordinator.extended_properties),
        }
        diag["devices"].append(device_diag)

    return diag
