"""
Module for entities implemented using the siren platform.

See https://www.home-assistant.io/integrations/siren/.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Final, TypedDict, Unpack

from hahomematic.const import HmPlatform
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic import HmAction, HmBinarySensor, HmSensor

_SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF: Final = "IDLE_OFF"


class _SirenCommand(StrEnum):
    """Enum with siren commands."""

    OFF = "INTRUSION_ALARM_OFF"
    ON = "INTRUSION_ALARM"


class SirenOnArgs(TypedDict, total=False):
    """Matcher for the siren arguments."""

    acoustic_alarm: str
    optical_alarm: str
    duration: str


class BaseSiren(CustomEntity):
    """Class for HomeMatic siren entities."""

    _platform = HmPlatform.SIREN

    @state_property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if siren is on."""

    @state_property
    @abstractmethod
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""

    @state_property
    @abstractmethod
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""

    @property
    @abstractmethod
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""

    @property
    def supports_tones(self) -> bool:
        """Flag if siren supports tones."""
        return self.available_tones is not None

    @property
    def supports_lights(self) -> bool:
        """Flag if siren supports lights."""
        return self.available_lights is not None

    @abstractmethod
    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""

    @abstractmethod
    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""


class CeIpSiren(BaseSiren):
    """Class for HomematicIP siren entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_acoustic_alarm_active: HmBinarySensor = self._get_entity(
            field=Field.ACOUSTIC_ALARM_ACTIVE, entity_type=HmBinarySensor
        )
        self._e_acoustic_alarm_selection: HmAction = self._get_entity(
            field=Field.ACOUSTIC_ALARM_SELECTION, entity_type=HmAction
        )
        self._e_optical_alarm_active: HmBinarySensor = self._get_entity(
            field=Field.OPTICAL_ALARM_ACTIVE, entity_type=HmBinarySensor
        )
        self._e_optical_alarm_selection: HmAction = self._get_entity(
            field=Field.OPTICAL_ALARM_SELECTION, entity_type=HmAction
        )
        self._e_duration: HmAction = self._get_entity(field=Field.DURATION, entity_type=HmAction)
        self._e_duration_unit: HmAction = self._get_entity(
            field=Field.DURATION_UNIT, entity_type=HmAction
        )

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return (
            self._e_acoustic_alarm_active.value is True
            or self._e_optical_alarm_active.value is True
        )

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return self._e_acoustic_alarm_selection.values

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return self._e_optical_alarm_selection.values

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return True

    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""

        acoustic_alarm = kwargs.get("acoustic_alarm", self._e_acoustic_alarm_selection.default)
        if self.available_tones and acoustic_alarm and acoustic_alarm not in self.available_tones:
            raise ValueError(
                f"Invalid tone specified for entity {self.full_name}: {acoustic_alarm}, "
                "check the available_tones attribute for valid tones to pass in"
            )

        optical_alarm = kwargs.get("optical_alarm", self._e_optical_alarm_selection.default)
        if self.available_lights and optical_alarm and optical_alarm not in self.available_lights:
            raise ValueError(
                f"Invalid light specified for entity {self.full_name}: {optical_alarm}, "
                "check the available_lights attribute for valid tones to pass in"
            )

        await self._e_acoustic_alarm_selection.send_value(
            value=acoustic_alarm, collector=collector
        )
        await self._e_optical_alarm_selection.send_value(value=optical_alarm, collector=collector)
        await self._e_duration_unit.send_value(
            value=self._e_duration_unit.default, collector=collector
        )
        duration = kwargs.get("duration", self._e_duration.default)
        await self._e_duration.send_value(value=duration, collector=collector)

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._e_acoustic_alarm_selection.send_value(
            value=self._e_acoustic_alarm_selection.default, collector=collector
        )
        await self._e_optical_alarm_selection.send_value(
            value=self._e_optical_alarm_selection.default, collector=collector
        )
        await self._e_duration_unit.send_value(
            value=self._e_duration_unit.default, collector=collector
        )
        await self._e_duration.send_value(value=self._e_duration.default, collector=collector)


class CeIpSirenSmoke(BaseSiren):
    """Class for HomematicIP siren smoke entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_smoke_detector_alarm_status: HmSensor[str | None] = self._get_entity(
            field=Field.SMOKE_DETECTOR_ALARM_STATUS, entity_type=HmSensor[str | None]
        )
        self._e_smoke_detector_command: HmAction = self._get_entity(
            field=Field.SMOKE_DETECTOR_COMMAND, entity_type=HmAction
        )

    @state_property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        if not self._e_smoke_detector_alarm_status.value:
            return False
        return bool(
            self._e_smoke_detector_alarm_status.value != _SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF
        )

    @state_property
    def available_tones(self) -> tuple[str, ...] | None:
        """Return available tones."""
        return None

    @state_property
    def available_lights(self) -> tuple[str, ...] | None:
        """Return available lights."""
        return None

    @property
    def supports_duration(self) -> bool:
        """Flag if siren supports duration."""
        return False

    @bind_collector()
    async def turn_on(
        self,
        collector: CallParameterCollector | None = None,
        **kwargs: Unpack[SirenOnArgs],
    ) -> None:
        """Turn the device on."""
        await self._e_smoke_detector_command.send_value(
            value=_SirenCommand.ON, collector=collector
        )

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the device off."""
        await self._e_smoke_detector_command.send_value(
            value=_SirenCommand.OFF, collector=collector
        )


def make_ip_siren(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP siren entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpSiren,
        device_profile=DeviceProfile.IP_SIREN,
        custom_config=custom_config,
    )


def make_ip_siren_smoke(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP siren entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpSirenSmoke,
        device_profile=DeviceProfile.IP_SIREN_SMOKE,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HmIP-ASIR": CustomConfig(make_ce_func=make_ip_siren, channels=(3,)),
    "HmIP-SWSD": CustomConfig(make_ce_func=make_ip_siren_smoke),
}
hmed.ALL_DEVICES[HmPlatform.SIREN] = DEVICES
