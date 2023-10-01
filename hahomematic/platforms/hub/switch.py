"""
Module for hub entities implemented using the switch platform.

See https://www.home-assistant.io/integrations/switch/.
"""
from __future__ import annotations

from hahomematic.const import Platform
from hahomematic.platforms.hub.entity import GenericSystemVariable


class HmSysvarSwitch(GenericSystemVariable):
    """Implementation of a sysvar switch entity."""

    _platform = Platform.HUB_SWITCH
    _is_extended = True
