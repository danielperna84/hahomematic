"""
Module for entities implemented using the siren platform.

See https://www.home-assistant.io/integrations/siren/.
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Final

from hahomematic.const import HmPlatform
from hahomematic.decorators import bind_collector
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import (
    FIELD_ACOUSTIC_ALARM_ACTIVE,
    FIELD_ACOUSTIC_ALARM_SELECTION,
    FIELD_DURATION,
    FIELD_DURATION_UNIT,
    FIELD_OPTICAL_ALARM_ACTIVE,
    FIELD_OPTICAL_ALARM_SELECTION,
    CustomConfig,
    ExtendedConfig,
    HmEntityDefinition,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.entity import CallParameterCollector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.support import value_property

# HM constants
HMIP_ACOUSTIC_ALARM_SELECTION: Final = "ACOUSTIC_ALARM_SELECTION"
HMIP_OPTICAL_ALARM_SELECTION: Final = "OPTICAL_ALARM_SELECTION"
HMIP_DURATION_UNIT: Final = "DURATION_UNIT"
HMIP_DURATION_VALUE: Final = "DURATION_VALUE"

DEFAULT_ACOUSTIC_ALARM_SELECTION: Final = "FREQUENCY_RISING_AND_FALLING"
DEFAULT_OPTICAL_ALARM_SELECTION: Final = "BLINKING_ALTERNATELY_REPEATING"
DISABLE_ACOUSTIC_SIGNAL: Final = "DISABLE_ACOUSTIC_SIGNAL"
DISABLE_OPTICAL_SIGNAL: Final = "DISABLE_OPTICAL_SIGNAL"
DEFAULT_DURATION_UNIT: Final = "S"
DEFAULT_DURATION_VALUE: Final = 60


class BaseSiren(CustomEntity):
    """Class for HomeMatic siren entities."""

    _attr_platform = HmPlatform.SIREN

    @value_property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if siren is on."""

    @value_property
    @abstractmethod
    def available_tones(self) -> tuple[str, ...] | None:
        """Return a list of available tones."""

    @value_property
    @abstractmethod
    def available_lights(self) -> tuple[str, ...] | None:
        """Return a list of available lights."""

    @abstractmethod
    async def turn_on(
        self,
        acoustic_alarm: str,
        optical_alarm: str,
        duration: int = DEFAULT_DURATION_VALUE,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Turn the device on."""

    @abstractmethod
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""


class CeIpSiren(BaseSiren):
    """Class for HomematicIP siren entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_acoustic_alarm_active: HmBinarySensor = self._get_entity(
            field_name=FIELD_ACOUSTIC_ALARM_ACTIVE, entity_type=HmBinarySensor
        )
        self._e_acoustic_alarm_selection: HmAction = self._get_entity(
            field_name=FIELD_ACOUSTIC_ALARM_SELECTION, entity_type=HmAction
        )
        self._e_optical_alarm_active: HmBinarySensor = self._get_entity(
            field_name=FIELD_OPTICAL_ALARM_ACTIVE, entity_type=HmBinarySensor
        )
        self._e_optical_alarm_selection: HmAction = self._get_entity(
            field_name=FIELD_OPTICAL_ALARM_SELECTION, entity_type=HmAction
        )
        self._e_duration: HmAction = self._get_entity(
            field_name=FIELD_DURATION, entity_type=HmAction
        )
        self._e_duration_unit: HmAction = self._get_entity(
            field_name=FIELD_DURATION_UNIT, entity_type=HmAction
        )

    @value_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return (
            self._e_acoustic_alarm_active.value is True
            or self._e_optical_alarm_active.value is True
        )

    @value_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return a list of available tones."""
        return self._e_acoustic_alarm_selection.value_list

    @value_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return a list of available lights."""
        return self._e_optical_alarm_selection.value_list

    @bind_collector
    async def turn_on(
        self,
        acoustic_alarm: str,
        optical_alarm: str,
        duration: int = DEFAULT_DURATION_VALUE,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Turn the device on."""
        await self._e_acoustic_alarm_selection.send_value(
            value=acoustic_alarm, collector=collector
        )
        await self._e_optical_alarm_selection.send_value(value=optical_alarm, collector=collector)
        await self._e_duration_unit.send_value(value=DEFAULT_DURATION_UNIT, collector=collector)
        await self._e_duration.send_value(value=duration, collector=collector)

    @bind_collector
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._e_acoustic_alarm_selection.send_value(
            value=DISABLE_ACOUSTIC_SIGNAL, collector=collector
        )
        await self._e_optical_alarm_selection.send_value(
            value=DISABLE_OPTICAL_SIGNAL, collector=collector
        )
        await self._e_duration_unit.send_value(value=DEFAULT_DURATION_UNIT, collector=collector)
        await self._e_duration.send_value(value=1, collector=collector)


def make_ip_siren(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create HomematicIP siren entities."""
    return hmed.make_custom_entity(
        device=device,
        custom_entity_class=CeIpSiren,
        device_enum=HmEntityDefinition.IP_SIREN,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant
hmed.ALL_DEVICES.append(
    {
        "HmIP-ASIR": CustomConfig(func=make_ip_siren, channels=(0,)),
    }
)
