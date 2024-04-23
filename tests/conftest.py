"""Test support for hahomematic."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

from aiohttp import ClientSession, TCPConnector
import pydevccu
import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client

from tests import const, helper

logging.basicConfig(level=logging.INFO)

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


@pytest.fixture
def pydev_ccu_full() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT))
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
def pydev_ccu_mini() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT), devices=["HmIP-BWTH"])
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
async def client_session() -> ClientSession:
    """Create ClientSession for json client."""
    session = ClientSession(connector=TCPConnector(limit=3))
    yield session
    if not session.closed:
        await session.close()


@pytest.fixture
async def central_unit_mini(pydev_ccu_mini: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""
    central = await helper.get_pydev_ccu_central_unit_full(client_session=None)
    yield central
    await central.stop()
    await central.clear_caches()


@pytest.fixture
async def central_unit_full(pydev_ccu_full: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""

    def ha_event_callback(*args, **kwargs):
        """Do dummy ha_event_callback."""

    def system_event_callback(*args, **kwargs):
        """Do dummy system_event_callback."""

    central = await helper.get_pydev_ccu_central_unit_full(
        client_session=None,
    )

    unregister_ha_event_callback = central.register_ha_event_callback(ha_event_callback)
    unregister_system_event_callback = central.register_system_event_callback(
        system_event_callback
    )

    yield central

    unregister_ha_event_callback()
    unregister_system_event_callback()
    await central.stop()
    await central.clear_caches()


@pytest.fixture
async def factory() -> helper.Factory:
    """Return central factory."""
    return helper.Factory(client_session=None)


@pytest.fixture
async def central_client(
    address_device_translation: dict[str, str],
    do_mock_client: bool,
    add_sysvars: bool,
    add_programs: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> tuple[CentralUnit, Client | Mock]:
    """Return central factory."""
    factory = helper.Factory(client_session=None)
    central_client = await factory.get_default_central(
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        add_sysvars=add_sysvars,
        add_programs=add_programs,
        ignore_devices_on_create=ignore_devices_on_create,
        un_ignore_list=un_ignore_list,
    )
    yield central_client
    central, _ = central_client
    await central.stop()
