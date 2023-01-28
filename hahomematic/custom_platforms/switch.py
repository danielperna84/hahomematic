"""
Module for entities implemented using the switch platform.

See https://www.home-assistant.io/integrations/switch/.
"""
from __future__ import annotations

from typing import Any, cast

from hahomematic.const import HM_ARG_ON_TIME, HmPlatform
from hahomematic.custom_platforms.entity_definition import (
    FIELD_CHANNEL_STATE,
    FIELD_ON_TIME_VALUE,
    FIELD_STATE,
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
from hahomematic.generic_platforms.switch import HmSwitch


class CeSwitch(CustomEntity):
    """Class for HomeMatic switch entities."""

    _attr_platform = HmPlatform.SWITCH

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_state: HmSwitch = self._get_entity(field_name=FIELD_STATE, entity_type=HmSwitch)
        self._e_on_time_value: HmAction = self._get_entity(
            field_name=FIELD_ON_TIME_VALUE, entity_type=HmAction
        )
        self._e_channel_state: HmBinarySensor = self._get_entity(
            field_name=FIELD_CHANNEL_STATE, entity_type=HmBinarySensor
        )

    @property
    def channel_value(self) -> bool | None:
        """Return the current channel value of the switch."""
        return self._e_channel_state.value

    @value_property
    def value(self) -> bool | None:
        """Return the current value of the switch."""
        return self._e_state.value

    @bind_collector
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: dict[str, Any] | None
    ) -> None:
        """Turn the switch on."""
        if HM_ARG_ON_TIME in kwargs and isinstance(self._e_on_time_value, HmAction):
            on_time: float = float(cast(float, kwargs[HM_ARG_ON_TIME]))
            await self._e_on_time_value.send_value(value=on_time, collector=collector)

        await self._e_state.turn_on(collector=collector, **kwargs)

    async def turn_off(self, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        await self._e_state.turn_off(collector=collector)

    async def set_on_time_value(
        self, on_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the on time value in seconds."""
        await self._e_on_time_value.send_value(value=float(on_time), collector=collector)


def make_ip_switch(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Create HomematicIP switch entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeSwitch,
        device_enum=EntityDefinition.IP_SWITCH,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_rf_switch(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Create HomematicIP switch entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeSwitch,
        device_enum=EntityDefinition.RF_SWITCH,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant
DEVICES: dict[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ELV-SH-BS2": CustomConfig(func=make_ip_switch, channels=(3, 7)),
    "HmIP-BS2": CustomConfig(func=make_ip_switch, channels=(3, 7)),
    "HmIP-BSL": CustomConfig(func=make_ip_switch, channels=(3,)),
    "HmIP-BSM": CustomConfig(func=make_ip_switch, channels=(3,)),
    "HmIP-DRSI1": CustomConfig(
        func=make_ip_switch,
        channels=(2,),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ACTUAL_TEMPERATURE",),
            }
        ),
    ),
    "HmIP-DRSI4": CustomConfig(
        func=make_ip_switch,
        channels=(5, 9, 13, 17),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ACTUAL_TEMPERATURE",),
            }
        ),
    ),
    "HmIP-FSI": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-FSM": CustomConfig(func=make_ip_switch, channels=(1,)),
    "HmIP-MOD-OC8": CustomConfig(func=make_ip_switch, channels=(9, 13, 17, 21, 25, 29, 33, 37)),
    "HmIP-PCBS": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-PCBS-BAT": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-PCBS2": CustomConfig(func=make_ip_switch, channels=(3, 7)),
    "HmIP-PS": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-SCTH230": CustomConfig(func=make_ip_switch, channels=(7,)),
    "HmIP-USBSM": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-WGC": CustomConfig(func=make_ip_switch, channels=(2,)),
    "HmIP-WHS2": CustomConfig(func=make_ip_switch, channels=(1, 5)),
    "HmIPW-DRS": CustomConfig(
        func=make_ip_switch,
        channels=(1, 5, 9, 13, 17, 21, 25, 29),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ACTUAL_TEMPERATURE",),
            }
        ),
    ),
    "HmIPW-FIO6": CustomConfig(func=make_ip_switch, channels=(7, 11, 15, 19, 23, 27)),
    # "HM-LC-Sw": CustomEntityConfig(make_rf_switch, group_base_channels=(1, 2, 3, 4)),
    # "HM-ES-PM": CustomEntityConfig(make_rf_switch, group_base_channels=(1,))),
}

# Devices are better supported without custom entities:
# HmIP-MIO16-PCB : Don't add it. Too much functionality.
# HmIP-MIOB : Don't add it. Too much functionality.

BLACKLISTED_DEVICES: tuple[str, ...] = ()
