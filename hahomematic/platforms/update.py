"""
Module for entities implemented using the update platform.

See https://www.home-assistant.io/integrations/update/.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from hahomematic.const import CALLBACK_TYPE, HmPlatform
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.entity import DEFAULT_CUSTOM_ID, CallbackEntity
from hahomematic.platforms.support import generate_unique_id


class HmUpdate(CallbackEntity):
    """
    Implementation of a update.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.UPDATE

    def __init__(self, device: hmd.HmDevice) -> None:
        """Init the callback entity."""
        self._device: Final = device
        super().__init__(
            central=device.central,
            unique_id=generate_unique_id(
                central=device.central, address=device.device_address, parameter="Update"
            ),
        )
        self._set_last_updated()

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def device(self) -> hmd.HmDevice:
        """Return the device of the entity."""
        return self._device

    @config_property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        return f"{self._device.name} Update"

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return "Update"

    @value_property
    def firmware(self) -> str | None:
        """Version installed and in use."""
        return self._device.firmware

    @value_property
    def available_firmware(self) -> str | None:
        """Latest version available for install."""
        return self._device.available_firmware

    @value_property
    def firmware_update_state(self) -> str | None:
        """Latest version available for install."""
        return self._device.firmware_update_state

    def register_entity_updated_callback(
        self, entity_updated_callback: Callable, custom_id: str
    ) -> CALLBACK_TYPE:
        """Register update callback."""
        self._device.register_firmware_update_callback(entity_updated_callback)
        if custom_id != DEFAULT_CUSTOM_ID:
            if self._custom_id is not None:
                raise HaHomematicException(
                    f"REGISTER_UPDATE_CALLBACK failed: hm_entity: {self.full_name} is already registered by {self._custom_id}"
                )
            self._custom_id = custom_id
        return partial(self._unregister_entity_updated_callback, entity_updated_callback)

    def _unregister_entity_updated_callback(
        self, entity_updated_callback: Callable, custom_id: str
    ) -> None:
        """Unregister update callback."""
        self._device.unregister_firmware_update_callback(entity_updated_callback)
        if custom_id is not None:
            self._custom_id = None

    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Turn the update on."""
        return await self._device.update_firmware(
            refresh_after_update_intervals=refresh_after_update_intervals
        )

    async def refresh_firmware_data(self) -> None:
        """Refresh device firmware data."""
        await self._device.central.refresh_firmware_data(
            device_address=self._device.device_address
        )
        self._set_last_updated()
