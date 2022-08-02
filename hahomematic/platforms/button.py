"""
Module for entities implemented using the
button platform (https://www.home-assistant.io/integrations/button/).
"""
from __future__ import annotations

import logging
from typing import Any, Final

import hahomematic.central_unit as hm_central
from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, GenericHubEntity
from hahomematic.helpers import HubData, ProgramData

_LOGGER = logging.getLogger(__name__)


class HmButton(GenericEntity[None]):
    """
    Implementation of a button.
    This is a default platform that gets automatically generated.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.BUTTON,
        )

    async def press(self) -> None:
        """Handle the button press."""
        await self.send_value(True)


class HmProgramButton(GenericHubEntity):
    """Class for a homematic program button."""

    def __init__(
        self,
        central: hm_central.CentralUnit,
        data: ProgramData,
    ):
        """
        Initialize the entity.
        """
        super().__init__(central=central, data=data, platform=HmPlatform.HUB_BUTTON)
        self.pid: Final[str] = data.pid
        self.ccu_program_name: Final[str] = data.name
        self.is_active: bool = data.is_active
        self.is_internal: bool = data.is_internal
        self.last_execute_time: str = data.last_execute_time

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.is_active

    def get_name(self, data: HubData) -> str:
        """Return the name of the program button entity."""
        return f"P_{data.name}"

    def update_data(self, data: ProgramData) -> None:
        """Set variable value on CCU/Homegear."""
        do_update: bool = False
        if self.is_active != data.is_active:
            self.is_active = data.is_active
            do_update = True
        if self.is_internal != data.is_internal:
            self.is_internal = data.is_internal
            do_update = True
        if self.last_execute_time != data.last_execute_time:
            self.last_execute_time = data.last_execute_time
            do_update = True
        if do_update:
            self.update_entity()

    async def press(self) -> None:
        """Handle the button press."""
        await self.central.execute_program(pid=self.pid)
