"""Select platform for Gree Climate Extended.

Provides fine-grained control over horizontal and vertical vane positions,
beyond the simple on/off swing toggle in the climate entity.
"""

from __future__ import annotations

import logging
from typing import Any

from greeclimate.device import HorizontalSwing, VerticalSwing

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DISPATCH_DEVICE_DISCOVERED
from .coordinator import DeviceDataUpdateCoordinator, GreeExtConfigEntry
from .entity import GreeEntity

_LOGGER = logging.getLogger(__name__)

# Human-readable labels → greeclimate enum values
VERTICAL_POSITIONS: dict[str, VerticalSwing] = {
    "Default": VerticalSwing.Default,
    "Full Swing": VerticalSwing.FullSwing,
    "Fixed Upper": VerticalSwing.FixedUpper,
    "Fixed Upper-Middle": VerticalSwing.FixedUpperMiddle,
    "Fixed Middle": VerticalSwing.FixedMiddle,
    "Fixed Lower-Middle": VerticalSwing.FixedLowerMiddle,
    "Fixed Lower": VerticalSwing.FixedLower,
    "Swing Upper": VerticalSwing.SwingUpper,
    "Swing Upper-Middle": VerticalSwing.SwingUpperMiddle,
    "Swing Middle": VerticalSwing.SwingMiddle,
    "Swing Lower-Middle": VerticalSwing.SwingLowerMiddle,
    "Swing Lower": VerticalSwing.SwingLower,
}
VERTICAL_POSITIONS_REVERSE: dict[int, str] = {
    v.value: k for k, v in VERTICAL_POSITIONS.items()
}

HORIZONTAL_POSITIONS: dict[str, HorizontalSwing] = {
    "Default": HorizontalSwing.Default,
    "Full Swing": HorizontalSwing.FullSwing,
    "Left": HorizontalSwing.Left,
    "Left-Center": HorizontalSwing.LeftCenter,
    "Center": HorizontalSwing.Center,
    "Right-Center": HorizontalSwing.RightCenter,
    "Right": HorizontalSwing.Right,
}
HORIZONTAL_POSITIONS_REVERSE: dict[int, str] = {
    v.value: k for k, v in HORIZONTAL_POSITIONS.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeExtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree Extended swing position selects from a config entry."""

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register select entities for a discovered device."""
        async_add_entities(
            [
                GreeVerticalSwingSelect(coordinator),
                GreeHorizontalSwingSelect(coordinator),
            ]
        )

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, DISPATCH_DEVICE_DISCOVERED, init_device
        )
    )


class GreeVerticalSwingSelect(GreeEntity, SelectEntity):
    """Select entity for vertical vane position."""

    _attr_translation_key = "vertical_swing"
    _attr_options = list(VERTICAL_POSITIONS.keys())
    _attr_icon = "mdi:arrow-up-down"

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the vertical swing select."""
        super().__init__(coordinator, "vertical_swing")

    @property
    def current_option(self) -> str | None:
        """Return the current vertical swing position."""
        val = self.coordinator.device.vertical_swing
        if val is None:
            return None
        return VERTICAL_POSITIONS_REVERSE.get(int(val), "Default")

    async def async_select_option(self, option: str) -> None:
        """Set the vertical swing position."""
        if option not in VERTICAL_POSITIONS:
            raise ValueError(f"Invalid vertical swing position: {option}")

        self.coordinator.device.vertical_swing = VERTICAL_POSITIONS[option]
        await self.coordinator.push_state_update()
        self.async_write_ha_state()


class GreeHorizontalSwingSelect(GreeEntity, SelectEntity):
    """Select entity for horizontal vane position."""

    _attr_translation_key = "horizontal_swing"
    _attr_options = list(HORIZONTAL_POSITIONS.keys())
    _attr_icon = "mdi:arrow-left-right"

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the horizontal swing select."""
        super().__init__(coordinator, "horizontal_swing")

    @property
    def current_option(self) -> str | None:
        """Return the current horizontal swing position."""
        val = self.coordinator.device.horizontal_swing
        if val is None:
            return None
        return HORIZONTAL_POSITIONS_REVERSE.get(int(val), "Default")

    async def async_select_option(self, option: str) -> None:
        """Set the horizontal swing position."""
        if option not in HORIZONTAL_POSITIONS:
            raise ValueError(f"Invalid horizontal swing position: {option}")

        self.coordinator.device.horizontal_swing = HORIZONTAL_POSITIONS[option]
        await self.coordinator.push_state_update()
        self.async_write_ha_state()
