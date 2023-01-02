# !/usr/bin/python3
import asyncio
import logging
import sys
import time

from hahomematic import config, const
from hahomematic.central_unit import CentralConfig
from hahomematic.client import InterfaceConfig, LocalRessources
from hahomematic.custom_platforms.entity_definition import validate_entity_definition

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CCU_HOST = "127.0.0.1"
CCU_USERNAME = "xxx"
CCU_PASSWORD = "xxx"
CENTRAL_NAME = "ccu-dev"
INTERFACE_ID = f"{CENTRAL_NAME}-{const.LOCAL_INTERFACE}"


class Example:
    # Create a server that listens on 127.0.0.1:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        self.SLEEPCOUNTER = 0
        self.central = None

    def systemcallback(self, src, *args):
        self.got_devices = True
        print("systemcallback: %s" % src)
        if src == const.HH_EVENT_NEW_DEVICES and args and args[0] and len(args[0]) > 0:
            self.got_devices = True
            print("Number of new device descriptions: %i" % len(args[0]))
            return
        elif (
            src == const.HH_EVENT_DEVICES_CREATED
            and args
            and args[0]
            and len(args[0]) > 0
        ):
            if len(args[0]) > 1:
                self.got_devices = True
                print("New devices:")
                print(len(args[0]))
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

        interface_configs = {
            InterfaceConfig(
                central_name=CENTRAL_NAME,
                interface=const.LOCAL_INTERFACE,
                port=2010,
                local_resources=LocalRessources(
                    address_device_translation={
                        # "VCU3432945": "HmIP-STV.json",
                        # "VCU4070501": "HmIP-FSM16.json",
                        # "VCU5628817": "HmIP-SMO.json",
                        "VCU5092447": "HmIP-SMO-A.json",
                        # "VCU4984404": "HmIPW-STHD.json",
                        "VCU1150287": "HmIP-HAP.json",
                        # "VCU3560967": "HmIP-HDM1.json",
                        "VCU5864966": "HmIP-SWDO-I.json",
                        "VCU4264293": "HmIP-RCV-50.json",
                        # "VCU4613288": "HmIP-FROLL.json",
                        # "VCU8655720": "HmIP-CCU3.json",
                        # "VCU1289997": "HmIP-SPDR.json",
                        "VCU1815001": "HmIP-SWD.json",
                        # "VCU2721398": "HmIPW-DRI32.json",
                        # "VCU1673350": "HmIPW-FIO6.json",
                        # "VCU5429697": "HmIP-SAM.json",
                        # "VCU7808411": "HmIP-eTRV-B1.json",
                        # "VCU8333683": "HmIP-SWDM-B2.json",
                        # "VCU4523900": "HmIP-STHO.json",
                        # "VCU4898089": "HmIP-KRC4.json",
                        # "VCU1954019": "HmIP-FAL230-C10.json",
                        # "VCU4567298": "HmIP-DBB.json",
                        # "VCU3790312": "HmIP-SWO-B.json",
                        "VCU7652142": "HmIP-SRD.json",
                        # "VCU1891174": "HmIPW-DRS8.json",
                        # "VCU6874371": "HmIP-MOD-RC8.json",
                        "VCU6354483": "HmIP-STHD.json",
                        "VCU1769958": "HmIP-BWTH.json",
                        # "VCU2118827": "HmIP-DLS.json",
                        # "VCU5778428": "HmIP-HEATING.json",
                        # "VCU1437294": "HmIP-SMI.json",
                        "VCU7981740": "HmIP-SRH.json",
                        "VCU3056370": "HmIP-SLO.json",
                        "VCU4243444": "HmIP-WRCD.json",
                        # "VCU1543608": "HmIP-MP3P.json",
                        "VCU2128127": "HmIP-BSM.json",
                        "VCU3716619": "HmIP-BSL.json",
                        # "VCU6153495": "HmIP-FCI1.json",
                        "VCU1152627": "HmIP-RC8.json",
                        "VCU7204276": "HmIP-DRSI4.json",
                        # "VCU2333555": "HmIP-FSI16.json",
                        "VCU5424977": "HmIP-DSD-PCB.json",
                        # "VCU8063453": "HmIP-STH.json",
                        # "VCU7447418": "HmIP-PCBS2.json",
                        # "VCU9344471": "HmIP-SPI.json",
                        # "VCU2680226": "HmIP-WTH-2.json",
                        # "VCU6306084": "HmIP-BRC2.json",
                        # "VCU2573721": "HmIP-SMO-2.json",
                        # "VCU5980155": "HmIP-PCBS-BAT.json",
                        "VCU8249617": "HmIP-ASIR-2.json",
                        # "VCU1004487": "HmIPW-DRAP.json",
                        "VCU7549831": "HmIP-STE2-PCB.json",
                        # "VCU9724704": "HmIP-DLD.json",
                        # "VCU1768323": "HmIP-eTRV-C-2.json",
                        # "VCU8205532": "HmIP-SCTH230.json",
                        # "VCU2407364": "HmIP-PCBS.json",
                        # "VCU1841406": "HmIP-SWO-PL.json",
                        # "VCU2826390": "HmIPW-STH.json",
                        # "VCU3188750": "HmIP-WGC.json",
                        "VCU3609622": "HmIP-eTRV-2.json",
                        # "VCU4743739": "HmIPW-SPI.json",
                        # "VCU6948166": "HmIP-DRDI3.json",
                        # "VCU5801873": "HmIP-PMFS.json",
                        # "VCU5644414": "HmIP-SWDM.json",
                        # "VCU8539034": "HmIP-WRCR.json",
                        "VCU3015080": "HmIP-SCI.json",
                        # "VCU1494703": "HmIP-eTRV-E.json",
                        "VCU9333179": "HmIP-ASIR.json",
                        # "VCU8126977": "HmIP-MOD-OC8.json",
                        # "VCU4704397": "HmIPW-WRC6.json",
                        # "VCU7807849": "HmIPW-DRBL4.json",
                        # "VCU5597068": "HmIPW-SMI55.json",
                        "VCU1399816": "HmIP-BDT.json",
                        # "VCU8255833": "HmIP-STHO-A.json",
                        # "VCU1803301": "HmIP-USBSM.json",
                        # "VCU9933791": "HmIPW-DRD3.json",
                        # "VCU6977344": "HmIP-MIO16-PCB.json",
                        # "VCU2913614": "HmIP-WHS2.json",
                        # "VCU8585352": "HmIP-DRSI1.json",
                        # "VCU8451105": "HmIPW-WTH.json",
                        "VCU1362746": "HmIP-SWO-PR.json",
                        "VCU7631078": "HmIP-FDT.json",
                        # "VCU1223813": "HmIP-FBL.json",
                        # "VCU8688276": "HmIP-eTRV-B.json",
                        # "VCU6531931": "HmIP-RCB1.json",
                        # "VCU1111390": "HmIP-HDM2.json",
                        "VCU2822385": "HmIP-SWSD.json",
                        "VCU1533290": "HmIP-WRC6.json",
                        "VCU5334484": "HmIP-KRCA.json",
                        # "VCU1260322": "HmIP-RFUSB.json",
                        # "VCU8537918": "HmIP-BROLL.json",
                        "VCU9981826": "HmIP-SFD.json",
                        # "VCU2428569": "HmIPW-FAL230-C6.json",
                        # "VCU9628024": "HmIPW-FALMOT-C12.json",
                        # "VCU9710932": "HmIP-SMI55.json",
                    }
                ),
            ),
        }
        self.central = await CentralConfig(
            name=CENTRAL_NAME,
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            central_id="1234",
            storage_folder="homematicip_local",
            interface_configs=interface_configs,
            default_callback_port=48888,
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
        await self.central.start()

        while not self.got_devices and self.SLEEPCOUNTER < 20:
            print("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(16):
            _LOGGER.debug("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the central_1 thread so Python can exit properly.
        await self.central.stop()


# valdate the device description
if validate_entity_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
