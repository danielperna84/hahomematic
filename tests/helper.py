"""Helpers for tests."""
from __future__ import annotations

import asyncio
import importlib.resources
import logging
import os
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession
import orjson

from hahomematic import const as hahomematic_const
from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import Client, InterfaceConfig, _ClientConfig
from hahomematic.const import HmInterface
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic_support.client_local import ClientLocal, LocalRessources

from tests import const

_LOGGER = logging.getLogger(__name__)

GOT_DEVICES = False

# pylint: disable=protected-access


class Factory:
    """Factory for a central_unit with one local client."""

    def __init__(self, client_session: ClientSession | None):
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
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs=set(interface_configs),
            default_callback_port=54321,
            client_session=self._client_session,
            load_un_ignore=un_ignore_list is not None,
            un_ignore_list=un_ignore_list,
            start_direct=True,
        ).create_central()

        central.register_system_event_callback(self.system_event_mock)
        central.register_entity_event_callback(self.entity_event_mock)
        central.register_ha_event_callback(self.ha_event_mock)

        return central

    async def get_unpatched_default_central(
        self,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        interface_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=hahomematic_const.HmInterface.HM,
            port=2002,
        )

        central = await self.get_raw_central(
            interface_config=interface_config,
            un_ignore_list=un_ignore_list,
        )

        _client = ClientLocal(
            client_config=_ClientConfig(
                central=central,
                interface_config=interface_config,
                local_ip="127.0.0.1",
            ),
            local_resources=LocalRessources(
                address_device_translation=address_device_translation,
                ignore_devices_on_create=ignore_devices_on_create
                if ignore_devices_on_create
                else [],
            ),
        )
        await _client.init_client()
        client = get_mock(_client) if do_mock_client else _client

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

        patch(
            "hahomematic.central_unit.CentralUnit._get_primary_client", return_value=client
        ).start()
        patch("hahomematic.client._ClientConfig.get_client", return_value=client).start()
        patch(
            "hahomematic_support.client_local.ClientLocal.get_all_system_variables",
            return_value=const.SYSVAR_DATA if add_sysvars else [],
        ).start()
        patch(
            "hahomematic_support.client_local.ClientLocal.get_all_programs",
            return_value=const.PROGRAM_DATA if add_programs else [],
        ).start()
        patch(
            "hahomematic.central_unit.CentralUnit._identify_callback_ip", return_value="127.0.0.1"
        ).start()

        await central.start()
        await central._create_devices()
        await central._init_hub()

        assert central
        assert client
        return central, client


def get_prepared_custom_entity(
    central_unit: CentralUnit, address: str, channel_no: int | None
) -> CustomEntity | None:
    """Return the hm custom_entity."""
    if custom_entity := central_unit.get_custom_entity(address=address, channel_no=channel_no):
        for data_entity in custom_entity.data_entities.values():
            data_entity._attr_state_uncertain = False
        return custom_entity
    return None


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
        return orjson.loads(fptr.read())


async def get_pydev_ccu_central_unit_full(
    client_session: ClientSession | None, use_caches: bool
) -> CentralUnit:
    """Create and yield central."""
    sleep_counter = 0
    global GOT_DEVICES  # pylint: disable=global-statement
    GOT_DEVICES = False

    def systemcallback(name, *args, **kwargs):
        if (
            name == "devicesCreated"
            and kwargs
            and kwargs.get("new_devices")
            and len(kwargs["new_devices"]) > 0
        ):
            global GOT_DEVICES  # pylint: disable=global-statement
            GOT_DEVICES = True

    interface_configs = {
        InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=HmInterface.HM,
            port=const.CCU_PORT,
        )
    }

    central_unit = CentralConfig(
        name=const.CENTRAL_NAME,
        host=const.CCU_HOST,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
        central_id="test1234",
        storage_folder="homematicip_local",
        interface_configs=interface_configs,
        default_callback_port=54321,
        client_session=client_session,
        use_caches=use_caches,
    ).create_central()
    central_unit.register_system_event_callback(systemcallback)
    await central_unit.start()
    while not GOT_DEVICES and sleep_counter < 300:
        sleep_counter += 1
        await asyncio.sleep(1)

    return central_unit
