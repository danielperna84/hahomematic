"""Module for HaHomematicExceptions."""
from __future__ import annotations


class HaHomematicException(Exception):
    """hahomematic exception."""


class ProxyException(HaHomematicException):
    """hahomematic Proxy exception."""


class NoConnection(HaHomematicException):
    """hahomematic NoConnection exception."""
