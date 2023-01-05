"""Helpers for tests."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession
import const

from hahomematic import const as hahomematic_const
from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import Client, InterfaceConfig, LocalRessources, _ClientConfig
from hahomematic.device import HmDevice
from hahomematic.entity import CustomEntity, GenericEntity, GenericSystemVariable
from hahomematic.generic_platforms.button import HmProgramButton
from hahomematic.helpers import ProgramData, SystemVariableData, get_device_address


class CentralUnitLocalFactory:
    """Factory for a central_unit with one local client."""

    def __init__(self, client_session: ClientSession):
        self._client_session = client_session

    async def get_central(
        self,
        address_device_translation: dict[str, str],
        add_sysvars: bool = False,
        add_programs: bool = False,
    ) -> tuple[CentralUnit, Mock]:
        """Returns a central based on give address_device_translation."""
        sysvar_data: list[SystemVariableData] = const.SYSVAR_DATA if add_sysvars else []
        program_data: list[ProgramData] = const.PROGRAM_DATA if add_programs else []

        local_client_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface="Local",
            port=2002,
            local_resources=LocalRessources(
                address_device_translation=address_device_translation
            ),
        )

        central_unit = await CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs={local_client_config},
            default_callback_port=54321,
            client_session=self._client_session,
        ).get_central()

        mock_client = get_mock(
            await _ClientConfig(
                central=central_unit,
                interface_config=local_client_config,
                local_ip="127.0.0.1",
            ).get_client()
        )

        with patch(
            "hahomematic.client.create_client",
            return_value=mock_client,
        ), patch(
            "hahomematic.client.ClientLocal.get_all_system_variables",
            return_value=sysvar_data,
        ), patch(
            "hahomematic.client.ClientLocal.get_all_programs",
            return_value=program_data,
        ):
            await central_unit.start()
        return central_unit, mock_client


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
    return hm_entity.value


def get_hm_device(central_unit: CentralUnit, address: str) -> HmDevice | None:
    """Return the hm_device."""
    d_address = get_device_address(address=address)
    return central_unit.devices.get(d_address)


async def get_hm_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm generic_entity."""
    hm_device = get_hm_device(central_unit=central_unit, address=address)
    assert hm_device
    hm_entity = hm_device.generic_entities.get((address, parameter))
    assert hm_entity
    return hm_entity


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
            return custom_entity
    return None


async def get_hm_sysvar_entity(
    central_unit: CentralUnit, name: str
) -> GenericSystemVariable | None:
    """Return the sysvar entity."""
    sysvar_entity = central_unit.sysvar_entities.get(name)
    assert sysvar_entity
    return sysvar_entity


async def get_hm_program_button(
    central_unit: CentralUnit, pid: str
) -> HmProgramButton | None:
    """Return the program button."""
    program_button = central_unit.program_entities.get(pid)
    assert program_button
    return program_button


def get_mock(instance):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(
            instance._mock_wraps.__dict__  # pylint: disable=protected-access
        )
        return instance

    mock = MagicMock(spec=instance, wraps=instance)
    mock.__dict__.update(instance.__dict__)
    return mock
