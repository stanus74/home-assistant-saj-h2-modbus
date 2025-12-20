import logging
import time
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import SAJModbusHub

_LOGGER = logging.getLogger(__name__)

PASSIVE_SWITCH_KEYS = {"passive_charge", "passive_discharge"}
PASSIVE_MODE_TARGETS = {
    "passive_charge": 2,
    "passive_discharge": 1,
}
PASSIVE_MODE_PENDING_ATTR = "_pending_passive_mode_state"

SWITCH_DEFINITIONS = [
    {
        "key": "charging",
        "name": "Charging Control",
        "unique_id_suffix": "_control",
    },
    {
        "key": "discharging",
        "name": "Discharging Control",
        "unique_id_suffix": "_control",
    },
    {
        "key": "passive_charge",
        "name": "Passive Charge Control",
        "unique_id_suffix": "_passive_charge_control",
    },
    {
        "key": "passive_discharge",
        "name": "Passive Discharge Control",
        "unique_id_suffix": "_passive_discharge_control",
    },
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SAJ switches."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    device_info = hass.data[DOMAIN][entry.entry_id]["device_info"]

    entities = []
    for desc in SWITCH_DEFINITIONS:
        entity = BaseSajSwitch(
            hub=hub,
            device_info=device_info,
            description=desc,
        )
        entities.append(entity)

    async_add_entities(entities)
    _LOGGER.info("Added SAJ switches")


class BaseSajSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, hub: SAJModbusHub, device_info, description: dict):
        super().__init__(hub)
        self._hub = hub
        self._definition = description
        self._switch_type = description["key"]
        self._attr_device_info = device_info
        self._pending_attr = (
            PASSIVE_MODE_PENDING_ATTR
            if self._switch_type in PASSIVE_SWITCH_KEYS
            else f"_pending_{self._switch_type}_state"
        )
        self._attr_unique_id = f"{hub.name}_{self._switch_type}{description['unique_id_suffix']}"
        self._attr_name = f"{hub.name} {description['name']}"
        self._attr_entity_registry_enabled_default = True
        self._attr_assumed_state = True
        self._attr_should_poll = False
        self._last_switch_time = 0
        self._switch_timeout = 2

    @property
    def is_on(self) -> bool:
        """Return true if switch is on.

        Simplified to only check register values without AppMode dependency.
        This ensures immediate UI feedback like in version 2.6.0.
        """
        try:
            data = self._hub.inverter_data

            if self._switch_type == "charging":
                charging_enabled = data.get("charging_enabled")
                if charging_enabled is None:
                    return False
                return bool(charging_enabled > 0)

            elif self._switch_type == "discharging":
                discharging_enabled = data.get("discharging_enabled")
                if discharging_enabled is None:
                    return False
                return bool(discharging_enabled > 0)

            elif self._switch_type in PASSIVE_SWITCH_KEYS:
                passive_state = data.get("passive_charge_enable")
                if passive_state is None:
                    return False
                return passive_state == PASSIVE_MODE_TARGETS[self._switch_type]

        except Exception as e:
            _LOGGER.warning("Error getting %s state: %s", self._switch_type, e)
            return False

        # Fallback (should never reach here with current switch types)
        return False

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        pending = getattr(self._hub, self._pending_attr, None)
        attrs = {"pending_write": pending is not None}
        if self._switch_type in PASSIVE_SWITCH_KEYS:
            attrs["passive_mode_value"] = self._hub.inverter_data.get("passive_charge_enable")
        return attrs

    async def _set_state(self, desired_state: bool) -> None:
        """Set the switch state with shared logic.

        Sets pending state and triggers processing in next update cycle.
        Does NOT apply optimistic updates to avoid conflicts with card slot configurations.
        """
        if self.is_on == desired_state:
            _LOGGER.debug("%s already %s", self._switch_type.capitalize(), "on" if desired_state else "off")
            return

        if not self._allow_switch():
            return

        try:
            _LOGGER.debug("%s turned %s", self._switch_type.capitalize(), "ON" if desired_state else "OFF")
            if self._switch_type in PASSIVE_SWITCH_KEYS:
                if not await self._handle_passive_mode_state(desired_state):
                    return
            else:
                setter = getattr(self._hub, f"set_{self._switch_type}", None)
                if setter is None:
                    _LOGGER.error("Hub missing setter for %s", self._switch_type)
                    return
                await setter(desired_state)

            self._last_switch_time = time.time()
            pending_value = getattr(self._hub, self._pending_attr, None)
            _LOGGER.debug("Pending %s set to: %s", self._pending_attr, pending_value)

            # UI will show pending status via extra_state_attributes
            self.async_write_ha_state()
            _LOGGER.debug(
                "Pending %s setting will be processed in next update cycle",
                self._switch_type
            )
        except Exception as e:
            _LOGGER.error("Failed to set %s state: %s", self._switch_type, e)
            raise

    async def _handle_passive_mode_state(self, desired_state: bool) -> bool:
        hub_method = getattr(self._hub, "set_passive_mode", None)
        if hub_method is None:
            _LOGGER.error("Passive mode control not supported by hub")
            return False
        target_value = PASSIVE_MODE_TARGETS[self._switch_type] if desired_state else 0
        await hub_method(target_value)
        return True

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)

    def _allow_switch(self) -> bool:
        current_time = time.time()
        elapsed = current_time - self._last_switch_time
        if elapsed < self._switch_timeout:
            remaining = round(self._switch_timeout - elapsed, 1)
            _LOGGER.warning("Time lock active! Wait %ss before switching %s again.", remaining, self._switch_type)
            return False
        return True
