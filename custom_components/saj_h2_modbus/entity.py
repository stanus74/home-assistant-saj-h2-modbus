"""Shared base for SAJ entities."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .hub import SAJModbusHub


class SajBaseEntity:
    """Holds the hub reference and device_info assignment shared by every
    SAJ entity, regardless of which HA entity class it otherwise extends.

    Deliberately not part of any cooperative super().__init__() chain:
    sensor.py and switch.py also inherit CoordinatorEntity and call
    super().__init__(coordinator=hub) themselves, while number.py and
    text.py stay plain input entities (see the F4 decision in
    plans/opti-0108.md). Subclasses call SajBaseEntity.__init__() directly
    so this stays independent of that difference and of each class's own
    MRO.
    """

    def __init__(self, hub: "SAJModbusHub", device_info: dict[str, Any]) -> None:
        self._hub = hub
        self._attr_device_info = device_info
