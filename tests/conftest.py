from __future__ import annotations

import asyncio
import logging
from typing import Any

import pydevccu
import pytest

from hahomematic import config, const
from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig
from hahomematic.device import HmDevice
from hahomematic.entity import CustomEntity, GenericEntity
from hahomematic.helpers import get_device_address

logging.basicConfig(level=logging.DEBUG)
CCU_HOST = "127.0.0.1"
CCU_USERNAME = "user"
CCU_PASSWORD = "pass"
GOT_DEVICES = False
# content of conftest.py


def pytest_configure(config):
    import sys

    sys._called_from_test = True


def pytest_unconfigure(config):  # pragma: no cover
    import sys  # This was missing from the manual

    del sys._called_from_test


@pytest.yield_fixture(scope="session")
def loop() -> asyncio.AbstractEventLoop:
    """Yield running event_loop"""
    event_loop = asyncio.get_event_loop_policy().new_event_loop()
    yield event_loop
    event_loop.close()


@pytest.fixture
def pydev_ccu() -> pydevccu.Server:
    """Defines the virtual ccu"""
    ccu = pydevccu.Server()
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
async def central(
    loop: asyncio.AbstractEventLoop, pydev_ccu: pydevccu.Server
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
            central_name="Test",
            interface="BidCos-RF",
            port=2001,
        )
    }

    central_unit = await CentralConfig(
        name="ccu-dev",
        host=CCU_HOST,
        username=CCU_USERNAME,
        password=CCU_PASSWORD,
        central_id="test1234",
        storage_folder="homematicip_local",
        interface_configs=interface_configs,
        default_callback_port=54321,
    ).get_central()
    central_unit.callback_system_event = systemcallback
    await central_unit.start()
    while not GOT_DEVICES and sleep_counter < 300:
        print("Waiting for devices")
        sleep_counter += 1
        await asyncio.sleep(1)

    yield central_unit

    await central_unit.stop()


async def get_value_from_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> Any:
    """Return the device value."""
    hm_entity = await get_hm_generic_entity(
        central_unit=central_unit, address=address, parameter=parameter
    )
    assert hm_entity
    await hm_entity.load_entity_value(
        call_source=const.HmCallSource.MANUAL_OR_SCHEDULED
    )
    return hm_entity.value


def get_hm_device(central_unit: CentralUnit, address: str) -> HmDevice | None:
    """Return the hm_device."""
    d_address = get_device_address(address=address)
    return central_unit.devices.get(d_address)


async def get_hm_generic_entity(
    central_unit: CentralUnit, address: str, parameter: str
) -> GenericEntity | None:
    """Return the hm generic_entity."""
    hm_device = get_hm_device(central_unit=central_unit, address=address)
    assert hm_device
    hm_entity = hm_device.generic_entities.get((address, parameter))
    assert hm_entity
    return hm_entity


async def get_hm_custom_entity(
    central_unit: CentralUnit, address: str, channel_no: int, do_load: bool = False
) -> CustomEntity | None:
    """Return the hm custom_entity."""
    hm_device = get_hm_device(central_unit, address)
    assert hm_device
    for custom_entity in hm_device.custom_entities.values():
        if custom_entity.channel_no == channel_no:
            if do_load:
                await custom_entity.load_entity_value(
                    call_source=const.HmCallSource.MANUAL_OR_SCHEDULED
                )
            return custom_entity
    return None


def send_device_value_to_ccu(
    pydev_ccu: pydevccu.Server, address: str, parameter: str, value: Any
) -> None:
    """Send the device value to ccu."""
    pydev_ccu.setValue(address, parameter, value)
