"""Support for entities used within hahomematic."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, Generic, TypeVar

from hahomematic import central_unit as hmcu, support as hm_support
from hahomematic.const import (
    BINARY_SENSOR_TRUE_VALUE_DICT_FOR_VALUE_LIST,
    HM_TYPE,
    HM_VIRTUAL_REMOTE_ADDRESSES,
    INIT_DATETIME,
    PROGRAM_ADDRESS,
    SYSVAR_ADDRESS,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    HmEntityUsage,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.support import to_bool

G = TypeVar("G")  # think about variance
S = TypeVar("S")

_LOGGER = logging.getLogger(__name__)


# pylint: disable=invalid-name
class generic_property(Generic[G, S], property):
    """Generic property implementation."""

    fget: Callable[[Any], G] | None
    fset: Callable[[Any, S], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], G] | None = None,
        fset: Callable[[Any, S], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, __fget: Callable[[Any], G]) -> generic_property:
        """Return generic getter."""
        return type(self)(__fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, __fset: Callable[[Any, S], None]) -> generic_property:
        """Return generic setter."""
        return type(self)(self.fget, __fset, self.fdel, self.__doc__)

    def deleter(self, __fdel: Callable[[Any], None]) -> generic_property:
        """Return generic deleter."""
        return type(self)(self.fget, self.fset, __fdel, self.__doc__)

    def __get__(self, __obj: Any, __type: type | None = None) -> G:
        """Return the attribute."""
        if __obj is None:
            return self  # type: ignore[return-value]
        if self.fget is None:
            raise AttributeError("unreadable attribute")  # pragma: no cover
        return self.fget(__obj)

    def __set__(self, __obj: Any, __value: Any) -> None:
        """Set the attribute."""
        if self.fset is None:
            raise AttributeError("can't set attribute")  # pragma: no cover
        self.fset(__obj, __value)

    def __delete__(self, __obj: Any) -> None:
        """Delete the attribute."""
        if self.fdel is None:
            raise AttributeError("can't delete attribute")  # pragma: no cover
        self.fdel(__obj)


# pylint: disable=invalid-name
class config_property(generic_property[G, S], property):
    """Decorate to mark own config properties."""


# pylint: disable=invalid-name
class value_property(generic_property[G, S], property):
    """Decorate to mark own value properties."""


def _get_public_attributes_by_decorator(
    data_object: Any, property_decorator: type
) -> dict[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = [
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_")
        and isinstance(getattr(data_object.__class__, y), property_decorator)
    ]
    return {x: getattr(data_object, x) for x in pub_attributes}


def get_public_attributes_for_config_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=config_property
    )


def get_public_attributes_for_value_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator value_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=value_property
    )


class PayloadMixin:
    """Mixin to add payload methods to class."""

    @property
    def config_payload(self) -> dict[str, Any]:
        """Return the config payload."""
        return get_public_attributes_for_config_property(data_object=self)

    @property
    def value_payload(self) -> dict[str, Any]:
        """Return the value payload."""
        return get_public_attributes_for_value_property(data_object=self)


class OnTimeMixin:
    """Mixin to add on_time support."""

    def __init__(self) -> None:
        """Init OnTimeMixin."""
        self._on_time: float | None = None
        self._on_time_updated: datetime = INIT_DATETIME

    def set_on_time(self, on_time: float) -> None:
        """Set the on_time."""
        self._on_time = on_time
        self._on_time_updated = datetime.now()

    def get_on_time_and_cleanup(self) -> float | None:
        """Return the on_time and cleanup afterwards."""
        if self._on_time is None:
            return None
        # save values
        on_time = self._on_time
        on_time_updated = self._on_time_updated
        # cleanup values
        self._on_time = None
        self._on_time_updated = INIT_DATETIME
        if not hm_support.updated_within_seconds(last_update=on_time_updated, max_age_seconds=5):
            return None
        return on_time


class EntityNameData:
    """Dataclass for entity name parts."""

    def __init__(
        self, device_name: str, channel_name: str, parameter_name: str | None = None
    ) -> None:
        """Init the EntityNameData class."""
        self._device_name = device_name
        self._channel_name = channel_name
        self._parameter_name = parameter_name

    @staticmethod
    def empty() -> EntityNameData:
        """Return an empty EntityNameData."""
        return EntityNameData(device_name="", channel_name="")

    @property
    def entity_name(self) -> str | None:
        """Return the name of the entity only name."""
        if self._device_name and self._name and self._name.startswith(self._device_name):
            return self._name.replace(self._device_name, "").strip()
        return self._name

    @property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        if self.entity_name:
            return f"{self._device_name} {self.entity_name}".strip()
        return self._device_name

    @property
    def _name(self) -> str | None:
        """Return the name of the entity."""
        if self._channel_name and self._parameter_name:
            return f"{self._channel_name} {self._parameter_name}".strip()
        if self._channel_name:
            return self._channel_name.strip()
        return None


def get_device_name(central: hmcu.CentralUnit, device_address: str, device_type: str) -> str:
    """Return the cached name for a device, or an auto-generated."""
    if name := central.device_details.get_name(address=device_address):
        return name

    _LOGGER.debug(
        "GET_DEVICE_NAME: Using auto-generated name for %s %s",
        device_type,
        device_address,
    )
    return _get_generic_device_name(device_address=device_address, device_type=device_type)


def _get_generic_device_name(device_address: str, device_type: str) -> str:
    """Return auto-generated device name."""
    return f"{device_type}_{device_address}"


def get_entity_name(
    central: hmcu.CentralUnit,
    device: hmd.HmDevice,
    channel_no: int | None,
    parameter: str,
) -> EntityNameData:
    """Get name for entity."""
    channel_address = hm_support.get_channel_address(
        device_address=device.device_address, channel_no=channel_no
    )
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        p_name = parameter.title().replace("_", " ")

        if _check_channel_name_with_channel_no(name=channel_name):
            c_name = channel_name.split(":")[0]
            c_postfix = ""
            if central.paramset_descriptions.has_multiple_channels(
                channel_address=channel_address, parameter=parameter
            ):
                c_postfix = "" if channel_no in (0, None) else f" ch{channel_no}"
            entity_name = EntityNameData(
                device_name=device.name,
                channel_name=c_name,
                parameter_name=f"{p_name}{c_postfix}",
            )
        else:
            entity_name = EntityNameData(
                device_name=device.name,
                channel_name=channel_name,
                parameter_name=p_name,
            )
        return entity_name

    _LOGGER.debug(
        "GET_ENTITY_NAME: Using unique_identifier for %s %s %s",
        device.device_type,
        channel_address,
        parameter,
    )
    return EntityNameData.empty()


def get_event_name(
    central: hmcu.CentralUnit,
    device: hmd.HmDevice,
    channel_no: int | None,
    parameter: str,
) -> EntityNameData:
    """Get name for event."""
    channel_address = hm_support.get_channel_address(
        device_address=device.device_address, channel_no=channel_no
    )
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        p_name = parameter.title().replace("_", " ")
        if _check_channel_name_with_channel_no(name=channel_name):
            d_name = channel_name.split(":")[0]
            c_name = "" if channel_no in (0, None) else f" Channel {channel_no}"
            event_name = EntityNameData(
                device_name=device.name,
                channel_name=d_name,
                parameter_name=f"{c_name} {p_name}",
            )
        else:
            event_name = EntityNameData(
                device_name=device.name,
                channel_name=channel_name,
                parameter_name=p_name,
            )
        return event_name

    _LOGGER.debug(
        "GET_EVENT_NAME: Using unique_identifier for %s %s %s",
        device.device_type,
        channel_address,
        parameter,
    )
    return EntityNameData.empty()


def get_custom_entity_name(
    central: hmcu.CentralUnit,
    device: hmd.HmDevice,
    channel_no: int | None,
    is_only_primary_channel: bool,
    usage: HmEntityUsage,
) -> EntityNameData:
    """Get name for custom entity."""
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        if is_only_primary_channel and _check_channel_name_with_channel_no(name=channel_name):
            return EntityNameData(device_name=device.name, channel_name=channel_name.split(":")[0])
        if _check_channel_name_with_channel_no(name=channel_name):
            c_name = channel_name.split(":")[0]
            p_name = channel_name.split(":")[1]
            marker = "ch" if usage == HmEntityUsage.CE_PRIMARY else "vch"
            p_name = f"{marker}{p_name}"
            return EntityNameData(
                device_name=device.name, channel_name=c_name, parameter_name=p_name
            )
        return EntityNameData(device_name=device.name, channel_name=channel_name)

    _LOGGER.debug(
        "GET_CUSTOM_ENTITY_NAME: Using unique_identifier for %s %s %s",
        device.device_type,
        device.device_address,
        channel_no,
    )
    return EntityNameData.empty()


def generate_unique_identifier(
    central: hmcu.CentralUnit,
    address: str,
    parameter: str | None = None,
    prefix: str | None = None,
) -> str:
    """
    Build unique identifier from address and parameter.

    Central id is additionally used for heating groups.
    Prefix is used for events and buttons.
    """
    unique_identifier = address.replace(":", "_").replace("-", "_")
    if parameter:
        unique_identifier = f"{unique_identifier}_{parameter}"

    if prefix:
        unique_identifier = f"{prefix}_{unique_identifier}"
    if (
        address in (PROGRAM_ADDRESS, SYSVAR_ADDRESS)
        or address.startswith("INT000")
        or address.split(":")[0] in HM_VIRTUAL_REMOTE_ADDRESSES
    ):
        return f"{central.config.central_id}_{unique_identifier}".lower()
    return f"{unique_identifier}".lower()


def _get_base_name_from_channel_or_device(
    central: hmcu.CentralUnit,
    device: hmd.HmDevice,
    channel_no: int | None,
) -> str | None:
    """Get the name from channel if it's not default, otherwise from device."""
    channel_address = hm_support.get_channel_address(
        device_address=device.device_address, channel_no=channel_no
    )
    default_channel_name = f"{device.device_type} {channel_address}"
    name = central.device_details.get_name(channel_address)
    if name is None or name == default_channel_name:
        return hm_support.get_channel_address(device_address=device.name, channel_no=channel_no)
    return name


def _check_channel_name_with_channel_no(name: str) -> bool:
    """Check if name contains channel and this is an int."""
    if name.count(":") == 1:
        channel_part = name.split(":")[1]
        try:
            int(channel_part)
            return True
        except ValueError:
            return False
    return False


def convert_value(value: Any, target_type: str, value_list: tuple[str, ...] | None) -> Any:
    """Convert a value to target_type."""
    if value is None:
        return None
    if target_type == TYPE_BOOL:
        if value_list:
            # relevant for ENUMs retyped to a BOOL
            return _get_binary_sensor_value(value=value, value_list=value_list)
        if isinstance(value, str):
            return to_bool(value)
        return bool(value)
    if target_type == TYPE_FLOAT:
        return float(value)
    if target_type == TYPE_INTEGER:
        return int(float(value))
    if target_type == TYPE_STRING:
        return str(value)
    return value


def is_binary_sensor(parameter_data: dict[str, Any]) -> bool:
    """Check, if the sensor is a binary_sensor."""
    if parameter_data[HM_TYPE] == TYPE_BOOL:
        return True
    if value_list := parameter_data.get("VALUE_LIST"):
        return tuple(value_list) in BINARY_SENSOR_TRUE_VALUE_DICT_FOR_VALUE_LIST
    return False


def _get_binary_sensor_value(value: int, value_list: tuple[str, ...]) -> bool:
    """Return, the value of a binary_sensor."""
    try:
        str_value = value_list[value]
        if true_value := BINARY_SENSOR_TRUE_VALUE_DICT_FOR_VALUE_LIST.get(value_list):
            return str_value == true_value
    except IndexError:
        pass
    return False


def check_channel_is_the_only_primary_channel(
    current_channel_no: int | None, device_def: dict[str, Any], device_has_multiple_channels: bool
) -> bool:
    """Check if this channel is the only primary channel."""
    primary_channel: int = device_def[hmed.ED_PRIMARY_CHANNEL]
    if primary_channel == current_channel_no and device_has_multiple_channels is False:
        return True
    return False
