"""Test support for hahomematic."""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientSession, TCPConnector
import const
import helper
import pydevccu
import pytest

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig

logging.basicConfig(level=logging.INFO)

GOT_DEVICES = False

# pylint: disable=protected-access, redefined-outer-name


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
async def central_unit_mini(
    pydev_ccu_mini: pydevccu.Server, client_session: ClientSession
) -> CentralUnit:
    """Create and yield central."""
    central_unit = await get_pydev_ccu_central_unit_full(client_session, use_caches=True)
    yield central_unit
    await central_unit.stop()


@pytest.fixture
async def central_unit_full(
    pydev_ccu_full: pydevccu.Server, client_session: ClientSession
) -> CentralUnit:
    """Create and yield central."""
    central_unit = await get_pydev_ccu_central_unit_full(client_session, use_caches=False)
    yield central_unit
    await central_unit.stop()


async def get_pydev_ccu_central_unit_full(
    client_session: ClientSession, use_caches: bool
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
            interface="BidCos-RF",
            port=const.CCU_PORT,
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
        client_session=client_session,
        use_caches=use_caches,
    ).create_central()
    central_unit.callback_system_event = systemcallback
    await central_unit.start()
    while not GOT_DEVICES and sleep_counter < 300:
        sleep_counter += 1
        await asyncio.sleep(1)

    return central_unit


@pytest.fixture(name="central_local_factory")
async def central_unit_local_factory(
    client_session: ClientSession,
) -> helper.CentralUnitLocalFactory:
    """Return central factory."""
    return helper.CentralUnitLocalFactory(client_session)
