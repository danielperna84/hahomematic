"""
Module for entities implemented using the switch platform.

See https://www.home-assistant.io/integrations/switch/.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
import logging
from typing import Any, Final

from hahomematic.const import HmPlatform, Parameter
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic import HmAction, HmBinarySensor, HmSwitch
from hahomematic.platforms.support import OnTimeMixin

_LOGGER: Final = logging.getLogger(__name__)


class _SwitchStateChangeArg(StrEnum):
    """Enum with switch state change arguments."""

    OFF = "off"
    ON = "on"
    ON_TIME = "on_time"


class CeSwitch(CustomEntity, OnTimeMixin):
    """Class for HomeMatic switch entities."""

    _platform = HmPlatform.SWITCH

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        OnTimeMixin.__init__(self)
        super()._init_entity_fields()
        self._e_state: HmSwitch = self._get_entity(field=Field.STATE, entity_type=HmSwitch)
        self._e_on_time_value: HmAction = self._get_entity(
            field=Field.ON_TIME_VALUE, entity_type=HmAction
        )
        self._e_channel_state: HmBinarySensor = self._get_entity(
            field=Field.CHANNEL_STATE, entity_type=HmBinarySensor
        )

    @property
    def channel_value(self) -> bool | None:
        """Return the current channel value of the switch."""
        return self._e_channel_state.value

    @state_property
    def value(self) -> bool | None:
        """Return the current value of the switch."""
        return self._e_state.value

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, on_time: float | None = None
    ) -> None:
        """Turn the switch on."""
        if not self.is_state_change(on=True, on_time=on_time):
            return
        if on_time is not None or (on_time := self.get_on_time_and_cleanup()):
            await self._e_on_time_value.send_value(value=float(on_time), collector=collector)
        await self._e_state.turn_on(collector=collector)

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        if not self.is_state_change(off=True):
            return
        await self._e_state.turn_off(collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_SwitchStateChangeArg.ON_TIME) is not None:
            return True
        if kwargs.get(_SwitchStateChangeArg.ON) is not None and self.value is not True:
            return True
        if kwargs.get(_SwitchStateChangeArg.OFF) is not None and self.value is not False:
            return True
        return super().is_state_change(**kwargs)


def make_ip_switch(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP switch entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeSwitch,
        device_profile=DeviceProfile.IP_SWITCH,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ELV-SH-BS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "HmIP-BS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "HmIP-BSL": CustomConfig(make_ce_func=make_ip_switch, channels=(4,)),
    "HmIP-BSM": CustomConfig(make_ce_func=make_ip_switch, channels=(4,)),
    "HmIP-DRSI1": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(3,),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIP-DRSI4": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(6, 10, 14, 18),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIP-FSI": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-FSM": CustomConfig(make_ce_func=make_ip_switch, channels=(2,)),
    "HmIP-MOD-OC8": CustomConfig(
        make_ce_func=make_ip_switch, channels=(10, 14, 18, 22, 26, 30, 34, 38)
    ),
    "HmIP-PCBS": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-PCBS-BAT": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-PCBS2": CustomConfig(make_ce_func=make_ip_switch, channels=(4, 8)),
    "HmIP-PS": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-SCTH230": CustomConfig(make_ce_func=make_ip_switch, channels=(8,)),
    "HmIP-USBSM": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-WGC": CustomConfig(make_ce_func=make_ip_switch, channels=(3,)),
    "HmIP-WHS2": CustomConfig(make_ce_func=make_ip_switch, channels=(2, 6)),
    "HmIPW-DRS": CustomConfig(
        make_ce_func=make_ip_switch,
        channels=(2, 6, 10, 14, 18, 22, 26, 30),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIPW-FIO6": CustomConfig(make_ce_func=make_ip_switch, channels=(8, 12, 16, 20, 24, 28)),
}
hmed.ALL_DEVICES[HmPlatform.SWITCH] = DEVICES
