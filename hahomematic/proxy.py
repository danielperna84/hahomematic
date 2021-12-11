"""
Implementation of a locking ServerProxy for XML-RPC communication.
"""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any
import xmlrpc.client

from hahomematic.const import ATTR_TLS, ATTR_VERIFY_TLS
from hahomematic.helpers import get_tls_context

_LOGGER = logging.getLogger(__name__)

ATTR_CONTEXT = "context"
ATTR_ENCODING_ISO_8859_1 = "ISO-8859-1"


class ProxyException(Exception):
    """hahomematic Proxy exception."""


class NoConnection(Exception):
    """hahomematic NoConnection exception."""


# noinspection PyProtectedMember,PyUnresolvedReferences
class ThreadPoolServerProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with ThreadPoolExecutor when request is executing.
    """

    def __init__(self, executor_func: Callable, *args: Any, **kwargs: Any):
        """
        Initialize new proxy for server and get local ip
        """
        self._executor_func = executor_func
        self._tls = kwargs.pop(ATTR_TLS, False)
        self._verify_tls = kwargs.pop(ATTR_VERIFY_TLS, True)
        if self._tls:
            kwargs[ATTR_CONTEXT] = get_tls_context(self._verify_tls)
        xmlrpc.client.ServerProxy.__init__(  # type: ignore[misc]
            self, encoding=ATTR_ENCODING_ISO_8859_1, *args, **kwargs
        )

    async def __async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """
        Call method on server side
        """
        parent = xmlrpc.client.ServerProxy
        try:
            return await self._executor_func(
                # pylint: disable=protected-access
                parent._ServerProxy__request,  # type: ignore[attr-defined]
                self,
                *args,
                **kwargs,
            )
        except OSError as ose:
            _LOGGER.exception(ose.args)
            raise NoConnection(ose) from ose
        except Exception as ex:
            raise ProxyException(ex) from ex

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """
        Magic method dispatcher
        """
        return xmlrpc.client._Method(self.__async_request, *args, **kwargs)
