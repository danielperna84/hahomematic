"""Module for HaHomematicExceptions."""
from __future__ import annotations

from typing import Any


class HaHomematicException(Exception):
    """hahomematic exception."""

    def __init__(self, name: str, *args: Any) -> None:
        """Init the HaHomematicException."""
        super().__init__(*args)
        self.name = name


class ProxyException(HaHomematicException):
    """hahomematic Proxy exception."""

    def __init__(self, *args: Any) -> None:
        """Init the ProxyException."""
        super().__init__("ProxyException", *args)


class NoConnection(HaHomematicException):
    """hahomematic NoConnection exception."""

    def __init__(self, *args: Any) -> None:
        """Init the NoConnection."""
        super().__init__("NoConnection", *args)
