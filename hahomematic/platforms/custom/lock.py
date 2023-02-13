"""
Module for entities implemented using the lock platform.

See https://www.home-assistant.io/integrations/lock/.
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Final

from hahomematic.const import HmPlatform
from hahomematic.decorators import bind_collector
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import (
    FIELD_DIRECTION,
    FIELD_ERROR,
    FIELD_LOCK_STATE,
    FIELD_LOCK_TARGET_LEVEL,
    FIELD_OPEN,
    FIELD_STATE,
    HmEntityDefinition,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.entity import CallParameterCollector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch
from hahomematic.platforms.support import value_property

# HM constants
LOCK_STATE_UNKNOWN: Final = "UNKNOWN"
LOCK_STATE_LOCKED: Final = "LOCKED"
LOCK_STATE_UNLOCKED: Final = "UNLOCKED"

LOCK_TARGET_LEVEL_LOCKED: Final = "LOCKED"
LOCK_TARGET_LEVEL_UNLOCKED: Final = "UNLOCKED"
LOCK_TARGET_LEVEL_OPEN: Final = "OPEN"

HM_UNLOCKING: Final = "UP"
HM_LOCKING: Final = "DOWN"
HM_NO_ERROR: Final = "NO_ERROR"


class BaseLock(CustomEntity):
    """Class for HomematicIP lock entities."""

    _attr_platform = HmPlatform.LOCK

    @value_property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return true if lock is on."""

    @value_property
    @abstractmethod
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""

    @value_property
    @abstractmethod
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""

    @value_property
    @abstractmethod
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""

    @abstractmethod
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""

    @abstractmethod
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""

    @abstractmethod
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""


class CeIpLock(BaseLock):
    """Class for HomematicIP lock entities."""

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

    @value_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_lock_state.value == LOCK_STATE_LOCKED

    @value_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_LOCKING
        return None

    @value_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_UNLOCKING
        return None

    @value_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @bind_collector
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._e_lock_target_level.send_value(
            value=LOCK_TARGET_LEVEL_LOCKED, collector=collector
        )

    @bind_collector
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._e_lock_target_level.send_value(
            value=LOCK_TARGET_LEVEL_UNLOCKED, collector=collector
        )

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._e_lock_target_level.send_value(
            value=LOCK_TARGET_LEVEL_OPEN, collector=collector
        )


class CeRfLock(BaseLock):
    """Class for classic HomeMatic lock entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_state: HmSwitch = self._get_entity(field_name=FIELD_STATE, entity_type=HmSwitch)
        self._e_open: HmAction = self._get_entity(field_name=FIELD_OPEN, entity_type=HmAction)
        self._e_direction: HmSensor = self._get_entity(
            field_name=FIELD_DIRECTION, entity_type=HmSensor
        )
        self._e_error: HmSensor = self._get_entity(field_name=FIELD_ERROR, entity_type=HmSensor)

    @value_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_state.value is not True

    @value_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_LOCKING
        return None

    @value_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_UNLOCKING
        return None

    @value_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._e_error.value is not None and self._e_error.value != HM_NO_ERROR

    @bind_collector
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._e_state.send_value(value=False, collector=collector)

    @bind_collector
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._e_state.send_value(value=True, collector=collector)

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._e_open.send_value(value=True, collector=collector)


def make_ip_lock(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create HomematicIP lock entities."""
    return hmed.make_custom_entity(
        device=device,
        custom_entity_class=CeIpLock,
        device_enum=HmEntityDefinition.IP_LOCK,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_rf_lock(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create HomeMatic rf lock entities."""
    return hmed.make_custom_entity(
        device=device,
        custom_entity_class=CeRfLock,
        device_enum=HmEntityDefinition.RF_LOCK,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant
DEVICES: dict[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HM-Sec-Key": CustomConfig(
        func=make_rf_lock,
        channels=(1,),
        extended=ExtendedConfig(
            additional_entities={
                1: (
                    "DIRECTION",
                    "ERROR",
                ),
            }
        ),
    ),
    "HmIP-DLD": CustomConfig(
        func=make_ip_lock,
        channels=(0,),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ERROR_JAMMED",),
            }
        ),
    ),
}

hmed.ALL_DEVICES.append(DEVICES)
