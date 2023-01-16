from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientSession, TCPConnector
import const
import helper
import pydevccu
import pytest

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig

logging.basicConfig(level=logging.INFO)

GOT_DEVICES = False


@pytest.fixture(name="ccu")
def pydev_ccu() -> pydevccu.Server:
    """Defines the virtual ccu"""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT))
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
async def client_session() -> ClientSession:
    """ClientSession for json client."""
    client_session = ClientSession(connector=TCPConnector(limit=3))
    yield client_session
    if not client_session.closed:
        await client_session.close()


@pytest.fixture(name="central_pydevccu")
async def central_unit(
    ccu: pydevccu.Server, client_session: ClientSession
) -> CentralUnit:
    """Yield central"""
    sleep_counter = 0
    global GOT_DEVICES
    GOT_DEVICES = False

    def systemcallback(src, *args):
        if src == "devicesCreated" and args and args[0] and len(args[0]) > 0:
            global GOT_DEVICES
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
        use_caches=False,
    ).create_central()
    central_unit.callback_system_event = systemcallback
    await central_unit.start()
    while not GOT_DEVICES and sleep_counter < 300:
        print("Waiting for devices")
        sleep_counter += 1
        await asyncio.sleep(1)

    yield central_unit

    await central_unit.stop()


@pytest.fixture(name="central_local_factory")
async def central_unit_local_factory(
    client_session: ClientSession,
) -> helper.CentralUnitLocalFactory:
    """Return central factory"""
    return helper.CentralUnitLocalFactory(client_session)
