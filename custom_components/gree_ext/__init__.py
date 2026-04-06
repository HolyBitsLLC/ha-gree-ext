"""The Gree Climate Extended integration.

Drop-in replacement for the built-in ``gree`` integration, adding:
  - binary_sensor.gree_ext_compressor_active
  - binary_sensor.gree_ext_idle
  - sensor.gree_ext_indoor_coil_temp
  - sensor.gree_ext_outdoor_coil_temp
  - gree_ext.force_fan_off service

All communication is local UDP on port 7000.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import DISCOVERY_SCAN_INTERVAL
from .coordinator import (
    DiscoveryService,
    GreeExtConfigEntry,
    GreeExtRuntimeData,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GreeExtConfigEntry
) -> bool:
    """Set up Gree Climate Extended from a config entry."""
    gree_discovery = DiscoveryService(hass, entry)
    entry.runtime_data = GreeExtRuntimeData(
        discovery_service=gree_discovery, coordinators=[]
    )

    async def _async_scan_update(_=None):
        bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
        await gree_discovery.discovery.scan(0, bcast_ifaces=bcast_addr)

    _LOGGER.debug("Scanning network for Gree devices")
    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_scan_update,
            timedelta(seconds=DISCOVERY_SCAN_INTERVAL),
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom services (force_fan_off).
    await async_setup_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GreeExtConfigEntry
) -> bool:
    """Unload a config entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await async_unload_services(hass)
    return result
