"""Generic python representation of a CCU parameter."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from hahomematic.const import CallSource, EntityUsage, EventType, Parameter, ParamsetKey
from hahomematic.platforms import device as hmd, entity as hme
from hahomematic.platforms.decorators import config_property
from hahomematic.platforms.support import EntityNameData, get_entity_name

_LOGGER: Final = logging.getLogger(__name__)


class GenericEntity(hme.BaseParameterEntity[hme.ParameterT, hme.InputParameterT]):
    """Base class for generic entities."""

    _validate_state_change: bool = True
    is_hmtype: Final = True

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_id: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: Mapping[str, Any],
    ) -> None:
        """Init the generic entity."""
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @config_property
    def usage(self) -> EntityUsage:
        """Return the entity usage."""
        if self._is_forced_sensor or self._is_un_ignored:
            return EntityUsage.ENTITY
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._usage
        return EntityUsage.ENTITY if force_enabled else EntityUsage.NO_CREATE

    def event(self, value: Any) -> None:
        """Handle event for which this entity has subscribed."""

        old_value, new_value = self.write_value(value=value)
        if old_value == new_value:
            return

        # reload paramset_descriptions, if value has changed
        if (
            self._parameter == Parameter.CONFIG_PENDING
            and new_value is False
            and old_value is True
        ):
            self._central.create_task(
                self._device.reload_paramset_descriptions(), name="reloadParamsetDescriptions"
            )

            for entity in self._device.get_readable_entities(paramset_key=ParamsetKey.MASTER):
                self._central.create_task(
                    entity.load_entity_value(
                        call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True
                    ),
                    name="reloadMasterData",
                )

        # send device availability events
        if self._parameter in (
            Parameter.UN_REACH,
            Parameter.STICKY_UN_REACH,
        ):
            self._device.fire_update_device_callback(self._unique_id)
            self._central.fire_ha_event_callback(
                event_type=EventType.DEVICE_AVAILABILITY,
                event_data=self.get_event_data(new_value),
            )

    async def send_value(
        self,
        value: hme.InputParameterT,
        collector: hme.CallParameterCollector | None = None,
        collector_order: int = 50,
        do_validate: bool = True,
    ) -> None:
        """Send value to ccu, or use collector if set."""
        if not self.is_writeable:
            _LOGGER.error(
                "SEND_VALUE: writing to non-writable entity %s is not possible", self.full_name
            )
            return
        try:
            prepared_value = self._prepare_value_for_sending(value=value, do_validate=do_validate)
        except ValueError as verr:
            _LOGGER.warning(verr)
            return

        converted_value = self._convert_value(value=prepared_value)
        if collector:
            collector.add_entity(self, value=converted_value, collector_order=collector_order)
            return

        if self._validate_state_change and not self.is_state_change(value=converted_value):
            return

        await self._client.set_value(
            channel_address=self._channel_address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
            value=converted_value,
        )

    def _prepare_value_for_sending(
        self, value: hme.InputParameterT, do_validate: bool = True
    ) -> hme.ParameterT:
        """Prepare value, if required, before send."""
        return value  # type: ignore[return-value]

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_entity_name(
            central=self._central,
            device=self._device,
            channel_no=self.channel_no,
            parameter=self._parameter,
        )

    def _get_entity_usage(self) -> EntityUsage:
        """Generate the usage for the entity."""
        if self._central.parameter_visibility.parameter_is_hidden(
            device_type=self._device.device_type,
            channel_no=self.channel_no,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        ):
            return EntityUsage.NO_CREATE

        return (
            EntityUsage.NO_CREATE
            if self._device.has_custom_entity_definition
            else EntityUsage.ENTITY
        )

    def is_state_change(self, value: hme.ParameterT) -> bool:
        """
        Check if the state/value changes.

        If the state is uncertain, the state should also marked as changed.
        """
        if value != self._value:
            return True
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False
