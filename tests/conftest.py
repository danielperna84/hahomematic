"""Test support for hahomematic."""
from __future__ import annotations

import logging
from unittest.mock import patch

from aiohttp import ClientSession, TCPConnector
import pydevccu
import pytest

from hahomematic.central import CentralUnit

from tests import const, helper

logging.basicConfig(level=logging.INFO)

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


@pytest.fixture
def pydev_ccu_full() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT))
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
def pydev_ccu_mini() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT), devices=["HmIP-BWTH"])
    ccu.start()
    yield ccu
    ccu.stop()


@pytest.fixture
async def client_session() -> ClientSession:
    """Create ClientSession for json client."""
    session = ClientSession(connector=TCPConnector(limit=3))
    yield session
    if not session.closed:
        await session.close()


@pytest.fixture
async def central_unit_mini(pydev_ccu_mini: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""
    central = await helper.get_pydev_ccu_central_unit_full(client_session=None)
    yield central
    await central.stop()
    await central.clear_all_caches()


@pytest.fixture
async def central_unit_full(pydev_ccu_full: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""

    def entity_data_event_callback(*args, **kwargs):
        """Do dummy entity_data_event_callback."""

    def entity_event_callback(*args, **kwargs):
        """Do dummy entity_event_callback."""

    def ha_event_callback(*args, **kwargs):
        """Do dummy ha_event_callback."""

    def system_event_callback(*args, **kwargs):
        """Do dummy system_event_callback."""

    central = await helper.get_pydev_ccu_central_unit_full(
        client_session=None,
    )

    central.register_entity_data_event_callback(entity_data_event_callback)
    central.register_entity_event_callback(entity_event_callback)
    central.register_ha_event_callback(ha_event_callback)
    central.register_system_event_callback(system_event_callback)

    yield central

    central.unregister_entity_data_event_callback(entity_data_event_callback)
    central.unregister_entity_event_callback(entity_event_callback)
    central.unregister_ha_event_callback(ha_event_callback)
    central.unregister_system_event_callback(system_event_callback)
    await central.stop()
    await central.clear_all_caches()


@pytest.fixture
async def factory() -> helper.Factory:
    """Return central factory."""
    return helper.Factory(client_session=None)
