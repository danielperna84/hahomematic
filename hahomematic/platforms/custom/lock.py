"""
Module for entities implemented using the lock platform.

See https://www.home-assistant.io/integrations/lock/.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from enum import StrEnum

from hahomematic.const import HmPlatform, Parameter
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch


class LockActivity(StrEnum):
    """Enum with lock activities."""

    LOCKING = "DOWN"
    UNLOCKING = "UP"


class LockState(StrEnum):
    """Enum with lock states."""

    LOCKED = "LOCKED"
    NO_ERROR = "NO_ERROR"
    OPEN = "OPEN"
    UNKNOWN = "UNKNOWN"
    UNLOCKED = "UNLOCKED"


class BaseLock(CustomEntity):
    """Class for HomematicIP lock entities."""

    _platform = HmPlatform.LOCK

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
            field=Field.LOCK_STATE, entity_type=HmSensor
        )
        self._e_lock_target_level: HmAction = self._get_entity(
            field=Field.LOCK_TARGET_LEVEL, entity_type=HmAction
        )
        self._e_direction: HmSensor = self._get_entity(field=Field.DIRECTION, entity_type=HmSensor)

    @value_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_lock_state.value == LockState.LOCKED  # type: ignore[no-any-return]

    @value_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == LockActivity.LOCKING
        return None

    @value_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == LockActivity.UNLOCKING
        return None

    @value_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @bind_collector
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._e_lock_target_level.send_value(value=LockState.LOCKED, collector=collector)

    @bind_collector
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._e_lock_target_level.send_value(value=LockState.UNLOCKED, collector=collector)

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._e_lock_target_level.send_value(value=LockState.OPEN, collector=collector)


class CeRfLock(BaseLock):
    """Class for classic HomeMatic lock entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_state: HmSwitch = self._get_entity(field=Field.STATE, entity_type=HmSwitch)
        self._e_open: HmAction = self._get_entity(field=Field.OPEN, entity_type=HmAction)
        self._e_direction: HmSensor = self._get_entity(field=Field.DIRECTION, entity_type=HmSensor)
        self._e_error: HmSensor = self._get_entity(field=Field.ERROR, entity_type=HmSensor)

    @value_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._e_state.value is not True

    @value_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == LockActivity.LOCKING
        return None

    @value_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == LockActivity.UNLOCKING
        return None

    @value_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._e_error.value is not None and self._e_error.value != LockState.NO_ERROR

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
        entity_class=CeIpLock,
        device_profile=DeviceProfile.IP_LOCK,
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
        entity_class=CeRfLock,
        device_profile=DeviceProfile.RF_LOCK,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HM-Sec-Key": CustomConfig(
        make_ce_func=make_rf_lock,
        channels=(1,),
        extended=ExtendedConfig(
            additional_entities={
                1: (
                    Parameter.DIRECTION,
                    Parameter.ERROR,
                ),
            }
        ),
    ),
    "HmIP-DLD": CustomConfig(
        make_ce_func=make_ip_lock,
        channels=(0,),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ERROR_JAMMED,),
            }
        ),
    ),
}

hmed.ALL_DEVICES.append(DEVICES)
