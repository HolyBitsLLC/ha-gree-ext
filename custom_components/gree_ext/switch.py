"""Switch platform for Gree Climate Extended.

Re-implements the upstream switch entities (panel light, quiet, fresh air,
xfan, health/anion) so this integration is a complete replacement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from greeclimate.device import Device

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DISPATCH_DEVICE_DISCOVERED
from .coordinator import DeviceDataUpdateCoordinator, GreeExtConfigEntry
from .entity import GreeEntity


@dataclass(kw_only=True, frozen=True)
class GreeSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Gree switch entity."""

    get_value_fn: Callable[[Device], bool]
    set_value_fn: Callable[[Device, bool], None]


def _set_light(device: Device, value: bool) -> None:
    device.light = value


def _set_quiet(device: Device, value: bool) -> None:
    device.quiet = value


def _set_fresh_air(device: Device, value: bool) -> None:
    device.fresh_air = value


def _set_xfan(device: Device, value: bool) -> None:
    device.xfan = value


def _set_anion(device: Device, value: bool) -> None:
    device.anion = value


def _get_beep(device: Device) -> bool:
    val = device.raw_properties.get("Bwt")
    return bool(val) if val is not None else True


def _set_beep(device: Device, value: bool) -> None:
    device._properties["Bwt"] = int(value)
    if "Bwt" not in device._dirty:
        device._dirty.append("Bwt")


GREE_SWITCHES: tuple[GreeSwitchEntityDescription, ...] = (
    GreeSwitchEntityDescription(
        key="Panel Light",
        translation_key="light",
        get_value_fn=lambda d: d.light,
        set_value_fn=_set_light,
    ),
    GreeSwitchEntityDescription(
        key="Quiet",
        translation_key="quiet",
        get_value_fn=lambda d: d.quiet,
        set_value_fn=_set_quiet,
    ),
    GreeSwitchEntityDescription(
        key="Fresh Air",
        translation_key="fresh_air",
        get_value_fn=lambda d: d.fresh_air,
        set_value_fn=_set_fresh_air,
    ),
    GreeSwitchEntityDescription(
        key="XFan",
        translation_key="xfan",
        get_value_fn=lambda d: d.xfan,
        set_value_fn=_set_xfan,
    ),
    GreeSwitchEntityDescription(
        key="Health mode",
        translation_key="health_mode",
        get_value_fn=lambda d: d.anion,
        set_value_fn=_set_anion,
    ),
    GreeSwitchEntityDescription(
        key="Beep",
        translation_key="beep",
        get_value_fn=_get_beep,
        set_value_fn=_set_beep,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeExtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gree HVAC switches from a config entry."""

    added_macs: set[str] = set()

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register switch entities for a discovered device."""
        mac = coordinator.device.device_info.mac
        if mac in added_macs:
            return
        added_macs.add(mac)
        async_add_entities(
            GreeSwitch(coordinator=coordinator, description=description)
            for description in GREE_SWITCHES
        )

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, DISPATCH_DEVICE_DISCOVERED, init_device
        )
    )


class GreeSwitch(GreeEntity, SwitchEntity):
    """Generic Gree switch entity."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: GreeSwitchEntityDescription

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        description: GreeSwitchEntityDescription,
    ) -> None:
        """Initialize the Gree device."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def is_on(self) -> bool:
        """Return if the state is turned on."""
        return self.entity_description.get_value_fn(
            self.coordinator.device
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self.entity_description.set_value_fn(
            self.coordinator.device, True
        )
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self.entity_description.set_value_fn(
            self.coordinator.device, False
        )
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
