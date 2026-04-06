"""Binary sensor platform for Gree Climate Extended.

Provides:
  - Compressor Active: True when the compressor is running (CompFreq > 0).
  - Idle:              True when the unit is powered on but the compressor is
                       stopped (i.e., target temperature reached / coasting).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DISPATCH_DEVICE_DISCOVERED, PROP_COMP_FREQ
from .coordinator import DeviceDataUpdateCoordinator, GreeExtConfigEntry
from .entity import GreeEntity

_LOGGER = logging.getLogger(__name__)


BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="compressor_active",
        translation_key="compressor_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="idle",
        translation_key="idle",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeExtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree Extended binary sensors from a config entry."""

    added_macs: set[str] = set()

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register binary sensor entities for a discovered device."""
        mac = coordinator.device.device_info.mac
        if mac in added_macs:
            return
        added_macs.add(mac)
        async_add_entities(
            [
                GreeCompressorActiveSensor(coordinator),
                GreeIdleSensor(coordinator),
            ]
        )

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, DISPATCH_DEVICE_DISCOVERED, init_device
        )
    )


class GreeCompressorActiveSensor(GreeEntity, BinarySensorEntity):
    """Binary sensor: True when the compressor is actively running.

    Derived from the extended property ``CompFreq``.  If the device does not
    report CompFreq, the sensor shows *unknown* rather than a wrong value.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "compressor_active"

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the compressor active sensor."""
        super().__init__(coordinator, "compressor_active")

    @property
    def is_on(self) -> bool | None:
        """Return True if the compressor is running."""
        freq = self.coordinator.extended_properties.get(PROP_COMP_FREQ)
        if freq is None:
            return None
        return int(freq) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose raw compressor frequency as an attribute."""
        freq = self.coordinator.extended_properties.get(PROP_COMP_FREQ)
        if freq is not None:
            return {"compressor_frequency_hz": int(freq)}
        return {}


class GreeIdleSensor(GreeEntity, BinarySensorEntity):
    """Binary sensor: True when the unit is ON but compressor has stopped.

    This indicates the unit is coasting (fan running, compressor off) — the
    exact state that the ``force_fan_off`` service is designed to act on.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "idle"

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the idle sensor."""
        super().__init__(coordinator, "idle")

    @property
    def is_on(self) -> bool | None:
        """Return True if the unit is powered on but compressor is off."""
        power = self.coordinator.device.power
        if power is None:
            return None
        if not power:
            return False

        freq = self.coordinator.extended_properties.get(PROP_COMP_FREQ)
        if freq is None:
            return None
        return int(freq) == 0
