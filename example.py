"""Example for hahomematic."""
# !/usr/bin/python3
import asyncio
import logging
import sys

from aiohttp import ClientSession, TCPConnector

from hahomematic import config, const
from hahomematic.central_unit import CentralConfig
from hahomematic.client import InterfaceConfig
from hahomematic.platforms.custom.entity_definition import validate_entity_definition

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CCU_HOST = "192.168.1.173"
CCU_USERNAME = "Admin"
CCU_PASSWORD = ""


class Example:
    """Example for hahomematic."""

    # Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        """Init example."""
        self.SLEEPCOUNTER = 0
        self.central = None

    def _systemcallback(self, name, *args, **kwargs):
        self.got_devices = True
        if (
            name == const.HH_EVENT_NEW_DEVICES
            and kwargs
            and kwargs.get("device_descriptions")
            and len(kwargs["device_descriptions"]) > 0
        ):
            self.got_devices = True
            return
        if (
            name == const.HH_EVENT_DEVICES_CREATED
            and kwargs
            and kwargs.get("new_devices")
            and len(kwargs["new_devices"]) > 0
        ):
            if len(kwargs["new_devices"]) > 1:
                self.got_devices = True
            return

    def _eventcallback(self, interface_id, channel_address, parameter, value):
        pass

    def _hacallback(self, eventtype, event_data):
        pass

    async def example_run(self):
        """Process the example."""
        central_name = "ccu-dev"
        interface_configs = {
            InterfaceConfig(
                central_name=central_name,
                interface="HmIP-Rf",
                port=2010,
            ),
            InterfaceConfig(
                central_name=central_name,
                interface="BidCos-RF",
                port=2001,
            ),
            InterfaceConfig(
                central_name=central_name,
                interface="VirtualDevices",
                port=9292,
                remote_path="/groups",
            ),
        }
        self.central = await CentralConfig(
            name=central_name,
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            central_id="1234",
            storage_folder="homematicip_local",
            interface_configs=interface_configs,
            default_callback_port=54321,
            use_caches=False,
            client_session=ClientSession(connector=TCPConnector(limit=3)),
        ).create_central()

        # For testing we set a short INIT_TIMEOUT
        config.INIT_TIMEOUT = 10
        # We have to set the cache location of stored data so the central_1 can load
        # it while initializing.
        config.CACHE_DIR = "cache"
        # Add callbacks to handle the events and see what happens on the system.
        self.central.callback_system_event = self._systemcallback
        self.central.callback_entity_event = self._eventcallback
        self.central.callback_ha_event = self._hacallback

        await self.central.start()
        while not self.got_devices and self.SLEEPCOUNTER < 20:
            _LOGGER.info("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(16):
            _LOGGER.info("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the central_1 thread so Python can exit properly.
        await self.central.stop()


# validate the device description
if validate_entity_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
