"""Helpers for tests."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock

from aiohttp import ClientSession
import const

from hahomematic import const as hahomematic_const
from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig, LocalRessources
from hahomematic.device import HmDevice
from hahomematic.entity import CustomEntity, GenericEntity
from hahomematic.helpers import get_device_address


class CentralUnitLocalFactory:
    def __init__(self, client_session: ClientSession):
        self._client_session = client_session

    async def get_central(
        self, address_device_translation: dict[str, str]
    ) -> CentralUnit:
        """Returns a central based on give address_device_translation."""
        interface_configs = {
            InterfaceConfig(
                central_name=const.CENTRAL_NAME,
                interface="Local",
                port=2002,
                local_resources=LocalRessources(
                    address_device_translation=address_device_translation
                ),
            )
        }

        central_unit = await CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs=interface_configs,
            default_callback_port=54321,
            client_session=self._client_session,
        ).get_central()
        await central_unit.start()

        return get_mock(central_unit)


async def get_value_from_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> Any:
    """Return the device value."""
    hm_entity = await get_hm_generic_entity(
        central_unit=central_unit, address=address, parameter=parameter
    )
    assert hm_entity
    await hm_entity.load_entity_value(
        call_source=hahomematic_const.HmCallSource.MANUAL_OR_SCHEDULED
    )
    return get_mock(hm_entity.value)


def get_hm_device(central_unit: CentralUnit, address: str) -> HmDevice | None:
    """Return the hm_device."""
    d_address = get_device_address(address=address)
    return get_mock(central_unit.devices.get(d_address))


async def get_hm_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm generic_entity."""
    hm_device = get_hm_device(central_unit=central_unit, address=address)
    assert hm_device
    hm_entity = hm_device.generic_entities.get((address, parameter))
    assert hm_entity
    return get_mock(hm_entity)


async def get_hm_custom_entity(
    central_unit: CentralUnit, address: str, channel_no: int, do_load: bool = False
) -> CustomEntity | None:
    """Return the hm custom_entity."""
    hm_device = get_hm_device(central_unit, address)
    assert hm_device
    for custom_entity in hm_device.custom_entities.values():
        if custom_entity.channel_no == channel_no:
            if do_load:
                await custom_entity.load_entity_value(
                    call_source=hahomematic_const.HmCallSource.MANUAL_OR_SCHEDULED
                )
            return get_mock(custom_entity)
    return None


def get_mock(instance):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(
            instance._mock_wraps.__dict__  # pylint: disable=protected-access
        )
        return instance

    mock = Mock(spec=instance, wraps=instance)
    mock.__dict__.update(instance.__dict__)
    return mock