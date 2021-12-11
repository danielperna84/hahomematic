"""Code to create the required entities for lock devices."""

from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_LOCK_STATE,
    FIELD_LOCK_TARGET_LEVEL,
    FIELD_OPEN,
    FIELD_STATE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity

_LOGGER = logging.getLogger(__name__)

HM_LOCKED = 0
HM_UNLOCKED = 1
HM_OPEN = 2


class BaseLock(CustomEntity):
    """Class for homematic ip lock entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        address: str,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[str, Any],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.LOCK,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HMLock.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return True

    @abstractmethod
    async def lock(self) -> None:
        """Lock the lock."""
        ...

    @abstractmethod
    async def unlock(self) -> None:
        """Unlock the lock."""
        ...

    @abstractmethod
    async def open(self) -> None:
        """Open the lock."""
        ...


class IpLock(BaseLock):
    """Class for homematic ip lock entities."""

    @property
    def _lock_state(self) -> float | None:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_LOCK_STATE)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._lock_state == HM_LOCKED

    async def lock(self) -> None:
        """Lock the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_LOCKED)

    async def unlock(self) -> None:
        """Unlock the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_UNLOCKED)

    async def open(self) -> None:
        """Open the lock."""
        await self._send_value(FIELD_LOCK_TARGET_LEVEL, HM_OPEN)


class RfLock(BaseLock):
    """Class for classic homematic lock entities."""

    @property
    def _state(self) -> bool | None:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_STATE)

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return not self._state is True

    async def lock(self) -> None:
        """Lock the lock."""
        await self._send_value(FIELD_STATE, True)

    async def unlock(self) -> None:
        """Unlock the lock."""
        await self._send_value(FIELD_STATE, False)

    async def open(self) -> None:
        """Open the lock."""
        await self._send_value(FIELD_OPEN, True)


def make_ip_lock(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip lock entities."""
    return make_custom_entity(
        device, address, IpLock, EntityDefinition.IP_LOCK, group_base_channels
    )


def make_rf_lock(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic rf lock entities."""
    return make_custom_entity(
        device, address, RfLock, EntityDefinition.RF_LOCK, group_base_channels
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-DLD": (make_ip_lock, []),
    "HM-Sec-Key*": (make_rf_lock, []),
}
