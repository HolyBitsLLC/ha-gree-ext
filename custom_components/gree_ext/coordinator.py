"""Coordinator and discovery helpers for Gree Climate Extended.

Extends the upstream greeclimate coordinator to request additional protocol
properties (compressor frequency, indoor/outdoor coil temperatures) that are
not part of the standard Props enum.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from greeclimate.device import Device, DeviceInfo, Props
from greeclimate.discovery import Discovery, Listener
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
from greeclimate.network import Response

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow

from .const import (
    DISCOVERY_TIMEOUT,
    DISPATCH_DEVICE_DISCOVERED,
    DOMAIN,
    EXTENDED_PROPERTIES,
    MAX_ERRORS,
    MAX_EXPECTED_RESPONSE_TIME_INTERVAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type GreeExtConfigEntry = ConfigEntry[GreeExtRuntimeData]


@dataclass
class GreeExtRuntimeData:
    """Runtime data for Gree Climate Extended integration."""

    discovery_service: DiscoveryService
    coordinators: list[DeviceDataUpdateCoordinator]


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages polling for state changes from the device.

    In addition to the standard greeclimate properties, this coordinator
    requests extended properties (compressor freq, coil temps) by issuing
    a separate status query for them after the normal update.
    """

    config_entry: GreeExtConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GreeExtConfigEntry,
        device: Device,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{device.device_info.name}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,
        )
        self.device = device
        self.device.add_handler(Response.RESULT, self.device_state_updated)

        self._error_count: int = 0
        self._last_response_time: datetime = utcnow()
        self._last_error_time: datetime | None = None

        # Extended properties stored separately so they don't collide with
        # greeclimate's internal _properties dict.
        self.extended_properties: dict[str, Any] = {}

    def device_state_updated(self, *args: Any) -> None:
        """Handle device state updates."""
        _LOGGER.debug("Device state updated: %s", json_dumps(args))
        self._error_count = 0
        self._last_response_time = utcnow()
        self.async_set_updated_data(self.device.raw_properties)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the state of the device."""
        _LOGGER.debug(
            "Updating device state: %s, error count: %d",
            self.name,
            self._error_count,
        )
        try:
            await self.device.update_state()
        except DeviceNotBoundError as error:
            raise UpdateFailed(
                f"Device {self.name} is unavailable, device is not bound."
            ) from error
        except DeviceTimeoutError as error:
            self._error_count += 1
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                _LOGGER.warning(
                    "Device %s is unavailable: %s",
                    self.name,
                    self.device.device_info,
                )
                raise UpdateFailed(
                    f"Device {self.name} is unavailable, could not send update request"
                ) from error
        else:
            now = utcnow()
            elapsed_success = now - self._last_response_time
            if self.update_interval and elapsed_success >= timedelta(
                seconds=MAX_EXPECTED_RESPONSE_TIME_INTERVAL
            ):
                if not self._last_error_time or (
                    (now - self.update_interval) >= self._last_error_time
                ):
                    self._last_error_time = now
                    self._error_count += 1

                _LOGGER.warning(
                    "Device %s took an unusually long time to respond, %s seconds",
                    self.name,
                    elapsed_success,
                )
            else:
                self._error_count = 0
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                raise UpdateFailed(
                    f"Device {self.name} is unresponsive for too long and now unavailable"
                )

        self._last_response_time = utcnow()

        # Fetch extended properties in a separate status request.
        await self._fetch_extended_properties()

        return copy.deepcopy(self.device.raw_properties)

    async def _fetch_extended_properties(self) -> None:
        """Request extended protocol properties from the device.

        Uses the same create_status_message / send mechanism as the standard
        update, but asks for our additional property names.  Results are
        captured via the RESULT handler and merged into extended_properties.
        """
        if not self.device.device_cipher:
            return

        try:
            # Build a status message requesting only the extended properties.
            msg = self.device.create_status_message(
                self.device.device_info, *EXTENDED_PROPERTIES
            )
            # We temporarily intercept the state-update handler to capture
            # the response for our custom properties.
            captured: dict[str, Any] = {}

            def _capture_extended(*args: Any) -> None:
                if args and isinstance(args[0], dict):
                    captured.update(args[0])

            self.device.add_handler(Response.DATA, _capture_extended)
            try:
                await self.device.send(msg)
                # Give the device a brief moment to respond. The result
                # handler fires synchronously within datagram_received.
                import asyncio

                await asyncio.sleep(0.5)
            finally:
                self.device.remove_handler(Response.DATA, _capture_extended)

            if captured:
                self.extended_properties.update(captured)
                _LOGGER.debug(
                    "Extended properties for %s: %s",
                    self.name,
                    self.extended_properties,
                )
        except (DeviceTimeoutError, DeviceNotBoundError):
            _LOGGER.debug(
                "Could not fetch extended properties for %s (timeout/not bound)",
                self.name,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "Unexpected error fetching extended properties for %s",
                self.name,
                exc_info=True,
            )

    async def push_state_update(self) -> None:
        """Send state updates to the physical device."""
        try:
            return await self.device.push_state_update()
        except DeviceTimeoutError:
            _LOGGER.warning(
                "Timeout send state update to: %s (%s)",
                self.name,
                self.device.device_info,
            )


class DiscoveryService(Listener):
    """Discovery event handler for gree devices."""

    def __init__(
        self, hass: HomeAssistant, entry: GreeExtConfigEntry
    ) -> None:
        """Initialize discovery service."""
        super().__init__()
        self.hass = hass
        self.entry = entry
        self.discovery = Discovery(DISCOVERY_TIMEOUT)
        self.discovery.add_listener(self)

    async def device_found(self, device_info: DeviceInfo) -> None:
        """Handle new device found on the network."""
        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError:
            _LOGGER.error("Unable to bind to gree device: %s", device_info)
            return
        except DeviceTimeoutError:
            _LOGGER.error(
                "Timeout trying to bind to gree device: %s", device_info
            )
            return

        _LOGGER.debug(
            "Adding Gree device %s at %s:%i",
            device.device_info.name,
            device.device_info.ip,
            device.device_info.port,
        )
        coordo = DeviceDataUpdateCoordinator(self.hass, self.entry, device)
        self.entry.runtime_data.coordinators.append(coordo)
        await coordo.async_refresh()

        async_dispatcher_send(
            self.hass, DISPATCH_DEVICE_DISCOVERED, coordo
        )

    async def device_update(self, device_info: DeviceInfo) -> None:
        """Handle updates in device information, update if ip has changed."""
        for coordinator in self.entry.runtime_data.coordinators:
            if coordinator.device.device_info.mac == device_info.mac:
                coordinator.device.device_info.ip = device_info.ip
                await coordinator.async_refresh()
