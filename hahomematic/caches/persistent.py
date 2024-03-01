"""Module for the persistent caches."""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from datetime import datetime
import logging
import os
from typing import Any, Final

import orjson

from hahomematic import central as hmcu
from hahomematic.const import (
    DEFAULT_ENCODING,
    FILE_DEVICES,
    FILE_PARAMSETS,
    INIT_DATETIME,
    DataOperationResult,
    Description,
    Operations,
    ParamsetKey,
)
from hahomematic.platforms.device import HmDevice
from hahomematic.support import (
    Channel,
    check_or_create_directory,
    get_device_address,
    get_split_channel_address,
)

_LOGGER: Final = logging.getLogger(__name__)


class BasePersistentCache(ABC):
    """Cache for files."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        filename: str,
        persistant_cache: dict[str, Any],
    ) -> None:
        """Init the base class of the persistent cache."""
        self._central: Final = central
        self._cache_dir: Final = f"{central.config.storage_folder}/cache"
        self._filename: Final = f"{central.name}_{filename}"
        self._persistant_cache: Final = persistant_cache
        self.last_save: datetime = INIT_DATETIME

    async def save(self) -> DataOperationResult:
        """Save current name data in NAMES to disk."""

        def _save() -> DataOperationResult:
            if not check_or_create_directory(self._cache_dir):
                return DataOperationResult.NO_SAVE

            self.last_save = datetime.now()
            if self._central.config.use_caches:
                with open(
                    file=os.path.join(self._cache_dir, self._filename),
                    mode="wb",
                ) as fptr:
                    fptr.write(
                        orjson.dumps(self._persistant_cache, option=orjson.OPT_NON_STR_KEYS)
                    )
                return DataOperationResult.SAVE_SUCCESS

            _LOGGER.debug("save: not saving cache for %s", self._central.name)
            return DataOperationResult.NO_SAVE

        return await self._central.async_add_executor_job(_save)

    async def load(self) -> DataOperationResult:
        """Load file from disk into dict."""

        def _load() -> DataOperationResult:
            if not check_or_create_directory(self._cache_dir):
                return DataOperationResult.NO_LOAD
            if not os.path.exists(os.path.join(self._cache_dir, self._filename)):
                return DataOperationResult.NO_LOAD
            with open(
                file=os.path.join(self._cache_dir, self._filename),
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                self._persistant_cache.clear()
                self._persistant_cache.update(orjson.loads(fptr.read()))
            return DataOperationResult.LOAD_SUCCESS

        return await self._central.async_add_executor_job(_load)

    async def clear(self) -> None:
        """Remove stored file from disk."""

        def _clear() -> None:
            check_or_create_directory(self._cache_dir)
            if os.path.exists(os.path.join(self._cache_dir, self._filename)):
                os.unlink(os.path.join(self._cache_dir, self._filename))
            self._persistant_cache.clear()

        await self._central.async_add_executor_job(_clear)


class DeviceDescriptionCache(BasePersistentCache):
    """Cache for device/channel names."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the device description cache."""
        # {interface_id, [device_descriptions]}
        self._raw_device_descriptions: Final[dict[str, list[dict[str, Any]]]] = {}
        super().__init__(
            central=central,
            filename=FILE_DEVICES,
            persistant_cache=self._raw_device_descriptions,
        )
        # {interface_id, {device_address, [channel_address]}}
        self._addresses: Final[dict[str, dict[str, list[str]]]] = {}
        # {interface_id, {address, device_descriptions}}
        self._device_descriptions: Final[dict[str, dict[str, dict[str, Any]]]] = {}

    def add_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """Add device_description to cache."""
        if interface_id not in self._raw_device_descriptions:
            self._raw_device_descriptions[interface_id] = []

        self._remove_device(
            interface_id=interface_id,
            deleted_addresses=[device_description[Description.ADDRESS]],
        )
        self._raw_device_descriptions[interface_id].append(device_description)

        self._convert_device_description(
            interface_id=interface_id, device_description=device_description
        )

    def get_raw_device_descriptions(self, interface_id: str) -> list[dict[str, Any]]:
        """Find raw device in cache."""
        return self._raw_device_descriptions.get(interface_id, [])

    async def remove_device(self, device: HmDevice) -> None:
        """Remove device from cache."""
        deleted_addresses: list[str] = [device.device_address]
        deleted_addresses.extend(device.channels)
        self._remove_device(interface_id=device.interface_id, deleted_addresses=deleted_addresses)
        await self.save()

    def _remove_device(self, interface_id: str, deleted_addresses: list[str]) -> None:
        """Remove device from cache."""
        self._raw_device_descriptions[interface_id] = [
            raw_device
            for raw_device in self.get_raw_device_descriptions(interface_id)
            if raw_device[Description.ADDRESS] not in deleted_addresses
        ]

        for address in deleted_addresses:
            try:
                if ":" not in address and self._addresses.get(interface_id, {}).get(address, []):
                    del self._addresses[interface_id][address]
                if self._device_descriptions.get(interface_id, {}).get(address, {}):
                    del self._device_descriptions[interface_id][address]
            except KeyError:
                _LOGGER.warning("REMOVE_DEVICE failed: Unable to delete: %s", address)

    def get_addresses(self, interface_id: str) -> tuple[str, ...]:
        """Return the addresses by interface."""
        return tuple(self._addresses.get(interface_id, {}).keys())

    def get_channels(self, interface_id: str, device_address: str) -> Mapping[str, Channel]:
        """Return the device channels by interface and device_address."""
        channels: dict[str, Channel] = {}
        for channel_address in self._addresses.get(interface_id, {}).get(device_address, []):
            channel_name = str(
                self.get_device_parameter(
                    interface_id=interface_id,
                    device_address=channel_address,
                    parameter=Description.TYPE,
                )
            )
            channels[channel_address] = Channel(type=channel_name, address=channel_address)

        return channels

    def get_device_descriptions(self, interface_id: str) -> dict[str, dict[str, Any]]:
        """Return the devices by interface."""
        return self._device_descriptions.get(interface_id, {})

    def get_device(self, interface_id: str, device_address: str) -> dict[str, Any]:
        """Return the device dict by interface and device_address."""
        return self._device_descriptions.get(interface_id, {}).get(device_address, {})

    def get_device_with_channels(
        self, interface_id: str, device_address: str
    ) -> Mapping[str, Any]:
        """Return the device dict by interface and device_address."""
        data: dict[str, Any] = {
            device_address: self._device_descriptions.get(interface_id, {}).get(device_address, {})
        }
        children = data[device_address][Description.CHILDREN]
        for channel_address in children:
            data[channel_address] = self._device_descriptions.get(interface_id, {}).get(
                channel_address, {}
            )
        return data

    def get_device_parameter(
        self, interface_id: str, device_address: str, parameter: str
    ) -> Any | None:
        """Return the device parameter by interface and device_address."""
        return (
            self._device_descriptions.get(interface_id, {}).get(device_address, {}).get(parameter)
        )

    def _convert_device_descriptions(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """Convert provided list of device descriptions."""
        for device_description in device_descriptions:
            self._convert_device_description(
                interface_id=interface_id, device_description=device_description
            )

    def _convert_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """Convert provided dict of device descriptions."""
        if interface_id not in self._addresses:
            self._addresses[interface_id] = {}
        if interface_id not in self._device_descriptions:
            self._device_descriptions[interface_id] = {}

        address = device_description[Description.ADDRESS]
        self._device_descriptions[interface_id][address] = device_description

        if ":" not in address and address not in self._addresses[interface_id]:
            self._addresses[interface_id][address] = [address]
        if ":" in address:
            device_address = get_device_address(address)
            if device_address not in self._addresses[interface_id]:
                self._addresses[interface_id][device_address] = []
            self._addresses[interface_id][device_address].append(address)

    async def load(self) -> DataOperationResult:
        """Load device data from disk into _device_description_cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching paramset descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        result = await super().load()
        for (
            interface_id,
            device_descriptions,
        ) in self._raw_device_descriptions.items():
            self._convert_device_descriptions(interface_id, device_descriptions)
        return result


class ParamsetDescriptionCache(BasePersistentCache):
    """Cache for paramset descriptions."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the paramset description cache."""
        # {interface_id, {channel_address, paramsets}}
        self._raw_paramset_descriptions: Final[
            dict[str, dict[str, dict[str, dict[str, Any]]]]
        ] = {}
        super().__init__(
            central=central,
            filename=FILE_PARAMSETS,
            persistant_cache=self._raw_paramset_descriptions,
        )

        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: Final[dict[tuple[str, str], list[int]]] = {}

    def add(
        self,
        interface_id: str,
        channel_address: str,
        paramset_key: str,
        paramset_description: dict[str, Any],
    ) -> None:
        """Add paramset description to cache."""
        if interface_id not in self._raw_paramset_descriptions:
            self._raw_paramset_descriptions[interface_id] = {}
        if channel_address not in self._raw_paramset_descriptions[interface_id]:
            self._raw_paramset_descriptions[interface_id][channel_address] = {}
        if paramset_key not in self._raw_paramset_descriptions[interface_id][channel_address]:
            self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = {}

        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = (
            paramset_description
        )

    async def remove_device(self, device: HmDevice) -> None:
        """Remove device paramset descriptions from cache."""
        if interface := self._raw_paramset_descriptions.get(device.interface_id):
            for channel_address in device.channels:
                if channel_address in interface:
                    del self._raw_paramset_descriptions[device.interface_id][channel_address]
        await self.save()

    def has_interface_id(self, interface_id: str) -> bool:
        """Return if interface is in paramset_descriptions cache."""
        return interface_id in self._raw_paramset_descriptions

    def get_paramset_keys(self, interface_id: str, channel_address: str) -> tuple[str, ...]:
        """Get paramset_keys from paramset descriptions cache."""
        return tuple(
            self._raw_paramset_descriptions.get(interface_id, {}).get(channel_address, [])
        )

    def get_paramset_descriptions(
        self, interface_id: str, channel_address: str, paramset_key: str
    ) -> dict[str, Any]:
        """Get paramset descriptions from cache."""
        return (
            self._raw_paramset_descriptions.get(interface_id, {})
            .get(channel_address, {})
            .get(paramset_key, {})
        )

    def get_parameter_data(
        self, interface_id: str, channel_address: str, paramset_key: str, parameter: str
    ) -> Any:
        """Get parameter_data  from cache."""
        return (
            self._raw_paramset_descriptions.get(interface_id, {})
            .get(channel_address, {})
            .get(paramset_key, {})
            .get(parameter)
        )

    def is_in_multiple_channels(self, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ":" not in channel_address:
            return False
        if channels := self._address_parameter_cache.get(
            (get_device_address(channel_address), parameter)
        ):
            return len(set(channels)) > 1
        return False

    def get_all_readable_parameters(self) -> tuple[str, ...]:
        """Return all readable, eventing parameters from VALUES paramset."""
        parameters: set[str] = set()
        for channels in self._raw_paramset_descriptions.values():
            for channel_address in channels:
                for parameter, paramset in channels[channel_address][ParamsetKey.VALUES].items():
                    operations = paramset[Description.OPERATIONS]
                    if operations & Operations.READ and operations & Operations.EVENT:
                        parameters.add(parameter)

        return tuple(sorted(parameters))

    def get_channel_addresses_by_paramset_key(
        self, interface_id: str, device_address: str
    ) -> dict[str, list[str]]:
        """Get device channel addresses."""
        channel_addresses: dict[str, list[str]] = {}
        interface_paramset_descriptions = self._raw_paramset_descriptions[interface_id]
        for (
            channel_address,
            paramset_descriptions,
        ) in interface_paramset_descriptions.items():
            if channel_address.startswith(device_address):
                for paramset_key in paramset_descriptions:
                    if paramset_key not in channel_addresses:
                        channel_addresses[paramset_key] = []
                    channel_addresses[paramset_key].append(channel_address)

        return channel_addresses

    def _init_address_parameter_list(self) -> None:
        """
        Initialize a device_address/parameter list.

        Used to identify, if a parameter name exists is in multiple channels.
        """
        for channel_paramsets in self._raw_paramset_descriptions.values():
            for channel_address, paramsets in channel_paramsets.items():
                device_address, channel_no = get_split_channel_address(channel_address)
                if not channel_no:
                    continue

                for paramset in paramsets.values():
                    if not paramset:
                        continue
                    for parameter in paramset:
                        if (
                            device_address,
                            parameter,
                        ) not in self._address_parameter_cache:
                            self._address_parameter_cache[(device_address, parameter)] = []
                        self._address_parameter_cache[(device_address, parameter)].append(
                            channel_no
                        )

    async def load(self) -> DataOperationResult:
        """Load paramset descriptions from disk into paramset cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching device descriptions for %s", self._central.name)
            return DataOperationResult.NO_LOAD
        result = await super().load()
        self._init_address_parameter_list()
        return result

    async def save(self) -> DataOperationResult:
        """Save current paramset descriptions to disk."""
        result = await super().save()
        self._init_address_parameter_list()
        return result
