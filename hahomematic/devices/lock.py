"""Code to create the required entities for lock devices."""

from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_DIRECTION,
    FIELD_ERROR,
    FIELD_LOCK_STATE,
    FIELD_LOCK_TARGET_LEVEL,
    FIELD_OPEN,
    FIELD_STATE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.binary_sensor import HmBinarySensor
from hahomematic.platforms.sensor import HmSensor
from hahomematic.platforms.switch import HmSwitch

_LOGGER = logging.getLogger(__name__)

# HM constants
LOCK_STATE_UNKNOWN = "UNKNOWN"
LOCK_STATE_LOCKED = "LOCKED"
LOCK_STATE_UNLOCKED = "UNLOCKED"

LOCK_TARGET_LEVEL_LOCKED = "LOCKED"
LOCK_TARGET_LEVEL_UNLOCKED = "UNLOCKED"
LOCK_TARGET_LEVEL_OPEN = "OPEN"

HM_UNLOCKING = "UP"
HM_LOCKING = "DOWN"


class BaseLock(CustomEntity):
    """Class for homematic ip lock entities."""

    _attr_platform = HmPlatform.LOCK

    @property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return true if lock is on."""

    @property
    @abstractmethod
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""

    @property
    @abstractmethod
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""

    @property
    @abstractmethod
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""

    @abstractmethod
    async def lock(self) -> None:
        """Lock the lock."""

    @abstractmethod
    async def unlock(self) -> None:
        """Unlock the lock."""

    @abstractmethod
    async def open(self) -> None:
        """Open the lock."""


class CeIpLock(BaseLock):
    """Class for homematic ip lock entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_lock_state: HmSensor = self._get_entity(
            field_name=FIELD_LOCK_STATE, entity_type=HmSensor
        )
        self._e_lock_target_level: HmAction = self._get_entity(
            field_name=FIELD_LOCK_TARGET_LEVEL, entity_type=HmAction
        )
        self._e_direction: HmSensor = self._get_entity(
            field_name=FIELD_DIRECTION, entity_type=HmSensor
        )
        self._e_error: HmBinarySensor = self._get_entity(
            field_name=FIELD_ERROR, entity_type=HmBinarySensor
        )

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_lock_state.value == LOCK_STATE_LOCKED

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_LOCKING
        return None

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_UNLOCKING
        return None

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._e_error.value is not None and self._e_error.value is True

    async def lock(self) -> None:
        """Lock the lock."""
        await self._e_lock_target_level.send_value(LOCK_TARGET_LEVEL_LOCKED)

    async def unlock(self) -> None:
        """Unlock the lock."""
        await self._e_lock_target_level.send_value(LOCK_TARGET_LEVEL_UNLOCKED)

    async def open(self) -> None:
        """Open the lock."""
        await self._e_lock_target_level.send_value(LOCK_TARGET_LEVEL_OPEN)


class CeRfLock(BaseLock):
    """Class for classic homematic lock entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_state: HmSwitch = self._get_entity(
            field_name=FIELD_STATE, entity_type=HmSwitch
        )
        self._e_open: HmAction = self._get_entity(
            field_name=FIELD_OPEN, entity_type=HmAction
        )
        self._e_direction: HmSensor = self._get_entity(
            field_name=FIELD_DIRECTION, entity_type=HmSensor
        )
        self._e_error: HmSensor = self._get_entity(
            field_name=FIELD_ERROR, entity_type=HmSensor
        )

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_state.value is not True

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_LOCKING
        return None

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_UNLOCKING
        return None

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._e_error.value is not None and self._e_error.value != "NO_ERROR"

    async def lock(self) -> None:
        """Lock the lock."""
        await self._e_state.send_value(False)

    async def unlock(self) -> None:
        """Unlock the lock."""
        await self._e_state.send_value(True)

    async def open(self) -> None:
        """Open the lock."""
        await self._e_open.send_value(True)


def make_ip_lock(
    device: hm_device.HmDevice, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip lock entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeIpLock,
        device_enum=EntityDefinition.IP_LOCK,
        group_base_channels=group_base_channels,
    )


def make_rf_lock(
    device: hm_device.HmDevice, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic rf lock entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeRfLock,
        device_enum=EntityDefinition.RF_LOCK,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-DLD": (make_ip_lock, [0]),
    "HM-Sec-Key": (make_rf_lock, [1]),
}

BLACKLISTED_DEVICES: list[str] = []
