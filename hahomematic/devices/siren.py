"""Code to create the required entities for siren devices."""

from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any, cast

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_ACOUSTIC_ALARM_ACTIVE,
    FIELD_ACOUSTIC_ALARM_SELECTION,
    FIELD_OPTICAL_ALARM_ACTIVE,
    FIELD_OPTICAL_ALARM_SELECTION,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.binary_sensor import HmBinarySensor

_LOGGER = logging.getLogger(__name__)

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
    """Class for homematic siren entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int, set[str]],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.SIREN,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HMSiren.__init__(%s, %s, %s)",
            self.device.interface_id,
            self.device.device_address,
            unique_id,
        )

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if siren is on."""

    @property
    @abstractmethod
    def available_tones(self) -> list[str] | None:
        """Return a list of available tones."""

    @property
    @abstractmethod
    def available_lights(self) -> list[str] | None:
        """Return a list of available lights."""

    @abstractmethod
    async def turn_on(
        self, acoustic_alarm: str, optical_alarm: str, duration: int
    ) -> None:
        """Turn the device on."""

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the device off."""


class CeIpSiren(BaseSiren):
    """Class for homematic ip siren entities."""

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

    @property
    def is_on(self) -> bool:
        """Return true if siren is on."""
        return (
            self._e_acoustic_alarm_active.value is True
            or self._e_optical_alarm_active.value is True
        )

    @property
    def available_tones(self) -> list[str] | None:
        """Return a list of available tones."""
        return cast(list[str], self._e_acoustic_alarm_selection.value_list)

    @property
    def available_lights(self) -> list[str] | None:
        """Return a list of available lights."""
        return cast(list[str], self._e_optical_alarm_selection.value_list)

    async def turn_on(
        self,
        acoustic_alarm: str,
        optical_alarm: str,
        duration: int = DEFAULT_DURATION_VALUE,
    ) -> None:
        """Turn the device on."""
        await self._client.put_paramset(
            address=f"{self.device_address}:3",
            paramset_key="VALUES",
            value={
                HMIP_ACOUSTIC_ALARM_SELECTION: acoustic_alarm,
                HMIP_OPTICAL_ALARM_SELECTION: optical_alarm,
                HMIP_DURATION_UNIT: DEFAULT_DURATION_UNIT,
                HMIP_DURATION_VALUE: duration,
            },
        )

    async def turn_off(self) -> None:
        """Turn the device off."""
        await self._client.put_paramset(
            address=f"{self.device_address}:3",
            paramset_key="VALUES",
            value={
                HMIP_ACOUSTIC_ALARM_SELECTION: DISABLE_ACOUSTIC_SIGNAL,
                HMIP_OPTICAL_ALARM_SELECTION: DISABLE_OPTICAL_SIGNAL,
                HMIP_DURATION_UNIT: DEFAULT_DURATION_UNIT,
                HMIP_DURATION_VALUE: 1,
            },
        )


class CeRfSiren(BaseSiren):
    """Class for classic homematic siren entities."""

    async def turn_on(
        self, acoustic_alarm: str, optical_alarm: str, duration: int
    ) -> None:
        """Turn the device on."""

    async def turn_off(self) -> None:
        """Turn the device off."""


def make_ip_siren(
    device: hm_device.HmDevice, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip siren entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeIpSiren,
        device_enum=EntityDefinition.IP_SIREN,
        group_base_channels=group_base_channels,
    )


def make_rf_siren(
    device: hm_device.HmDevice, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic rf siren entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeRfSiren,
        device_enum=EntityDefinition.RF_SIREN,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-ASIR": (make_ip_siren, [0]),
}

BLACKLISTED_DEVICES: list[str] = []
