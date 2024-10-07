"""
Module for entities implemented using the update platform.

See https://www.home-assistant.io/integrations/update/.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from hahomematic.const import (
    CALLBACK_TYPE,
    DEFAULT_CUSTOM_ID,
    HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES,
    HMIP_FIRMWARE_UPDATE_READY_STATES,
    HmPlatform,
    InterfaceName,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.decorators import config_property, get_service_calls, state_property
from hahomematic.platforms.entity import CallbackEntity
from hahomematic.platforms.support import PayloadMixin, generate_unique_id

__all__ = ["HmUpdate"]


class HmUpdate(CallbackEntity, PayloadMixin):
    """
    Implementation of a update.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.UPDATE

    def __init__(self, device: hmd.HmDevice) -> None:
        """Init the callback entity."""
        PayloadMixin.__init__(self)
        self._device: Final = device
        super().__init__(
            central=device.central,
            unique_id=generate_unique_id(
                central=device.central, address=device.address, parameter="Update"
            ),
        )
        self._set_modified_at()
        self._service_methods = get_service_calls(obj=self)

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def device(self) -> hmd.HmDevice:
        """Return the device of the entity."""
        return self._device

    @property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        return f"{self._device.name} Update"

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return "Update"

    @state_property
    def firmware(self) -> str | None:
        """Version installed and in use."""
        return self._device.firmware

    @state_property
    def firmware_update_state(self) -> str | None:
        """Latest version available for install."""
        return self._device.firmware_update_state

    @state_property
    def in_progress(self) -> bool:
        """Update installation progress."""
        if self._device.interface == InterfaceName.HMIP_RF:
            return self._device.firmware_update_state in HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES
        return False

    @state_property
    def latest_firmware(self) -> str | None:
        """Latest firmware available for install."""
        if self._device.available_firmware and (
            (
                self._device.interface == InterfaceName.HMIP_RF
                and self._device.firmware_update_state in HMIP_FIRMWARE_UPDATE_READY_STATES
            )
            or self._device.interface in (InterfaceName.BIDCOS_RF, InterfaceName.BIDCOS_WIRED)
        ):
            return self._device.available_firmware
        return self._device.firmware

    @property
    def path(self) -> str:
        """Return the path of the entity."""
        return f"{self._device.path}/{HmPlatform.UPDATE}"

    def register_entity_updated_callback(self, cb: Callable, custom_id: str) -> CALLBACK_TYPE:
        """Register update callback."""
        if custom_id != DEFAULT_CUSTOM_ID:
            if self._custom_id is not None:
                raise HaHomematicException(
                    f"REGISTER_UPDATE_CALLBACK failed: hm_entity: {self.full_name} is already registered by {self._custom_id}"
                )
            self._custom_id = custom_id

        if self._device.register_firmware_update_callback(cb) is not None:
            return partial(self._unregister_entity_updated_callback, cb=cb, custom_id=custom_id)
        return None

    def _unregister_entity_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        if custom_id is not None:
            self._custom_id = None
        self._device.unregister_firmware_update_callback(cb)

    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Turn the update on."""
        return await self._device.update_firmware(
            refresh_after_update_intervals=refresh_after_update_intervals
        )

    async def refresh_firmware_data(self) -> None:
        """Refresh device firmware data."""
        await self._device.central.refresh_firmware_data(device_address=self._device.address)
        self._set_modified_at()
