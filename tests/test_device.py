"""Tests for devices of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_generic_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.text import HmText

TEST_DEVICES: dict[str, str] = {}


# TODO: Add device related tests, available, unreach
