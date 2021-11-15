# pylint: disable=line-too-long
"""
Code to create the required entities for lock devices.
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_COVER
from hahomematic.devices.device_description import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_STOP,
    Devices,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

_LOGGER = logging.getLogger(__name__)


class HmLock(CustomEntity):

    # pylint: disable=too-many-arguments
    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

       # Lock State ch1
       # LOCK_TARGET_LEVEL

    @property
    def is_locked(self):
        """Return true if lock is on."""
        return self._device.is_locked

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        await self._device.lock()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        await self._device.unlock()

    async def async_open(self, **kwargs: Any) -> None:
        """Open the lock."""
        pass
