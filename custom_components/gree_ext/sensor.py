"""Sensor platform for Gree Climate Extended.

Provides:
  - Indoor Coil Temperature:  TemInlet from the device (evaporator / indoor).
  - Outdoor Coil Temperature: TemOutlet from the device (condenser / outdoor).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfFrequency, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DISPATCH_DEVICE_DISCOVERED,
    PROP_COMP_FREQ,
    PROP_INDOOR_COIL_TEMP,
    PROP_OUTDOOR_COIL_TEMP,
    TEMP_OFFSET,
)
from .coordinator import DeviceDataUpdateCoordinator, GreeExtConfigEntry
from .entity import GreeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeExtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree Extended temperature sensors from a config entry."""

    added_macs: set[str] = set()

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register sensor entities for a discovered device."""
        mac = coordinator.device.device_info.mac
        if mac in added_macs:
            return
        added_macs.add(mac)
        async_add_entities(
            [
                GreeCompressorFrequencySensor(coordinator),
                GreeCoilTemperatureSensor(
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="indoor_coil_temp",
                        translation_key="indoor_coil_temp",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        suggested_display_precision=0,
                    ),
                    prop_name=PROP_INDOOR_COIL_TEMP,
                ),
                GreeCoilTemperatureSensor(
                    coordinator=coordinator,
                    description=SensorEntityDescription(
                        key="outdoor_coil_temp",
                        translation_key="outdoor_coil_temp",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        suggested_display_precision=0,
                    ),
                    prop_name=PROP_OUTDOOR_COIL_TEMP,
                ),
            ]
        )

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, DISPATCH_DEVICE_DISCOVERED, init_device
        )
    )


class GreeCoilTemperatureSensor(GreeEntity, SensorEntity):
    """Temperature sensor for indoor or outdoor coil.

    The raw value from the device uses an offset of +40 on firmware < 4.0
    (same convention as TemSen in greeclimate).  On firmware >= 4.0 the raw
    value IS the temperature in Celsius.
    """

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        description: SensorEntityDescription,
        prop_name: str,
    ) -> None:
        """Initialize the coil temperature sensor."""
        self.entity_description = description
        self._prop_name = prop_name
        super().__init__(coordinator, description.key)

    @property
    def native_value(self) -> float | None:
        """Return the coil temperature in °C.

        Supports both firmware conventions:
          - FW < 4.0: raw value has +40 offset (e.g. 65 → 25°C)
          - FW >= 4.0: raw value IS the temperature in °C

        Detection is handled by the coordinator's firmware_is_v4 property
        which uses multiple signals (device.version from hid, heuristic on
        raw temp values).  If detection hasn't happened yet, falls back to
        the heuristic inline.
        """
        raw = self.coordinator.extended_properties.get(self._prop_name)
        if raw is None:
            return None

        raw = int(raw)
        if raw == 0:
            return None

        fw_v4 = self.coordinator.firmware_is_v4
        if fw_v4 is True:
            return float(raw)
        if fw_v4 is False:
            return float(raw - TEMP_OFFSET)

        # firmware_is_v4 is None — detection hasn't run yet.
        # Apply the same inline heuristic: values < offset are raw °C.
        if raw < TEMP_OFFSET:
            return float(raw)
        return float(raw - TEMP_OFFSET)


class GreeCompressorFrequencySensor(GreeEntity, SensorEntity):
    """Numeric sensor exposing the compressor frequency in Hz.

    Complements the binary compressor_active sensor with the actual
    frequency value for use in automations and dashboards.
    """

    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_translation_key = "compressor_frequency"
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the compressor frequency sensor."""
        super().__init__(coordinator, "compressor_frequency")

    @property
    def native_value(self) -> int | None:
        """Return the compressor frequency in Hz."""
        freq = self.coordinator.extended_properties.get(PROP_COMP_FREQ)
        if freq is None:
            return None
        return int(freq)
