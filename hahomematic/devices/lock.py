"""Code to create the required entities for lock devices."""

from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.devices.device_description import (
    FIELD_LOCK_STATE,
    FIELD_LOCK_TARGET_LEVEL,
    FIELD_OPEN,
    FIELD_STATE,
    DeviceDescription,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

_LOGGER = logging.getLogger(__name__)

HM_LOCKED = 0
HM_UNLOCKED = 1
HM_OPEN = 2


class IpLock(CustomEntity):
    """Class for homematic ip lock entities."""

    def __init__(
        self,
        device,
        address,
        unique_id,
        device_enum,
        device_desc,
        entity_desc,
        channel_no,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            device_enum=device_enum,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HmPlatform.LOCK,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _lock_state(self) -> float:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_LOCK_STATE)

    @property
    def is_locked(self):
        """Return true if lock is on."""
        return self._lock_state == HM_LOCKED

    async def lock(self, **kwargs):
        """Lock the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_LOCKED)

    async def unlock(self, **kwargs):
        """Unlock the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_UNLOCKED)

    async def open(self, **kwargs: Any) -> None:
        """Open the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_OPEN)


class RfLock(CustomEntity):
    """Class for classic homematic lock entities."""

    def __init__(
        self,
        device,
        address,
        unique_id,
        device_enum,
        device_desc,
        entity_desc,
        channel_no,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            device_enum=device_enum,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HmPlatform.LOCK,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _state(self) -> bool:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_STATE)

    @property
    def is_locked(self):
        """Return true if lock is on."""
        return not self._state

    async def lock(self, **kwargs):
        """Lock the lock."""
        await self._send_value(FIELD_STATE, True)

    async def unlock(self, **kwargs):
        """Unlock the lock."""
        await self._send_value(FIELD_STATE, False)

    async def open(self, **kwargs: Any) -> None:
        """Open the lock."""
        await self._send_value(FIELD_OPEN, True)


def make_ip_lock(device, address, group_base_channels: [int]):
    """Creates homematic ip lock entities."""
    return make_custom_entity(
        device, address, IpLock, DeviceDescription.IP_LOCK, group_base_channels
    )


def make_rf_lock(device, address, group_base_channels: [int]):
    """Creates homematic rf lock entities."""
    return make_custom_entity(
        device, address, RfLock, DeviceDescription.RF_LOCK, group_base_channels
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES = {
    "HmIP-DLD": (make_ip_lock, []),
    "HM-Sec-Key*": (make_rf_lock, []),
}
