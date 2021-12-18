import asyncio
import logging

import pydevccu
import pytest

from hahomematic import config, const
from hahomematic.central_unit import CentralConfig
from hahomematic.client import ClientConfig
from hahomematic.xml_rpc_server import register_xml_rpc_server

logging.basicConfig(level=logging.DEBUG)
CCU_HOST = "127.0.0.1"
CCU_USERNAME = None
CCU_PASSWORD = None
got_devices = False

# content of conftest.py
def pytest_configure(config):
    import sys

    sys._called_from_test = True


def pytest_unconfigure(config):  # pragma: no cover
    import sys  # This was missing from the manual

    del sys._called_from_test


@pytest.fixture
async def pydev_ccu(loop):
    """Defines the virtual ccu"""
    ccu = pydevccu.Server(persistance=True, logic={"startupdelay": 1, "interval": 30})
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
async def central(loop, pydev_ccu):
    """Yield central"""
    SLEEPCOUNTER = 0

    def systemcallback(self, src, *args):
        if args and args[0] and len(args[0]) > 0:
            global got_devices
            got_devices = True

    central = CentralConfig(
        name="ccu-dev",
        entry_id="123",
        loop=loop,
        xml_rpc_server=register_xml_rpc_server(),
        host=CCU_HOST,
        username=CCU_USERNAME,
        password=CCU_PASSWORD,
        enable_virtual_channels=True,
    ).get_central()
    config.INIT_TIMEOUT = 10
    config.CACHE_DIR = "cache"
    central.callback_system_event = systemcallback
    client1 = await ClientConfig(
        central=central,
        name="hm",
        port=2001,
    ).get_client()

    # Clients have to exist prior to creating the devices
    central.create_devices()
    # Once the central_1 is running we subscribe to receive messages.
    await client1.proxy_init()
    await central.init_hub()
    while not got_devices and SLEEPCOUNTER < 300:
        print("Waiting for devices")
        SLEEPCOUNTER += 1
        await asyncio.sleep(1)

    yield central

    await central.stop()


@pytest.yield_fixture(scope="session")
def loop(request):
    """Yield running event_loop"""
    event_loop = asyncio.get_event_loop_policy().new_event_loop()
    yield event_loop
    event_loop.close()
