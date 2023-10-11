"""Functions for entity creation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime
from functools import wraps
from inspect import getfullargspec
import logging
from typing import Any, Final, Generic, TypeVar, cast

import voluptuous as vol

from hahomematic import central as hmcu, client as hmcl, support as hms
from hahomematic.const import (
    EVENT_ADDRESS,
    EVENT_CHANNEL_NO,
    EVENT_DEVICE_TYPE,
    EVENT_INTERFACE_ID,
    EVENT_PARAMETER,
    EVENT_VALUE,
    INIT_DATETIME,
    KEY_CHANNEL_OPERATION_MODE_VISIBILITY,
    NO_CACHE_ENTRY,
    CallSource,
    Description,
    EntityUsage,
    Flag,
    HmPlatform,
    Operations,
    Parameter,
    ParameterType,
    ParamsetKey,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.support import (
    EntityNameData,
    PayloadMixin,
    convert_value,
    generate_channel_unique_identifier,
)

_LOGGER: Final = logging.getLogger(__name__)

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

_CONFIGURABLE_CHANNEL: Final[tuple[str, ...]] = (
    "KEY_TRANSCEIVER",
    "MULTI_MODE_INPUT_TRANSMITTER",
)
_DEFAULT_CUSTOM_IDENTIFIER: Final = "DEFAULT_CUSTOM_IDENTIFIER"

_FIX_UNIT_REPLACE: Final[Mapping[str, str]] = {
    '"': "",
    "100%": "%",
    "% rF": "%",
    "degree": "°C",
    "Lux": "lx",
    "m3": "m³",
}

_FIX_UNIT_BY_PARAM: Final[Mapping[str, str]] = {
    "ACTUAL_TEMPERATURE": "°C",
    "CURRENT_ILLUMINATION": "lx",
    "HUMIDITY": "%",
    "ILLUMINATION": "lx",
    "LEVEL": "%",
    "MASS_CONCENTRATION_PM_10_24H_AVERAGE": "µg/m³",
    "MASS_CONCENTRATION_PM_1_24H_AVERAGE": "µg/m³",
    "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE": "µg/m³",
    "OPERATING_VOLTAGE": "V",
    "RSSI_DEVICE": "dBm",
    "RSSI_PEER": "dBm",
    "SUNSHINEDURATION": "min",
    "WIND_DIRECTION": "°",
    "WIND_DIRECTION_RANGE": "°",
}

EVENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_ADDRESS): str,
        vol.Required(EVENT_CHANNEL_NO): int,
        vol.Required(EVENT_DEVICE_TYPE): str,
        vol.Required(EVENT_INTERFACE_ID): str,
        vol.Required(EVENT_PARAMETER): str,
        vol.Optional(EVENT_VALUE): vol.Any(bool, int),
    }
)


class CallbackEntity(ABC):
    """Base class for callback entities."""

    _platform: HmPlatform

    def __init__(self, central: hmcu.CentralUnit, unique_identifier: str) -> None:
        """Init the callback entity."""
        self._central: Final = central
        self._unique_identifier: Final = unique_identifier
        self._update_callbacks: dict[Callable, str] = {}
        self._remove_callbacks: list[Callable] = []
        self._custom_identifier: str | None = None

    @property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @property
    def custom_identifier(self) -> str | None:
        """Return the central unit."""
        return self._custom_identifier

    @property
    def central(self) -> hmcu.CentralUnit:
        """Return the central unit."""
        return self._central

    @config_property
    @abstractmethod
    def full_name(self) -> str:
        """Return the full name of the entity."""

    @config_property
    @abstractmethod
    def name(self) -> str | None:
        """Return the name of the entity."""

    @config_property
    def platform(self) -> HmPlatform:
        """Return, the platform of the entity."""
        return self._platform

    @config_property
    def unique_identifier(self) -> str:
        """Return the unique_identifier."""
        return self._unique_identifier

    @config_property
    def usage(self) -> EntityUsage:
        """Return the entity usage."""
        return EntityUsage.ENTITY

    @config_property
    def enabled_default(self) -> bool:
        """Return, if entity should be enabled based on usage attribute."""
        return self.usage in (
            EntityUsage.CE_PRIMARY,
            EntityUsage.ENTITY,
            EntityUsage.EVENT,
        )

    @property
    def is_registered_externally(self) -> bool:
        """Return if entity is registered externally."""
        return self._custom_identifier is not None

    def register_internal_update_callback(self, update_callback: Callable) -> None:
        """Register internal update callback."""
        self.register_update_callback(
            update_callback=update_callback, custom_identifier=_DEFAULT_CUSTOM_IDENTIFIER
        )

    def register_update_callback(self, update_callback: Callable, custom_identifier: str) -> None:
        """Register update callback."""
        if callable(update_callback):
            self._update_callbacks[update_callback] = custom_identifier
        if custom_identifier != _DEFAULT_CUSTOM_IDENTIFIER:
            if self._custom_identifier is not None:
                raise HaHomematicException(
                    f"REGISTER_UPDATE_CALLBACK failed: hm_entity: {self.full_name} is already registered by {self._custom_identifier}"
                )
            self._custom_identifier = custom_identifier

    def unregister_internal_update_callback(self, update_callback: Callable) -> None:
        """Unregister update callback."""
        self.unregister_update_callback(
            update_callback=update_callback, custom_identifier=_DEFAULT_CUSTOM_IDENTIFIER
        )

    def unregister_update_callback(
        self, update_callback: Callable, custom_identifier: str
    ) -> None:
        """Unregister update callback."""
        if update_callback in self._update_callbacks:
            del self._update_callbacks[update_callback]
        if self.custom_identifier == custom_identifier:
            self._custom_identifier = None

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """Register the remove callback."""
        if callable(remove_callback) and remove_callback not in self._remove_callbacks:
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """Unregister the remove callback."""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def update_entity(self, *args: Any, **kwargs: Any) -> None:
        """Do what is needed when the value of the entity has been updated."""
        for _callback in self._update_callbacks:
            _callback(*args, **kwargs)

    def remove_entity(self, *args: Any) -> None:
        """Do what is needed when the entity has been removed."""
        for _callback in self._remove_callbacks:
            _callback(*args)


class BaseEntity(CallbackEntity, PayloadMixin):
    """Base class for regular entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_no: int | None,
        is_in_multiple_channels: bool,
    ) -> None:
        """Initialize the entity."""
        PayloadMixin.__init__(self)
        super().__init__(central=device.central, unique_identifier=unique_identifier)
        self._device: Final[hmd.HmDevice] = device
        self._channel_no: Final = channel_no
        self._channel_address: Final[str] = hms.get_channel_address(
            device_address=device.device_address, channel_no=channel_no
        )
        self._channel_unique_identifier: Final = generate_channel_unique_identifier(
            central=device.central, address=self._channel_address
        )
        self._is_in_multiple_channels: Final = is_in_multiple_channels
        self._channel_type: Final = str(device.channels[self._channel_address].type)
        self._function: Final = self._central.device_details.get_function_text(
            address=self._channel_address
        )
        self._client: Final[hmcl.Client] = device.central.get_client(
            interface_id=device.interface_id
        )

        self._usage: EntityUsage = self._get_entity_usage()
        entity_name_data: Final = self._get_entity_name()
        self._channel_name: Final = entity_name_data.channel_name
        self._full_name: Final = entity_name_data.full_name
        self._name: Final = entity_name_data.entity_name

    @property
    def address_path(self) -> str:
        """Return the address pass of the entity."""
        return f"{self._platform}/{self._device.interface_id}/{self._unique_identifier}/"

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @config_property
    def channel_address(self) -> str:
        """Return the channel_address of the entity."""
        return self._channel_address

    @config_property
    def channel_name(self) -> str:
        """Return the channel_name of the entity."""
        return self._channel_name

    @config_property
    def channel_no(self) -> int | None:
        """Return the channel_no of the entity."""
        return self._channel_no

    @config_property
    def channel_unique_identifier(self) -> str:
        """Return the channel_unique_identifier of the entity."""
        return self._channel_unique_identifier

    @property
    def device(self) -> hmd.HmDevice:
        """Return the device of the entity."""
        return self._device

    @config_property
    def function(self) -> str | None:
        """Return the function of the entity."""
        return self._function

    @config_property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        return self._full_name

    @config_property
    def is_in_multiple_channels(self) -> bool:
        """Return the parameter/CE is also in multiple channels."""
        return self._is_in_multiple_channels

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._name

    @config_property
    def usage(self) -> EntityUsage:
        """Return the entity usage."""
        return self._usage

    def set_usage(self, usage: EntityUsage) -> None:
        """Set the entity usage."""
        self._usage = usage

    def update_entity(self, *args: Any, **kwargs: Any) -> None:
        """Do what is needed when the value of the entity has been updated."""
        super().update_entity(*args, **kwargs)
        self._central.fire_entity_data_event_callback(
            interface_id=self._device.interface_id, entity=self
        )

    @abstractmethod
    async def load_entity_value(self, call_source: CallSource) -> None:
        """Init the entity data."""

    @abstractmethod
    def _get_entity_name(self) -> EntityNameData:
        """Generate the name for the entity."""

    @abstractmethod
    def _get_entity_usage(self) -> EntityUsage:
        """Generate the usage for the entity."""

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address_path: {self.address_path}, type: {self._device.device_type}, "
            f"name: {self.full_name}"
        )


InputParameterT = TypeVar("InputParameterT", bool, int, float, str, int | str, float | str, None)
ParameterT = TypeVar("ParameterT", bool, int, float, str, int | str, None)


class BaseParameterEntity(Generic[ParameterT, InputParameterT], BaseEntity):
    """Base class for stateless entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: Mapping[str, Any],
    ) -> None:
        """Initialize the entity."""
        self._paramset_key: Final[str] = paramset_key
        # required for name in BaseEntity
        self._parameter: Final[str] = parameter

        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_no=hms.get_channel_no(address=channel_address),
            is_in_multiple_channels=device.central.paramset_descriptions.is_in_multiple_channels(
                channel_address=channel_address, parameter=parameter
            ),
        )
        self._value: ParameterT | None = None
        self._last_update: datetime = INIT_DATETIME
        self._state_uncertain: bool = True
        self._assign_parameter_data(parameter_data=parameter_data)

    def _assign_parameter_data(self, parameter_data: Mapping[str, Any]) -> None:
        """Assign parameter data to instance variables."""
        self._type: ParameterType = ParameterType(parameter_data[Description.TYPE])
        self._values = (
            tuple(parameter_data[Description.VALUE_LIST])
            if Description.VALUE_LIST in parameter_data
            else None
        )
        self._max: ParameterT = self._convert_value(parameter_data[Description.MAX])
        self._min: ParameterT = self._convert_value(parameter_data[Description.MIN])
        self._default: ParameterT = self._convert_value(
            parameter_data.get(Description.DEFAULT, self._min)
        )
        flags: int = parameter_data[Description.FLAGS]
        self._visible: bool = flags & Flag.VISIBLE == Flag.VISIBLE
        self._service: bool = flags & Flag.SERVICE == Flag.SERVICE
        self._operations: int = parameter_data[Description.OPERATIONS]
        self._special: Mapping[str, Any] | None = parameter_data.get(Description.SPECIAL)
        self._raw_unit: str | None = parameter_data.get(Description.UNIT)
        self._unit: str | None = self._fix_unit(raw_unit=self._raw_unit)

    @config_property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @config_property
    def hmtype(self) -> ParameterType:
        """Return the HomeMatic type."""
        return self._type

    @config_property
    def is_unit_fixed(self) -> bool:
        """Return if the unit is fixed."""
        return self._raw_unit != self._unit

    @config_property
    def max(self) -> ParameterT:
        """Return max value."""
        return self._max

    @config_property
    def min(self) -> ParameterT:
        """Return min value."""
        return self._min

    @config_property
    def multiplier(self) -> int:
        """Return multiplier value."""
        return 100 if self._raw_unit and self._raw_unit == "100%" else 1

    @config_property
    def parameter(self) -> str:
        """Return parameter name."""
        return self._parameter

    @config_property
    def paramset_key(self) -> str:
        """Return paramset_key name."""
        return self._paramset_key

    @config_property
    def raw_unit(self) -> str | None:
        """Return raw unit value."""
        return self._raw_unit

    @property
    def is_readable(self) -> bool:
        """Return, if entity is readable."""
        return bool(self._operations & Operations.READ)

    @value_property
    def is_valid(self) -> bool:
        """Return, if the value of the entity is valid based on the last updated datetime."""
        return self._last_update > INIT_DATETIME

    @property
    def is_writeable(self) -> bool:
        """Return, if entity is writeable."""
        return bool(self._operations & Operations.WRITE)

    @value_property
    def last_update(self) -> datetime:
        """Return the last updated datetime value."""
        return self._last_update

    @value_property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @value_property
    def value(self) -> ParameterT | None:
        """Return the value of the entity."""
        return self._value

    @property
    def supports_events(self) -> bool:
        """Return, if entity is supports events."""
        return bool(self._operations & Operations.EVENT)

    @config_property
    def unit(self) -> str | None:
        """Return unit value."""
        return self._unit

    @value_property
    def values(self) -> tuple[str, ...] | None:
        """Return the values."""
        return self._values

    @property
    def visible(self) -> bool:
        """Return the if entity is visible in ccu."""
        return self._visible

    @property
    def _channel_operation_mode(self) -> str | None:
        """Return the channel operation mode if available."""
        cop: BaseParameterEntity | None = self._device.get_generic_entity(
            channel_address=self._channel_address, parameter=Parameter.CHANNEL_OPERATION_MODE
        )
        if cop and cop.value:
            return str(cop.value)
        return None

    @property
    def _enabled_by_channel_operation_mode(self) -> bool | None:
        """Return, if the entity/event must be enabled."""
        if self._channel_type not in _CONFIGURABLE_CHANNEL:
            return None
        if self._parameter not in KEY_CHANNEL_OPERATION_MODE_VISIBILITY:
            return None
        if (cop := self._channel_operation_mode) is None:
            return None
        return cop in KEY_CHANNEL_OPERATION_MODE_VISIBILITY[self._parameter]

    def _fix_unit(self, raw_unit: str | None) -> str | None:
        """Replace given unit."""
        if new_unit := _FIX_UNIT_BY_PARAM.get(self._parameter):
            return new_unit
        if not raw_unit:
            return None
        for check, fix in _FIX_UNIT_REPLACE.items():
            if check in raw_unit:
                return fix
        return raw_unit

    @abstractmethod
    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""

    async def load_entity_value(self, call_source: CallSource) -> None:
        """Init the entity data."""
        if hms.updated_within_seconds(last_update=self._last_update):
            return

        # Check, if entity is readable
        if not self.is_readable:
            return

        self.update_value(
            value=await self._device.value_cache.get_value(
                channel_address=self._channel_address,
                paramset_key=self._paramset_key,
                parameter=self._parameter,
                call_source=call_source,
            )
        )

    def update_value(self, value: Any) -> None:
        """Update value of the entity."""
        if value == NO_CACHE_ENTRY:
            if self.last_update != INIT_DATETIME:
                self._state_uncertain = True
                self.update_entity()
            return
        self._value = self._convert_value(value)
        self._state_uncertain = False
        self._set_last_update()
        self.update_entity()

    def update_parameter_data(self) -> None:
        """Update parameter data."""
        self._assign_parameter_data(
            parameter_data=self._central.paramset_descriptions.get_parameter_data(
                interface_id=self._device.interface_id,
                channel_address=self._channel_address,
                paramset_key=self._paramset_key,
                parameter=self._parameter,
            )
        )

    def _convert_value(self, value: Any) -> ParameterT:
        """Convert to value to ParameterT."""
        if value is None:
            return None  # type: ignore[return-value]
        try:
            if (
                self._type == ParameterType.BOOL
                and self._values is not None
                and value is not None
                and isinstance(value, str)
            ):
                return convert_value(  # type: ignore[no-any-return]
                    value=self._values.index(value),
                    target_type=self._type,
                    value_list=self.values,
                )
            return convert_value(  # type: ignore[no-any-return]
                value=value, target_type=self._type, value_list=self.values
            )
        except ValueError:  # pragma: no cover
            _LOGGER.debug(
                "CONVERT_VALUE: conversion failed for %s, %s, %s, value: [%s]",
                self._device.interface_id,
                self._channel_address,
                self._parameter,
                value,
            )
            return None  # type: ignore[return-value]

    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""
        event_data = {
            EVENT_ADDRESS: self._device.device_address,
            EVENT_CHANNEL_NO: self._channel_no,
            EVENT_DEVICE_TYPE: self._device.device_type,
            EVENT_INTERFACE_ID: self._device.interface_id,
            EVENT_PARAMETER: self._parameter,
        }
        if value is not None:
            event_data[EVENT_VALUE] = value
        return cast(dict[str, Any], EVENT_DATA_SCHEMA(event_data))

    def _set_last_update(self) -> None:
        """Set last_update to current datetime."""
        self._last_update = datetime.now()


class CallParameterCollector:
    """Create a Paramset based on given generic entities."""

    def __init__(self, client: hmcl.Client) -> None:
        """Init the generator."""
        self._client: Final = client
        self._use_put_paramset: bool = True
        self._paramsets: Final[dict[str, dict[str, Any]]] = {}

    def add_entity(
        self, entity: BaseParameterEntity, value: Any, use_put_paramset: bool = True
    ) -> None:
        """Add a generic entity."""
        if use_put_paramset is False:
            self._use_put_paramset = False
        if entity.channel_address not in self._paramsets:
            self._paramsets[entity.channel_address] = {}
        self._paramsets[entity.channel_address][entity.parameter] = value

    async def send_data(self) -> bool:
        """Send data to backend."""
        for channel_address, paramset in self._paramsets.items():
            if len(paramset.values()) == 1 or self._use_put_paramset is False:
                for parameter, value in paramset.items():
                    if not await self._client.set_value(
                        channel_address=channel_address,
                        paramset_key=ParamsetKey.VALUES,
                        parameter=parameter,
                        value=value,
                    ):
                        return False  # pragma: no cover
            elif not await self._client.put_paramset(
                address=channel_address, paramset_key=ParamsetKey.VALUES, value=paramset
            ):
                return False  # pragma: no cover
        return True


def bind_collector(func: _CallableT) -> _CallableT:
    """Decorate function to automatically add collector if not set."""
    argument_name = "collector"
    argument_index = getfullargspec(func).args.index(argument_name)

    @wraps(func)
    async def wrapper_collector(*args: Any, **kwargs: Any) -> Any:
        """Wrap method to add collector."""
        try:
            collector_exists = args[argument_index] is not None
        except IndexError:
            collector_exists = kwargs.get(argument_name) is not None

        if collector_exists:
            return_value = await func(*args, **kwargs)
        else:
            collector = CallParameterCollector(client=args[0].device.client)
            kwargs[argument_name] = collector
            return_value = await func(*args, **kwargs)
            await collector.send_data()
        return return_value

    return wrapper_collector  # type: ignore[return-value]
