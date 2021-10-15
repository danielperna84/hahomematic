#!/usr/bin/python3
import time
import sys
import logging
from hahomematic import config, const
from hahomematic.server import Server
from hahomematic.client import Client

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

SLEEPCOUNTER = 0
GOT_DEVICES = False


# Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
server = Server("ccu-dev")

def systemcallback(src, *args):
    global GOT_DEVICES
    print("systemcallback: %s" % src)
    if src == const.HH_EVENT_NEW_DEVICES:
        print("Number of new device descriptions: %i" % len(args[0]))
        return
    elif src == const.HH_EVENT_DEVICES_CREATED:
        GOT_DEVICES = True
        print("All devices:")
        print(server.ha_devices)
        for _, device in server.ha_devices.items():
            print(device)
        print("New devices:")
        print(args[0])
        print("New entities:")
        print(args[1])
        return
    for arg in args:
        print("argument: %s" % arg)

def eventcallback(address, interface_id, key, value):
    print("eventcallback at %i: %s, %s, %s, %s" % (int(time.time()), address, interface_id, key, value))

def entityupdatecallback(entity_id):
    print("entityupdatecallback at %i: %s" % (int(time.time()), entity_id))


# Specify a unique name to identify our server.
config.INTERFACE_ID = "myserver"
# For testing we set a short INIT_TIMEOUT
config.INIT_TIMEOUT = 10
# We have to set the cache location of stored data so the server can load
# it while initializing.
config.CACHE_DIR = 'cache'
# Add callbacks to handle the events and see what happens on the system.
config.CALLBACK_SYSTEM = systemcallback
config.CALLBACK_EVENT = eventcallback
config.CALLBACK_ENTITY_UPDATE = entityupdatecallback


# Create clients
# Connect to pydevccu at 127.0.0.1:2001
client1 = Client(server=server, name="localhost", host="127.0.0.1", port=2001, password='')
# Connect to CCU for RF-deices at 192.168.1.173:2001
client2 = Client(server=server, name="rf", host="192.168.1.173", port=2001, password='')
# Connect to CCU for HmIP-deices at 192.168.1.173:2010
client3 = Client(server=server, name="hmip", host="192.168.1.173", port=2010, password='')

# Clients have to exist prior to starting the server thread!
server.start()
# Once the server is running we subscribe to receive messages.
client1.proxy_init()
client2.proxy_init()
client3.proxy_init()

while not GOT_DEVICES and SLEEPCOUNTER < 20:
    print("Waiting for devices")
    SLEEPCOUNTER += 1
    time.sleep(1)
time.sleep(5)

for i in range(16):
    if i % 4 == 0:
        for client in server.clients:
            if not server.clients[client].is_connected():
                LOG.warning("Disconnected. Reconnecting for %s" % client)
                server.clients[client].proxy_init()
    LOG.debug("Sleeping (%i)", i)
    time.sleep(2)
# Stop the server thread so Python can exit properly.
server.stop()

sys.exit(0)