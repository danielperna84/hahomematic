"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from hahomematic.platforms.decorators import (
    config_property,
    get_public_attributes_for_config_property,
    get_public_attributes_for_value_property,
    value_property,
)

# pylint: disable=protected-access


def test_generic_property() -> None:
    """Test CeSwitch."""
    test_class = PropertyTestClazz()
    assert test_class.value == "test_value"
    assert test_class.config == "test_config"
    test_class.value = "new_value"
    test_class.config = "new_config"
    assert test_class.value == "new_value"
    assert test_class.config == "new_config"
    del test_class.value
    del test_class.config
    assert test_class.value == ""
    assert test_class.config == ""


def test_generic_property_read() -> None:
    """Test CeSwitch."""
    test_class = PropertyTestClazz()
    config_attributes = get_public_attributes_for_config_property(data_object=test_class)
    assert config_attributes == {"config": "test_config"}
    value_attributes = get_public_attributes_for_value_property(data_object=test_class)
    assert value_attributes == {"value": "test_value"}


class PropertyTestClazz:
    """test class for generic_properties."""

    def __init__(self):
        """Init PropertyTestClazz."""
        self._value: str = "test_value"
        self._config: str = "test_config"

    @value_property
    def value(self) -> str:
        """Return value."""
        return self._value

    @value.setter
    def value(self, value: str) -> None:
        """Set value."""
        self._value = value

    @value.deleter
    def value(self) -> None:
        """Delete value."""
        self._value = ""

    @config_property
    def config(self) -> str:
        """Return config."""
        return self._config

    @config.setter
    def config(self, config: str) -> None:
        """Set config."""
        self._config = config

    @config.deleter
    def config(self) -> None:
        """Delete config."""
        self._config = ""
