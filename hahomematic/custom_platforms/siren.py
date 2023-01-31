"""
Module for entities implemented using the siren platform.

See https://www.home-assistant.io/integrations/siren/.
"""
from __future__ import annotations

from abc import abstractmethod

from hahomematic.const import HmPlatform
from hahomematic.custom_platforms.entity_definition import (
    FIELD_ACOUSTIC_ALARM_ACTIVE,
    FIELD_ACOUSTIC_ALARM_SELECTION,
    FIELD_DURATION,
    FIELD_DURATION_UNIT,
    FIELD_OPTICAL_ALARM_ACTIVE,
    FIELD_OPTICAL_ALARM_SELECTION,
    CustomConfig,
    EntityDefinition,
    ExtendedConfig,
    make_custom_entity,
)
from hahomematic.decorators import bind_collector, value_property
import hahomematic.device as hmd
import hahomematic.entity as hme
from hahomematic.entity import CallParameterCollector, CustomEntity
from hahomematic.generic_platforms.action import HmAction
from hahomematic.generic_platforms.binary_sensor import HmBinarySensor

# HM constants
HMIP_ACOUSTIC_ALARM_SELECTION = "ACOUSTIC_ALARM_SELECTION"
HMIP_OPTICAL_ALARM_SELECTION = "OPTICAL_ALARM_SELECTION"
HMIP_DURATION_UNIT = "DURATION_UNIT"
HMIP_DURATION_VALUE = "DURATION_VALUE"

DEFAULT_ACOUSTIC_ALARM_SELECTION = "FREQUENCY_RISING_AND_FALLING"
DEFAULT_OPTICAL_ALARM_SELECTION = "BLINKING_ALTERNATELY_REPEATING"
DISABLE_ACOUSTIC_SIGNAL = "DISABLE_ACOUSTIC_SIGNAL"
DISABLE_OPTICAL_SIGNAL = "DISABLE_OPTICAL_SIGNAL"
DEFAULT_DURATION_UNIT = "S"
DEFAULT_DURATION_VALUE = 60


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
    async def turn_on(self, acoustic_alarm: str, optical_alarm: str, duration: int) -> None:
        """Turn the device on."""

    @abstractmethod
    async def turn_off(self) -> None:
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
) -> tuple[hme.BaseEntity, ...]:
    """Create HomematicIP siren entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeIpSiren,
        device_enum=EntityDefinition.IP_SIREN,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant
DEVICES: dict[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HmIP-ASIR": CustomConfig(func=make_ip_siren, channels=(0,)),
}

BLACKLISTED_DEVICES: tuple[str, ...] = ()
