# !/usr/bin/python3
import asyncio
import logging
import sys
import time

from hahomematic import config, const
from hahomematic.client import ClientFactory
from hahomematic.devices.device_description import validate_device_description
from hahomematic.server import Server
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
        self.server = None
        self.server2 = None

    def systemcallback(self, src, *args):
        self.got_devices = True
        print("systemcallback: %s" % src)
        if src == const.HH_EVENT_NEW_DEVICES:
            print("Number of new device descriptions: %i" % len(args[0]))
            return
        elif src == const.HH_EVENT_DEVICES_CREATED:
            if len(self.server.hm_devices) > 1:
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
            if len(self.server2.hm_devices) > 1:
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

    def clickcallback(self, eventtype, event_data):
        print(
            "clickcallback: %s, %s"
            % (
                eventtype,
                event_data,
            )
        )

    def impulsecallback(self, eventtype, event_data):
        print(
            "impulsecallback: %s, %s"
            % (
                eventtype,
                event_data,
            )
        )

    async def example_run(self):
        self.server = Server(
            "ccu-dev",
            "123",
            asyncio.get_running_loop(),
            xml_rpc_server=register_xml_rpc_server(),
            enable_virtual_channels=True,
        )
        self.server2 = Server(
            "ccu-2-dev",
            "456",
            asyncio.get_running_loop(),
            xml_rpc_server=register_xml_rpc_server(),
            enable_virtual_channels=True,
        )

        # For testing we set a short INIT_TIMEOUT
        config.INIT_TIMEOUT = 10
        # We have to set the cache location of stored data so the server can load
        # it while initializing.
        config.CACHE_DIR = "cache"
        # Add callbacks to handle the events and see what happens on the system.
        self.server.callback_system_event = self.systemcallback
        self.server.callback_entity_event = self.eventcallback
        self.server.callback_click_event = self.clickcallback
        self.server.callback_impulse_event = self.impulsecallback
        self.server2.callback_system_event = self.systemcallback2
        self.server2.callback_entity_event = self.eventcallback

        # Create clients
        client1 = await ClientFactory(
            server=self.server,
            name="hmip",
            host=CCU_HOST,
            port=2010,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
        ).get_client()
        client2 = await ClientFactory(
            server=self.server,
            name="rf",
            host=CCU_HOST,
            port=2001,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
        ).get_client()
        client3 = await ClientFactory(
            server=self.server,
            name="groups",
            host=CCU_HOST,
            port=9292,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            path="/groups",
        ).get_client()
        client1_1 = await ClientFactory(
            server=self.server2,
            name="rf",
            host=CCU2_HOST,
            port=2001,
            username=CCU2_USERNAME,
            password=CCU2_PASSWORD,
        ).get_client()

        # Clients have to exist prior to creating the devices
        self.server.create_devices()
        self.server.start_connection_checker()
        self.server2.create_devices()
        self.server2.start_connection_checker()
        # Once the server is running we subscribe to receive messages.
        await client1.proxy_init()
        await client2.proxy_init()
        await client3.proxy_init()
        await client1_1.proxy_init()

        while not self.got_devices and self.SLEEPCOUNTER < 20:
            print("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(1600):
            _LOGGER.debug("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the server thread so Python can exit properly.
        await self.server.stop()
        await self.server2.stop()


# valdate the device description
if validate_device_description():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
