"""Test support for hahomematic."""
from __future__ import annotations

import logging

from aiohttp import ClientSession, TCPConnector
from hahomematic.central_unit import CentralUnit
import pydevccu
import pytest

import const
import helper
from helper import get_pydev_ccu_central_unit_full

logging.basicConfig(level=logging.INFO)

# pylint: disable=protected-access, redefined-outer-name


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
async def central_unit_mini(
    pydev_ccu_mini: pydevccu.Server, client_session: ClientSession
) -> CentralUnit:
    """Create and yield central."""
    central_unit = await get_pydev_ccu_central_unit_full(client_session, use_caches=True)
    yield central_unit
    await central_unit.stop()


@pytest.fixture
async def central_unit_full(
    pydev_ccu_full: pydevccu.Server, client_session: ClientSession
) -> CentralUnit:
    """Create and yield central."""

    def entity_data_event_callback(*args, **kwargs):
        """Do dummy entity_data_event_callback."""

    def entity_event_callback(*args, **kwargs):
        """Do dummy entity_event_callback."""

    def ha_event_callback(*args, **kwargs):
        """Do dummy ha_event_callback."""

    def system_event_callback(*args, **kwargs):
        """Do dummy system_event_callback."""

    central_unit = await get_pydev_ccu_central_unit_full(client_session, use_caches=False)

    central_unit.register_entity_data_event_callback(entity_data_event_callback)
    central_unit.register_entity_event_callback(entity_event_callback)
    central_unit.register_ha_event_callback(ha_event_callback)
    central_unit.register_system_event_callback(system_event_callback)

    yield central_unit

    central_unit.unregister_entity_data_event_callback(entity_data_event_callback)
    central_unit.unregister_entity_event_callback(entity_event_callback)
    central_unit.unregister_ha_event_callback(ha_event_callback)
    central_unit.unregister_system_event_callback(system_event_callback)
    await central_unit.stop()


@pytest.fixture(name="central_local_factory")
async def central_unit_local_factory(
    client_session: ClientSession,
) -> helper.CentralUnitLocalFactory:
    """Return central factory."""
    return helper.CentralUnitLocalFactory(client_session)
