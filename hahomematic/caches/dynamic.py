"""Module for the dynamic caches."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic import central as hmcu
from hahomematic.config import (
    LAST_COMMAND_SEND_STORE_TIMEOUT,
    PING_PONG_MISMATCH_COUNT,
    PING_PONG_MISMATCH_COUNT_TTL,
)
from hahomematic.const import (
    ENTITY_KEY,
    EVENT_DATA,
    EVENT_INSTANCE_NAME,
    EVENT_INTERFACE_ID,
    EVENT_PONG_MISMATCH_COUNT,
    EVENT_TYPE,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    CallSource,
    HomematicEventType,
    InterfaceEventType,
    InterfaceName,
    ParamsetKey,
)
from hahomematic.converter import CONVERTABLE_PARAMETERS, convert_combined_parameter_to_paramset
from hahomematic.platforms.device import HmDevice
from hahomematic.support import changed_within_seconds, get_entity_key

_LOGGER: Final = logging.getLogger(__name__)


class CommandCache:
    """Cache for send commands."""

    def __init__(self, interface_id: str) -> None:
        """Init command cache."""
        self._interface_id: Final = interface_id
        # (paramset_key, device_address, channel_no, parameter)
        self._last_send_command: Final[dict[ENTITY_KEY, tuple[Any, datetime]]] = {}

    def add_set_value(
        self,
        channel_address: str,
        parameter: str,
        value: Any,
    ) -> set[ENTITY_KEY]:
        """Add data from set value command."""
        if parameter in CONVERTABLE_PARAMETERS:
            return self.add_combined_parameter(
                parameter=parameter, channel_address=channel_address, combined_parameter=value
            )

        entity_key = get_entity_key(
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )
        self._last_send_command[entity_key] = (value, datetime.now())
        return {entity_key}

    def add_put_paramset(
        self, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> set[ENTITY_KEY]:
        """Add data from put paramset command."""
        entity_keys: set[ENTITY_KEY] = set()
        for parameter, value in values.items():
            entity_key = get_entity_key(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=parameter,
            )
            self._last_send_command[entity_key] = (value, datetime.now())
            entity_keys.add(entity_key)
        return entity_keys

    def add_combined_parameter(
        self, parameter: str, channel_address: str, combined_parameter: str
    ) -> set[ENTITY_KEY]:
        """Add data from combined parameter."""
        if values := convert_combined_parameter_to_paramset(
            parameter=parameter, cpv=combined_parameter
        ):
            return self.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey.VALUES,
                values=values,
            )
        return set()

    def get_last_value_send(
        self, entity_key: ENTITY_KEY, max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT
    ) -> Any:
        """Return the last send values."""
        if result := self._last_send_command.get(entity_key):
            value, last_send_dt = result
            if last_send_dt and changed_within_seconds(last_change=last_send_dt, max_age=max_age):
                return value
            self.remove_last_value_send(
                entity_key=entity_key,
                max_age=max_age,
            )
        return None

    def remove_last_value_send(
        self,
        entity_key: ENTITY_KEY,
        value: Any = None,
        max_age: int = LAST_COMMAND_SEND_STORE_TIMEOUT,
    ) -> None:
        """Remove the last send value."""
        if result := self._last_send_command.get(entity_key):
            stored_value, last_send_dt = result
            if not changed_within_seconds(last_change=last_send_dt, max_age=max_age) or (
                value is not None and stored_value == value
            ):
                del self._last_send_command[entity_key]


class DeviceDetailsCache:
    """Cache for device/channel details."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the device details cache."""
        self._central: Final = central
        self._channel_rooms: Final[dict[str, set[str]]] = {}
        self._device_channel_ids: Final[dict[str, str]] = {}
        self._functions: Final[dict[str, set[str]]] = {}
        self._interface_cache: Final[dict[str, str]] = {}
        self._names_cache: Final[dict[str, str]] = {}
        self._refreshed_at = INIT_DATETIME

    async def load(self, direct_call: bool = False) -> None:
        """Fetch names from backend."""
        if direct_call is False and changed_within_seconds(
            last_change=self._refreshed_at, max_age=int(MAX_CACHE_AGE / 2)
        ):
            return
        self.clear()
        _LOGGER.debug("LOAD: Loading names for %s", self._central.name)
        if client := self._central.primary_client:
            await client.fetch_device_details()
        _LOGGER.debug("LOAD: Loading rooms for %s", self._central.name)
        self._channel_rooms.clear()
        self._channel_rooms.update(await self._get_all_rooms())
        _LOGGER.debug("LOAD: Loading functions for %s", self._central.name)
        self._functions.clear()
        self._functions.update(await self._get_all_functions())
        self._refreshed_at = datetime.now()

    @property
    def device_channel_ids(self) -> Mapping[str, str]:
        """Return device channel ids."""
        return self._device_channel_ids

    def add_name(self, address: str, name: str) -> None:
        """Add name to cache."""
        self._names_cache[address] = name

    def get_name(self, address: str) -> str | None:
        """Get name from cache."""
        return self._names_cache.get(address)

    def add_interface(self, address: str, interface: str) -> None:
        """Add interface to cache."""
        self._interface_cache[address] = interface

    def get_interface(self, address: str) -> str:
        """Get interface from cache."""
        return self._interface_cache.get(address) or InterfaceName.BIDCOS_RF

    def add_address_id(self, address: str, hmid: str) -> None:
        """Add channel id for a channel."""
        self._device_channel_ids[address] = hmid

    def get_address_id(self, address: str) -> str:
        """Get id for address."""
        return self._device_channel_ids.get(address) or "0"

    async def _get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms, if available."""
        if client := self._central.primary_client:
            return await client.get_all_rooms()
        return {}

    def get_device_rooms(self, device_address: str) -> set[str]:
        """Return all rooms by device_address."""
        rooms: set[str] = set()
        for channel_address, channel_rooms in self._channel_rooms.items():
            if channel_address.startswith(device_address):
                rooms.update(channel_rooms)
        return rooms

    def get_channel_rooms(self, channel_address: str) -> set[str]:
        """Return rooms by channel_address."""
        return self._channel_rooms.get(channel_address) or set()

    async def _get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions, if available."""
        if client := self._central.primary_client:
            return await client.get_all_functions()
        return {}

    def get_function_text(self, address: str) -> str | None:
        """Return function by address."""
        if functions := self._functions.get(address):
            return ",".join(functions)
        return None

    def remove_device(self, device: HmDevice) -> None:
        """Remove name from cache."""
        if device.address in self._names_cache:
            del self._names_cache[device.address]
        for channel_address in device.channels:
            if channel_address in self._names_cache:
                del self._names_cache[channel_address]

    def clear(self) -> None:
        """Clear the cache."""
        self._names_cache.clear()
        self._channel_rooms.clear()
        self._functions.clear()
        self._refreshed_at = INIT_DATETIME


class CentralDataCache:
    """Central cache for device/channel initial data."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Init the central data cache."""
        self._central: Final = central
        # { key, value}
        self._value_cache: Final[dict[str, Any]] = {}
        self._refreshed_at = INIT_DATETIME

    @property
    def is_empty(self) -> bool:
        """Return if cache is empty."""
        if len(self._value_cache) == 0:
            return True
        if not changed_within_seconds(last_change=self._refreshed_at):
            self.clear()
            return True
        return False

    async def load(self, direct_call: bool = False) -> None:
        """Fetch data from backend."""
        if direct_call is False and changed_within_seconds(
            last_change=self._refreshed_at, max_age=int(MAX_CACHE_AGE / 2)
        ):
            return
        self.clear()
        _LOGGER.debug("load: Loading device data for %s", self._central.name)
        for client in self._central.clients:
            await client.fetch_all_device_data()

    async def refresh_entity_data(self, paramset_key: ParamsetKey | None = None) -> None:
        """Refresh entity data."""
        for entity in self._central.get_readable_generic_entities(paramset_key=paramset_key):
            await entity.load_entity_value(call_source=CallSource.HM_INIT)

    def add_data(self, all_device_data: dict[str, Any]) -> None:
        """Add data to cache."""
        self.clear()
        self._value_cache.update(all_device_data)
        self._refreshed_at = datetime.now()

    def get_data(
        self,
        interface: str,
        channel_address: str,
        parameter: str,
    ) -> Any:
        """Get data from cache."""
        if not self.is_empty:
            key = f"{interface}.{channel_address.replace(':','%3A')}.{parameter}"
            return self._value_cache.get(key, NO_CACHE_ENTRY)
        return NO_CACHE_ENTRY

    def clear(self) -> None:
        """Clear the cache."""
        self._value_cache.clear()
        self._refreshed_at = INIT_DATETIME


class PingPongCache:
    """Cache to collect ping/pong events with ttl."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        interface_id: str,
        allowed_delta: int = PING_PONG_MISMATCH_COUNT,
        ttl: int = PING_PONG_MISMATCH_COUNT_TTL,
    ):
        """Initialize the cache with ttl."""
        assert ttl > 0
        self._central: Final = central
        self._interface_id: Final = interface_id
        self._allowed_delta: Final = allowed_delta
        self._ttl: Final = ttl
        self._pending_pongs: Final[set[datetime]] = set()
        self._unknown_pongs: Final[set[datetime]] = set()
        self._pending_pong_logged: bool = False
        self._unknown_pong_logged: bool = False

    @property
    def high_pending_pongs(self) -> bool:
        """Check, if store contains too many pending pongs."""
        self._cleanup_pending_pongs()
        return len(self._pending_pongs) > self._allowed_delta

    @property
    def high_unknown_pongs(self) -> bool:
        """Check, if store contains too many unknown pongs."""
        self._cleanup_unknown_pongs()
        return len(self._unknown_pongs) > self._allowed_delta

    @property
    def low_pending_pongs(self) -> bool:
        """Return the pending pong count is low."""
        self._cleanup_pending_pongs()
        return len(self._pending_pongs) < (self._allowed_delta / 2)

    @property
    def low_unknown_pongs(self) -> bool:
        """Return the unknown pong count is low."""
        self._cleanup_unknown_pongs()
        return len(self._unknown_pongs) < (self._allowed_delta / 2)

    @property
    def pending_pong_count(self) -> int:
        """Return the pending pong count."""
        return len(self._pending_pongs)

    @property
    def unknown_pong_count(self) -> int:
        """Return the unknown pong count."""
        return len(self._unknown_pongs)

    def clear(self) -> None:
        """Clear the cache."""
        self._pending_pongs.clear()
        self._unknown_pongs.clear()
        self._pending_pong_logged = False
        self._unknown_pong_logged = False

    def handle_send_ping(self, ping_ts: datetime) -> None:
        """Handle send ping timestamp."""
        self._pending_pongs.add(ping_ts)
        self._check_and_fire_pong_event(
            event_type=InterfaceEventType.PENDING_PONG,
            pong_mismatch_count=self.pending_pong_count,
        )
        _LOGGER.debug(
            "PING PONG CACHE: Increase pending PING count: %s - %i for ts: %s",
            self._interface_id,
            self.pending_pong_count,
            ping_ts,
        )

    def handle_received_pong(self, pong_ts: datetime) -> None:
        """Handle received pong timestamp."""
        if pong_ts in self._pending_pongs:
            self._pending_pongs.remove(pong_ts)
            self._check_and_fire_pong_event(
                event_type=InterfaceEventType.PENDING_PONG,
                pong_mismatch_count=self.pending_pong_count,
            )
            _LOGGER.debug(
                "PING PONG CACHE: Reduce pending PING count: %s - %i for ts: %s",
                self._interface_id,
                self.pending_pong_count,
                pong_ts,
            )
            return

        self._unknown_pongs.add(pong_ts)
        self._check_and_fire_pong_event(
            event_type=InterfaceEventType.UNKNOWN_PONG,
            pong_mismatch_count=self.unknown_pong_count,
        )
        _LOGGER.debug(
            "PING PONG CACHE: Increase unknown PONG count: %s - %i for ts: %s",
            self._interface_id,
            self.unknown_pong_count,
            pong_ts,
        )

    def _cleanup_pending_pongs(self) -> None:
        """Cleanup too old pending pongs."""
        dt_now = datetime.now()
        for pong_ts in list(self._pending_pongs):
            delta = dt_now - pong_ts
            if delta.seconds > self._ttl:
                self._pending_pongs.remove(pong_ts)
                _LOGGER.debug(
                    "PING PONG CACHE: Removing expired pending PONG: %s - %i for ts: %s",
                    self._interface_id,
                    self.pending_pong_count,
                    pong_ts,
                )

    def _cleanup_unknown_pongs(self) -> None:
        """Cleanup too old unknown pongs."""
        dt_now = datetime.now()
        for pong_ts in list(self._unknown_pongs):
            delta = dt_now - pong_ts
            if delta.seconds > self._ttl:
                self._unknown_pongs.remove(pong_ts)
                _LOGGER.debug(
                    "PING PONG CACHE: Removing expired unknown PONG: %s - %i or ts: %s",
                    self._interface_id,
                    self.unknown_pong_count,
                    pong_ts,
                )

    def _check_and_fire_pong_event(
        self, event_type: InterfaceEventType, pong_mismatch_count: int
    ) -> None:
        """Fire an event about the pong status."""

        def _fire_event(mismatch_count: int) -> None:
            self._central.fire_homematic_callback(
                event_type=HomematicEventType.INTERFACE,
                event_data=cast(
                    dict[str, Any],
                    hmcu.INTERFACE_EVENT_SCHEMA(
                        {
                            EVENT_INTERFACE_ID: self._interface_id,
                            EVENT_TYPE: event_type,
                            EVENT_DATA: {
                                EVENT_INSTANCE_NAME: self._central.name,
                                EVENT_PONG_MISMATCH_COUNT: mismatch_count,
                            },
                        }
                    ),
                ),
            )

        if self.low_pending_pongs and event_type == InterfaceEventType.PENDING_PONG:
            _fire_event(mismatch_count=0)
            self._pending_pong_logged = False
            return

        if self.low_unknown_pongs and event_type == InterfaceEventType.UNKNOWN_PONG:
            self._unknown_pong_logged = False
            return

        if self.high_pending_pongs and event_type == InterfaceEventType.PENDING_PONG:
            _fire_event(mismatch_count=pong_mismatch_count)
            if self._pending_pong_logged is False:
                _LOGGER.warning(
                    "Pending PONG mismatch: There is a mismatch between send ping events and received pong events for HA instance %s. "
                    "Possible reason 1: You are running multiple instances of HA with the same instance name configured for this integration. "
                    "Re-add one instance! Otherwise this HA instance will not receive update events from your CCU. "
                    "Possible reason 2: Something is stuck on the CCU or hasn't been cleaned up. Therefore, try a CCU restart."
                    "Possible reason 3: Your setup is misconfigured and HA is not able to receive events from the CCU.",
                    self._interface_id,
                )
            self._pending_pong_logged = True

        if self.high_unknown_pongs and event_type == InterfaceEventType.UNKNOWN_PONG:
            if self._unknown_pong_logged is False:
                _LOGGER.warning(
                    "Unknown PONG Mismatch: Your HA instance %s receives PONG events, that it hasn't send. "
                    "Possible reason 1: You are running multiple instances of HA with the same instance name configured for this integration. "
                    "Re-add one instance! Otherwise the other HA instance will not receive update events from your CCU. "
                    "Possible reason 2: Something is stuck on the CCU or hasn't been cleaned up. Therefore, try a CCU restart.",
                    self._interface_id,
                )
            self._unknown_pong_logged = True
