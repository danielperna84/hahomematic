# !/usr/bin/python3
import asyncio
import logging
import sys
import time

from hahomematic import config, const
from hahomematic.central_unit import CentralConfig
from hahomematic.client import ClientConfig
from hahomematic.devices.entity_definition import validate_entity_definition
from hahomematic.xml_rpc_server import register_xml_rpc_server

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CCU_HOST = "192.168.1.173"
CCU_USERNAME = "Admin"
CCU_PASSWORD = ""


class Example:
    # Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        self.SLEEPCOUNTER = 0
        self.central = None

    def systemcallback(self, src, *args):
        self.got_devices = True
        print("systemcallback: %s" % src)
        if src == const.HH_EVENT_NEW_DEVICES:
            print("Number of new device descriptions: %i" % len(args[0]))
            return
        elif src == const.HH_EVENT_DEVICES_CREATED:
            if len(self.central.hm_devices) > 1:
                self.got_devices = True
                print("New devices:")
                print(len(args[0]))
                print("New entities:")
                print(len(args[1]))
            return
        for arg in args:
            print("argument: %s" % arg)

    def eventcallback(self, address, interface_id, key, value):
        print(
            "eventcallback at %i: %s, %s, %s, %s"
            % (int(time.time()), address, interface_id, key, value)
        )

    def hacallback(self, eventtype, event_data):
        print(
            "hacallback: %s, %s"
            % (
                eventtype,
                event_data,
            )
        )

    async def example_run(self):
        self.central = CentralConfig(
            name="ccu-dev",
            entry_id="123",
            loop=asyncio.get_running_loop(),
            xml_rpc_server=register_xml_rpc_server(),
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            enable_virtual_channels=True,
        ).get_central()

        # For testing we set a short INIT_TIMEOUT
        config.INIT_TIMEOUT = 10
        # We have to set the cache location of stored data so the central_1 can load
        # it while initializing.
        config.CACHE_DIR = "cache"
        # Add callbacks to handle the events and see what happens on the system.
        self.central.callback_system_event = self.systemcallback
        self.central.callback_entity_event = self.eventcallback
        self.central.callback_ha_event = self.hacallback

        # Create clients
        client1 = await ClientConfig(
            central=self.central,
            name="hmip",
            port=2010,
        ).get_client()
        client2 = await ClientConfig(
            central=self.central,
            name="rf",
            port=2001,
        ).get_client()
        client3 = await ClientConfig(
            central=self.central,
            name="groups",
            port=9292,
            path="/groups",
        ).get_client()

        # Clients have to exist prior to creating the devices
        self.central.create_devices()
        # Once the central_1 is running we subscribe to receive messages.
        await client1.proxy_init()
        await client2.proxy_init()
        await client3.proxy_init()

        while not self.got_devices and self.SLEEPCOUNTER < 20:
            print("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(1600):
            _LOGGER.debug("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the central_1 thread so Python can exit properly.
        await self.central.stop()


# valdate the device description
if validate_entity_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
