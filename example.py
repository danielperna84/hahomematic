#!/usr/bin/python3
import time
import sys
import logging
import hahomematic

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

SLEEPCOUNTER = 0
GOT_DEVICES = False

def systemcallback(src, *args):
    global GOT_DEVICES
    print("systemcallback: %s" % src)
    if src == hahomematic.const.HH_EVENT_NEW_DEVICES:
        print("Number of new device descriptions: %i" % len(args[0]))
        return
    elif src == hahomematic.const.HH_EVENT_ENTITIES_CREATED:
        GOT_DEVICES = True
    for arg in args:
        print("argument: %s" % arg)

def eventcallback(address, interface_id, key, value):
    print("eventcallback at %i: %s, %s, %s, %s" % (int(time.time()), address, interface_id, key, value))

def entityupdatecallback(entity_id):
    print("entityupdatecallback at %i: %s" % (int(time.time()), entity_id))


# Specify a unique name to identify our server.
hahomematic.config.INTERFACE_ID = "myserver"
# For testing we set a short INIT_TIMEOUT
hahomematic.config.INIT_TIMEOUT = 10
# We have to set the locations of stored data so the server can load
# it while initializing.
hahomematic.config.FILE_DEVICES = 'ha_devices.json'
hahomematic.config.FILE_PARAMSETS = 'ha_paramsets.json'
hahomematic.config.FILE_NAMES = 'ha_names.json'
# Add callbacks to handle the events and see what happens on the system.
hahomematic.config.CALLBACK_SYSTEM = systemcallback
hahomematic.config.CALLBACK_EVENT = eventcallback
hahomematic.config.CALLBACK_ENTITY_UPDATE = entityupdatecallback
# Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
server = hahomematic.Server()

# Create clients
# Connect to pydevccu at 127.0.0.1:2001
client1 = hahomematic.Client(name="localhost", host="127.0.0.1", port=2001, password='', local_port=server.local_port)
# Connect to CCU for RF-deices at 192.168.1.173:2001
client2 = hahomematic.Client(name="rf", host="192.168.1.173", port=2001, password='', local_port=server.local_port)
# Connect to CCU for HmIP-deices at 192.168.1.173:2010
client3 = hahomematic.Client(name="hmip", host="192.168.1.173", port=2010, password='', local_port=server.local_port)

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
print(hahomematic.data.HA_DEVICES)
time.sleep(5)

for i in range(16):
    if i % 4 == 0:
        for client in hahomematic.data.CLIENTS:
            if not hahomematic.data.CLIENTS[client].is_connected():
                LOG.warning("Disconnected. Reconnecting for %s" % client)
                hahomematic.data.CLIENTS[client].proxy_init()
    LOG.debug("Sleeping (%i)", i)
    time.sleep(2)
# Stop the server thread so Python can exit properly.
server.stop()

sys.exit(0)