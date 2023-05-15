"""
Module for entities implemented using the update platform.

See https://www.home-assistant.io/integrations/update/.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Final

from hahomematic.const import HmPlatform
from hahomematic.platforms import device as hmd
from hahomematic.platforms.entity import CallbackEntity
from hahomematic.platforms.support import (
    config_property,
    generate_unique_identifier,
    value_property,
)


class HmUpdate(CallbackEntity):
    """
    Implementation of a update.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.UPDATE

    def __init__(self, device: hmd.HmDevice) -> None:
        """Init the callback entity."""
        self.device: Final = device
        super().__init__(
            unique_identifier=generate_unique_identifier(
                central=device.central, address=device.device_address, parameter="Update"
            )
        )

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.device.available

    @config_property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        return f"{self.device.name} Update"

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return "Update"

    @value_property
    def firmware(self) -> str | None:
        """Version installed and in use."""
        return self.device.firmware

    @value_property
    def available_firmware(self) -> str | None:
        """Latest version available for install."""
        return self.device.available_firmware

    @value_property
    def firmware_update_state(self) -> str | None:
        """Latest version available for install."""
        return self.device.firmware_update_state

    def register_update_callback(self, update_callback: Callable) -> None:
        """Register update callback."""
        self.device.register_firmware_update_callback(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """Unregister update callback."""
        self.device.unregister_firmware_update_callback(update_callback)

    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Turn the update on."""
        return await self.device.update_firmware(
            refresh_after_update_intervals=refresh_after_update_intervals
        )

    async def refresh_firmware_data(self) -> None:
        """Refresh device firmware data."""
        await self.device.central.refresh_firmware_data(device_address=self.device.device_address)
