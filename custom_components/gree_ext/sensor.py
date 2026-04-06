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
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DISPATCH_DEVICE_DISCOVERED,
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

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register sensor entities for a discovered device."""
        async_add_entities(
            [
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
        """Return the coil temperature in °C."""
        raw = self.coordinator.extended_properties.get(self._prop_name)
        if raw is None:
            return None

        raw = int(raw)
        if raw == 0:
            return None

        # Apply the same offset logic as greeclimate's current_temperature.
        version = self.coordinator.device.version
        v_major = 0
        if version:
            try:
                v_major = int(version.split(".")[0])
            except (ValueError, IndexError):
                pass

        if v_major >= 4:
            return float(raw)
        return float(raw - TEMP_OFFSET)
