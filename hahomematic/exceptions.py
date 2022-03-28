"""Module for HaHomematicExceptions."""
from __future__ import annotations

from typing import Any


class BaseHomematicException(Exception):
    """hahomematic base exception."""

    def __init__(self, name: str, *args: Any) -> None:
        """Init the HaHomematicException."""
        super().__init__(*args)
        self.name = name


class ProxyException(BaseHomematicException):
    """hahomematic Proxy exception."""

    def __init__(self, *args: Any) -> None:
        """Init the ProxyException."""
        super().__init__("ProxyException", *args)


class NoConnection(BaseHomematicException):
    """hahomematic NoConnection exception."""

    def __init__(self, *args: Any) -> None:
        """Init the NoConnection."""
        super().__init__("NoConnection", *args)


class NoClients(BaseHomematicException):
    """hahomematic NoClients exception."""

    def __init__(self, *args: Any) -> None:
        """Init the NoClients."""
        super().__init__("NoClients", *args)


class AuthFailure(BaseHomematicException):
    """hahomematic AuthFailure exception."""

    def __init__(self, *args: Any) -> None:
        """Init the AuthFailure."""
        super().__init__("AuthFailure", *args)


class HaHomematicException(BaseHomematicException):
    """hahomematic HaHomematicException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the HaHomematicException."""
        super().__init__("HaHomematicException", *args)
