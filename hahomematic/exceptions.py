"""Module for HaHomematicExceptions."""
from __future__ import annotations

import re
from typing import Any

USERNAME_PASSWORD_DIVIDER = ":"
CREDENTIALS_URL_DIVIDER = "@"
REPLACE_TEXT = f"{USERNAME_PASSWORD_DIVIDER}<PASSWORD>{CREDENTIALS_URL_DIVIDER}"


class BaseHomematicException(Exception):
    """hahomematic base exception."""

    def __init__(self, name: str, *args: Any) -> None:
        """Init the HaHomematicException."""
        super().__init__(_replace_password_in_args(args))
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


class HaHomematicException(BaseHomematicException):
    """hahomematic HaHomematicException exception."""

    def __init__(self, *args: Any) -> None:
        """Init the HaHomematicException."""
        super().__init__("HaHomematicException", *args)


def _replace_password_in_args(args: Any) -> Any:
    """Replace in args."""
    if isinstance(args, str):
        return _replace_password_in_text(input_text=args)
    if isinstance(args, Exception):
        return _replace_password_in_exception(parent_exception=args)
    if isinstance(args, dict):
        return _replace_password_in_dict(input_dict=args)
    if isinstance(args, tuple):
        new_args: list[Any] = []
        for arg in args:
            if isinstance(arg, str):
                new_args.append(_replace_password_in_text(input_text=arg))
            elif isinstance(arg, Exception):
                new_args.append(_replace_password_in_exception(parent_exception=arg))
            else:
                new_args.append(arg)
        return tuple(new_args)
    return args


def _replace_password_in_exception(parent_exception: Exception) -> Exception:
    """Try replace password by special string."""
    parent_exception.__dict__.update(
        _replace_password_in_dict(parent_exception.__dict__)
    )
    return parent_exception


def _replace_password_in_dict(input_dict: dict[str, Any]) -> dict[str, Any]:
    """Try replace password in dict by special string."""

    for k, value in input_dict.items():
        if isinstance(value, str):
            input_dict[k] = _replace_password_in_text(input_text=value)
        if isinstance(value, dict):
            input_dict[k] = _replace_password_in_dict(input_dict=value)
    return input_dict


def _replace_password_in_text(input_text: str) -> str:
    """Try replace password by special string."""

    regex = f"{USERNAME_PASSWORD_DIVIDER}(.*){CREDENTIALS_URL_DIVIDER}"
    if replaced_text := re.sub(regex, REPLACE_TEXT, input_text):
        return replaced_text
    return input_text
