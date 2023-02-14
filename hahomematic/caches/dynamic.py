"""Module for the dynamic caches."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final

from hahomematic import central_unit as hmcu
from hahomematic.const import (
    IF_BIDCOS_RF_NAME,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    HmCallSource,
)
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.support import get_device_address, updated_within_seconds

_LOGGER = logging.getLogger(__name__)


class DeviceDetailsCache:
    """Cache for device/channel details."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the device details cache."""
        # {address, name}
        self._names_cache: Final[dict[str, str]] = {}
        self._interface_cache: Final[dict[str, str]] = {}
        self.device_channel_ids: Final[dict[str, str]] = {}
        self._channel_rooms: dict[str, set[str]] = {}
        self._device_room: Final[dict[str, str]] = {}
        self._functions: dict[str, set[str]] = {}
        self._central: Final[hmcu.CentralUnit] = central
        self._last_updated = INIT_DATETIME

    async def load(self) -> None:
        """Fetch names from backend."""
        if updated_within_seconds(
            last_update=self._last_updated, max_age_seconds=(MAX_CACHE_AGE / 2)
        ):
            return
        self.clear()
        _LOGGER.debug("load: Loading names for %s", self._central.name)
        if client := self._central.get_primary_client():
            await client.fetch_device_details()
        _LOGGER.debug("load: Loading rooms for %s", self._central.name)
        self._channel_rooms = await self._get_all_rooms()
        self._identify_device_room()
        _LOGGER.debug("load: Loading functions for %s", self._central.name)
        self._functions = await self._get_all_functions()
        self._last_updated = datetime.now()

    def add_name(self, address: str, name: str) -> None:
        """Add name to cache."""
        if address not in self._names_cache:
            self._names_cache[address] = name

    def get_name(self, address: str) -> str | None:
        """Get name from cache."""
        return self._names_cache.get(address)

    def add_interface(self, address: str, interface: str) -> None:
        """Add interface to cache."""
        if address not in self._interface_cache:
            self._interface_cache[address] = interface

    def get_interface(self, address: str) -> str:
        """Get interface from cache."""
        return self._interface_cache.get(address) or IF_BIDCOS_RF_NAME

    def add_device_channel_id(self, address: str, channel_id: str) -> None:
        """Add channel id for a channel."""
        self.device_channel_ids[address] = channel_id

    async def _get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms, if available."""
        if client := self._central.get_primary_client():
            return await client.get_all_rooms()
        return {}

    def get_room(self, device_address: str) -> str | None:
        """Return room by device_address."""
        return self._device_room.get(device_address)

    async def _get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions, if available."""
        if client := self._central.get_primary_client():
            return await client.get_all_functions()
        return {}

    def get_function_text(self, address: str) -> str | None:
        """Return function by address."""
        if functions := self._functions.get(address):
            return ",".join(functions)
        return None

    def remove_device(self, device: HmDevice) -> None:
        """Remove name from cache."""
        if device.device_address in self._names_cache:
            del self._names_cache[device.device_address]
        for channel_address in device.channels:
            if channel_address in self._names_cache:
                del self._names_cache[channel_address]

    def clear(self) -> None:
        """Clear the cache."""
        self._names_cache.clear()
        self._channel_rooms.clear()
        self._functions.clear()
        self._last_updated = INIT_DATETIME

    def _identify_device_room(self) -> None:
        """
        Identify a possible room of a device.

        A room is relevant for a device, if there is only one room assigned to the channels.
        """
        device_rooms: dict[str, set[str]] = {}
        for address, rooms in self._channel_rooms.items():
            device_address = get_device_address(address=address)
            if device_address not in device_rooms:
                device_rooms[device_address] = set()
            device_rooms[device_address].update(rooms)
        for device_address, rooms in device_rooms.items():
            if rooms and len(set(rooms)) == 1:
                self._device_room[device_address] = list(set(rooms))[0]


class DeviceDataCache:
    """Cache for device/channel initial data."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the device data cache."""
        self._central: Final[hmcu.CentralUnit] = central
        # { interface, {channel_address, {parameter, CacheEntry}}}
        self._central_values_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._last_updated = INIT_DATETIME

    def is_empty(self, max_age_seconds: int) -> bool:
        """Return if cache is empty."""
        if len(self._central_values_cache) == 0:
            return True
        if not updated_within_seconds(
            last_update=self._last_updated, max_age_seconds=max_age_seconds
        ):
            self.clear()
            return True
        return False

    async def load(self) -> None:
        """Fetch device data from backend."""
        if updated_within_seconds(
            last_update=self._last_updated, max_age_seconds=(MAX_CACHE_AGE / 2)
        ):
            return
        self.clear()
        _LOGGER.debug("load: device data for %s", self._central.name)
        if client := self._central.get_primary_client():
            await client.fetch_all_device_data()

    async def refresh_entity_data(
        self, paramset_key: str | None = None, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Refresh entity data."""
        for entity in self._central.get_readable_entities():
            if paramset_key is None or (
                isinstance(entity, GenericEntity) and entity.paramset_key == paramset_key
            ):
                await entity.load_entity_value(
                    call_source=HmCallSource.HM_INIT,
                    max_age_seconds=max_age_seconds,
                )

    def add_device_data(self, device_data: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Add device data to cache."""
        self._central_values_cache = device_data
        self._last_updated = datetime.now()

    def get_device_data(
        self,
        interface: str,
        channel_address: str,
        parameter: str,
        max_age_seconds: int,
    ) -> Any:
        """Get device data from cache."""
        if not self.is_empty(max_age_seconds=max_age_seconds):
            return (
                self._central_values_cache.get(interface, {})
                .get(channel_address, {})
                .get(parameter, NO_CACHE_ENTRY)
            )
        return NO_CACHE_ENTRY

    def clear(self) -> None:
        """Clear the cache."""
        self._central_values_cache.clear()
        self._last_updated = INIT_DATETIME
