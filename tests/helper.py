"""Helpers for tests."""
from __future__ import annotations

import importlib.resources
import json
import logging
import os
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession
import const

from hahomematic import const as hahomematic_const
from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import Client, InterfaceConfig, LocalRessources, _ClientConfig
from hahomematic.helpers import get_device_address
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub.button import HmProgramButton
from hahomematic.platforms.hub.entity import GenericSystemVariable

_LOGGER = logging.getLogger(__name__)

# pylint: disable=protected-access


class CentralUnitLocalFactory:
    """Factory for a central_unit with one local client."""

    def __init__(self, client_session: ClientSession):
        """Init the central factory."""
        self._client_session = client_session
        self.system_event_mock = MagicMock()
        self.entity_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_raw_central(
        self,
        interface_config: InterfaceConfig | None,
        un_ignore_list: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = {interface_config} if interface_config else {}
        central = await CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs=interface_configs,
            default_callback_port=54321,
            client_session=self._client_session,
            load_un_ignore=un_ignore_list is not None,
            un_ignore_list=un_ignore_list,
        ).create_central()

        central.callback_system_event = self.system_event_mock
        central.callback_entity_event = self.entity_event_mock
        central.callback_ha_event = self.ha_event_mock

        return central

    async def get_unpatched_default_central(
        self,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        interface_config = get_local_client_interface_config(
            address_device_translation=address_device_translation,
            ignore_devices_on_create=ignore_devices_on_create,
        )
        central = await self.get_raw_central(
            interface_config=interface_config, un_ignore_list=un_ignore_list
        )
        client = await get_client(
            central=central,
            interface_config=interface_config,
            do_mock_client=do_mock_client,
            ignore_devices_on_create=ignore_devices_on_create if ignore_devices_on_create else [],
        )

        assert central
        assert client
        return central, client

    async def get_default_central(
        self,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        add_sysvars: bool = False,
        add_programs: bool = False,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        central, client = await self.get_unpatched_default_central(
            address_device_translation=address_device_translation,
            do_mock_client=do_mock_client,
            ignore_devices_on_create=ignore_devices_on_create,
            un_ignore_list=un_ignore_list,
        )

        with patch(
            "hahomematic.client.create_client",
            return_value=client,
        ), patch(
            "hahomematic.client.ClientLocal.get_all_system_variables",
            return_value=const.SYSVAR_DATA if add_sysvars else [],
        ), patch(
            "hahomematic.client.ClientLocal.get_all_programs",
            return_value=const.PROGRAM_DATA if add_programs else [],
        ):
            await central.start()

        assert central
        assert client
        return central, client


def get_local_client_interface_config(
    address_device_translation: dict[str, str],
    ignore_devices_on_create: list[str] | None = None,
) -> InterfaceConfig:
    """Return a central based on give address_device_translation."""
    _ignore_devices_on_create: list[str] = (
        ignore_devices_on_create if ignore_devices_on_create else []
    )

    return InterfaceConfig(
        central_name=const.CENTRAL_NAME,
        interface="Local",
        port=2002,
        local_resources=LocalRessources(
            address_device_translation=address_device_translation,
            ignore_devices_on_create=_ignore_devices_on_create,
        ),
    )


async def get_client(
    central: CentralUnit,
    interface_config: InterfaceConfig,
    do_mock_client: bool = True,
    ignore_devices_on_create: list[str] | None = None,
) -> Client | Mock:
    """Return a central based on give address_device_translation."""
    _client = await _ClientConfig(
        central=central,
        interface_config=interface_config,
        local_ip="127.0.0.1",
    ).get_client()
    _mock_client = get_mock(_client)
    client = _mock_client if do_mock_client else _client

    assert client
    return client


async def get_value_from_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> Any:
    """Return the device value."""
    entity = await get_generic_entity(
        central_unit=central_unit, address=address, parameter=parameter
    )
    assert entity
    await entity.load_entity_value(call_source=hahomematic_const.HmCallSource.MANUAL_OR_SCHEDULED)
    return entity.value


def get_device(central_unit: CentralUnit, address: str) -> HmDevice | None:
    """Return the device."""
    d_address = get_device_address(address=address)
    device = central_unit.get_device(device_address=d_address)
    assert device
    return device


async def get_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm generic_entity."""
    device = get_device(central_unit=central_unit, address=address)
    entity = device.generic_entities.get((address, parameter))
    assert entity
    return entity


async def get_wrapper_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm wrapper_entity."""
    device = get_device(central_unit=central_unit, address=address)
    entity = device.wrapper_entities.get((address, parameter))
    assert entity
    return entity


async def get_event(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm event."""
    device = get_device(central_unit=central_unit, address=address)
    event = device.events.get((address, parameter))
    assert event
    return event


async def get_custom_entity(
    central_unit: CentralUnit, address: str, channel_no: int, do_load: bool = False
) -> CustomEntity | None:
    """Return the hm custom_entity."""
    device = get_device(central_unit, address)
    for custom_entity in device.custom_entities.values():
        if custom_entity.channel_no == channel_no:
            if do_load:
                await custom_entity.load_entity_value(
                    call_source=hahomematic_const.HmCallSource.MANUAL_OR_SCHEDULED
                )

            for data_entities in custom_entity.data_entities.values():
                data_entities._attr_state_uncertain = False
            return custom_entity
    return None


async def get_sysvar_entity(central: CentralUnit, name: str) -> GenericSystemVariable | None:
    """Return the sysvar entity."""
    entity = central.sysvar_entities.get(name)
    assert entity
    return entity


async def get_program_button(central: CentralUnit, pid: str) -> HmProgramButton | None:
    """Return the program button."""
    entity = central.program_entities.get(pid)
    assert entity
    return entity


def load_device_description(central: CentralUnit, filename: str) -> Any:
    """Load device description."""
    dev_desc = _load_json_file(
        package="pydevccu", resource="device_descriptions", filename=filename
    )
    assert dev_desc
    return dev_desc


def get_mock(instance, **kwargs):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)
        return instance

    mock = MagicMock(spec=instance, wraps=instance, **kwargs)
    mock.__dict__.update(instance.__dict__)
    return mock


def _load_json_file(package: str, resource: str, filename: str) -> Any | None:
    """Load json file from disk into dict."""
    package_path = str(importlib.resources.files(package=package))
    with open(
        file=os.path.join(package_path, resource, filename),
        encoding=hahomematic_const.DEFAULT_ENCODING,
    ) as fptr:
        return json.load(fptr)
