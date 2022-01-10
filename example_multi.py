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
CCU2_HOST = "192.168.1.173"
CCU2_USERNAME = "Admin"
CCU2_PASSWORD = ""


class Example:
    # Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        self.SLEEPCOUNTER = 0
        self.central_1 = None
        self.central_2 = None

    def systemcallback(self, src, *args):
        self.got_devices = True
        print("systemcallback: %s" % src)
        if src == const.HH_EVENT_NEW_DEVICES and args and args[0] and len(args[0]) > 0:
            self.got_devices = True
            print("Number of new device descriptions: %i" % len(args[0]))
            return
        elif src == const.HH_EVENT_DEVICES_CREATED:
            if len(self.central_1.hm_devices) > 1:
                self.got_devices = True
                print("New devices:")
                print(len(args[0]))
                print("New entities:")
                print(len(args[1]))
            return
        for arg in args:
            print("argument: %s" % arg)

    def systemcallback2(self, src, *args):
        self.got_devices = True
        print("systemcallback: %s" % src)
        if src == const.HH_EVENT_NEW_DEVICES:
            print("Number of new device descriptions: %i" % len(args[0]))
            return
        elif src == const.HH_EVENT_DEVICES_CREATED:
            if len(self.central_2.hm_devices) > 1:
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
        self.central_1 = await CentralConfig(
            domain="hahm",
            name="ccu-dev",
            loop=asyncio.get_running_loop(),
            xml_rpc_server=register_xml_rpc_server(),
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            storage_folder="hahm",
        ).get_central()
        self.central_2 = await CentralConfig(
            domain="hahm",
            name="ccu-2-dev",
            loop=asyncio.get_running_loop(),
            xml_rpc_server=register_xml_rpc_server(),
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            storage_folder="hahm",
        ).get_central()

        # For testing we set a short INIT_TIMEOUT
        config.INIT_TIMEOUT = 10
        # We have to set the cache location of stored data so the central_1 can load
        # it while initializing.
        config.CACHE_DIR = "cache"
        # Add callbacks to handle the events and see what happens on the system.
        self.central_1.callback_system_event = self.systemcallback
        self.central_1.callback_entity_event = self.eventcallback
        self.central_1.callback_ha_event = self.hacallback
        self.central_2.callback_system_event = self.systemcallback2
        self.central_2.callback_entity_event = self.eventcallback

        # Create clients
        client1 = await ClientConfig(
            central=self.central_1,
            name="hmip",
            port=2010,
        ).get_client()
        client2 = await ClientConfig(
            central=self.central_1,
            name="rf",
            port=2001,
        ).get_client()
        client3 = await ClientConfig(
            central=self.central_1,
            name="groups",
            port=9292,
            path="/groups",
        ).get_client()
        client1_1 = await ClientConfig(
            central=self.central_2,
            name="rf",
            port=2001,
        ).get_client()

        # Clients have to exist prior to creating the devices
        self.central_1.create_devices()
        self.central_1.start_connection_checker()
        self.central_2.create_devices()
        self.central_2.start_connection_checker()
        # Once the central_1 is running we subscribe to receive messages.
        await client1.proxy_init()
        await client2.proxy_init()
        await client3.proxy_init()
        await client1_1.proxy_init()

        while not self.got_devices and self.SLEEPCOUNTER < 20:
            print("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(16):
            _LOGGER.debug("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the central_1 thread so Python can exit properly.
        await self.central_1.stop()
        await self.central_2.stop()


# valdate the device description
if validate_entity_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
