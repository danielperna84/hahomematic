"""Module for HaHomematicExceptions."""
from __future__ import annotations

from typing import Any


class BaseHomematicException(Exception):
    """hahomematic base exception."""

    def __init__(self, name: str, *args: Any) -> None:
        """Init the HaHomematicException."""
        if isinstance(args[0], BaseException):
            self.name = args[0].__class__.__name__
            args = args[0].args
        else:
            self.name = name
        super().__init__(*args)


class ClientException(BaseHomematicException):
    """hahomematic Client exception."""

    def __init__(self, *args: Any) -> None:
        """Init the ClientException."""
        super().__init__("ClientException", *args)


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
