"""Coordinator and discovery helpers for Gree Climate Extended.

Extends the upstream greeclimate coordinator to request additional protocol
properties (compressor frequency, indoor/outdoor coil temperatures) that are
not part of the standard Props enum.
"""

from __future__ import annotations

import asyncio
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
    FW_V4_VERSION_PREFIX,
    MAX_ERRORS,
    MAX_EXPECTED_RESPONSE_TIME_INTERVAL,
    PROP_COMP_FREQ,
    PROP_COMP_FREQ_ALIASES,
    PROP_INDOOR_COIL_ALIASES,
    PROP_INDOOR_COIL_TEMP,
    PROP_OUTDOOR_COIL_ALIASES,
    PROP_OUTDOOR_COIL_TEMP,
    TEMP_OFFSET,
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
        self.device.add_handler(Response.DATA, self._on_device_response)
        self.device.add_handler(Response.RESULT, self._on_device_response)

        self._error_count: int = 0
        self._last_response_time: datetime = utcnow()
        self._last_error_time: datetime | None = None

        # Signalled when the device responds to a status request.
        self._response_received: asyncio.Event = asyncio.Event()

        # Extended properties stored separately so they don't collide with
        # greeclimate's internal _properties dict.
        self.extended_properties: dict[str, Any] = {}

        # Detected firmware style.  None = not yet determined.
        self._firmware_is_v4: bool | None = None

    def _on_device_response(self, *args: Any) -> None:
        """Handle raw protocol responses from the device."""
        _LOGGER.debug("Device response received: %s", json_dumps(args))
        self._error_count = 0
        self._last_response_time = utcnow()
        self._response_received.set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the state of the device.

        Sends a SINGLE combined status request that includes both the
        standard greeclimate properties AND our extended properties
        (compressor freq, coil temps).  Uses an asyncio.Event to wait for
        the actual response before extracting extended properties, ensuring
        entities see consistent data.
        """
        _LOGGER.debug(
            "Updating device state: %s, error count: %d",
            self.name,
            self._error_count,
        )

        self._response_received.clear()

        try:
            if not self.device.device_cipher:
                await self.device.bind()

            # Build a combined property list: standard + extended.
            props = [x.value for x in Props]
            if not self.device.hid:
                props.append("hid")
            props.extend(EXTENDED_PROPERTIES)

            await self.device.send(
                self.device.create_status_message(
                    self.device.device_info, *props
                )
            )
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
            # Wait for the device to actually respond.
            try:
                await asyncio.wait_for(
                    self._response_received.wait(), timeout=10
                )
            except asyncio.TimeoutError:
                self._error_count += 1
                _LOGGER.warning(
                    "Device %s did not respond within 10 seconds",
                    self.name,
                )
                if self.last_update_success and self._error_count >= MAX_ERRORS:
                    raise UpdateFailed(
                        f"Device {self.name} is unresponsive"
                    )

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
            else:
                self._error_count = 0

        self._last_response_time = utcnow()

        # Extract extended properties from the combined response BEFORE
        # returning, so entities see consistent data in this update cycle.
        self._extract_extended_from_raw()

        raw = self.device.raw_properties
        _LOGGER.debug(
            "Raw properties for %s: %s | Extended: %s",
            self.name,
            raw,
            self.extended_properties,
        )

        return copy.deepcopy(raw)

    def _extract_extended_from_raw(self) -> None:
        """Pull extended property values from raw_properties after update.

        After a combined status request, the device's response includes both
        standard and extended properties in _properties.  Extract and normalise
        the extended ones into self.extended_properties.
        """
        raw = self.device.raw_properties
        if not raw:
            return

        normalised = self._normalise_aliases(raw)
        if normalised:
            self.extended_properties.update(normalised)
            self._detect_firmware_version(normalised)
            _LOGGER.debug(
                "Extended properties for %s (fw_v4=%s): %s",
                self.name,
                self._firmware_is_v4,
                self.extended_properties,
            )

    @staticmethod
    def _normalise_aliases(raw: dict[str, Any]) -> dict[str, Any]:
        """Map firmware-specific property names to canonical keys.

        Different firmware versions use different names for the same data.
        We normalise to the canonical names defined in const.py so that
        sensor entities can use a single key.
        """
        result: dict[str, Any] = {}
        for alias in PROP_COMP_FREQ_ALIASES:
            if alias in raw and raw[alias] is not None:
                result[PROP_COMP_FREQ] = raw[alias]
                break
        for alias in PROP_INDOOR_COIL_ALIASES:
            if alias in raw and raw[alias] is not None:
                result[PROP_INDOOR_COIL_TEMP] = raw[alias]
                break
        for alias in PROP_OUTDOOR_COIL_ALIASES:
            if alias in raw and raw[alias] is not None:
                result[PROP_OUTDOOR_COIL_TEMP] = raw[alias]
                break
        return result

    def _detect_firmware_version(self, props: dict[str, Any]) -> None:
        """Auto-detect firmware temperature convention.

        Uses the same heuristic as greeclimate's handle_state_update:
        if a temperature value is below TEMP_OFFSET (40) the firmware
        reports raw °C ("v4 style").  Also checks device.version if
        greeclimate already identified the firmware from the hid string.
        """
        # If greeclimate already tagged the firmware, trust that.
        ver = self.device.version
        if ver:
            try:
                if int(ver.split(".")[0]) >= 4:
                    self._firmware_is_v4 = True
                    return
            except (ValueError, IndexError):
                pass

        # Heuristic: check coil temps.  If either is non-zero and < offset,
        # the device is reporting raw °C.
        for key in (PROP_INDOOR_COIL_TEMP, PROP_OUTDOOR_COIL_TEMP):
            val = props.get(key)
            if val is not None:
                val = int(val)
                if 0 < val < TEMP_OFFSET:
                    self._firmware_is_v4 = True
                    _LOGGER.info(
                        "Detected v4-style firmware for %s (raw coil temp %d < %d)",
                        self.name,
                        val,
                        TEMP_OFFSET,
                    )
                    return
                if val >= TEMP_OFFSET:
                    self._firmware_is_v4 = False
                    return

    @property
    def firmware_is_v4(self) -> bool | None:
        """Return True if firmware uses raw °C (v4+), False if +40 offset, None if unknown."""
        return self._firmware_is_v4

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
        # De-duplicate against devices already registered (e.g. manual IP binds).
        for coord in self.entry.runtime_data.coordinators:
            if coord.device.device_info.mac == device_info.mac:
                _LOGGER.debug(
                    "Device %s already registered, skipping duplicate discovery",
                    device_info.mac,
                )
                return

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
