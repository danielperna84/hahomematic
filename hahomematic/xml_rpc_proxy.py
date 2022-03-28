"""
Implementation of a locking ServerProxy for XML-RPC communication.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any
import xmlrpc.client

from hahomematic.const import ATTR_TLS, ATTR_VERIFY_TLS
from hahomematic.exceptions import AuthFailure, NoConnection, ProxyException
from hahomematic.helpers import get_tls_context

_LOGGER = logging.getLogger(__name__)

ATTR_CONTEXT = "context"
ATTR_ENCODING_ISO_8859_1 = "ISO-8859-1"


# noinspection PyProtectedMember,PyUnresolvedReferences
class XmlRpcProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with ThreadPoolExecutor when request is executing.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        max_workers: int,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize new proxy for server and get local ip
        """
        self._loop = loop
        self._proxy_executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tls = kwargs.pop(ATTR_TLS, False)
        self._verify_tls = kwargs.pop(ATTR_VERIFY_TLS, True)
        if self._tls:
            kwargs[ATTR_CONTEXT] = get_tls_context(self._verify_tls)
        xmlrpc.client.ServerProxy.__init__(  # type: ignore[misc]
            self, encoding=ATTR_ENCODING_ISO_8859_1, *args, **kwargs
        )

    async def _async_add_proxy_executor_job(
        self, func: Callable, *args: Any
    ) -> Awaitable:
        """Add an executor job from within the event loop for all device related interaction."""
        return await self._loop.run_in_executor(self._proxy_executor, func, *args)

    async def __async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """
        Call method on server side
        """
        _LOGGER.debug("__async_request: %s", args)
        parent = xmlrpc.client.ServerProxy
        try:
            return await self._async_add_proxy_executor_job(
                # pylint: disable=protected-access
                parent._ServerProxy__request,  # type: ignore[attr-defined]
                self,
                *args,
            )
        except OSError as ose:
            _LOGGER.error(ose.args)
            raise NoConnection(ose) from ose
        except xmlrpc.client.Fault as fex:
            raise ProxyException(fex) from fex
        except xmlrpc.client.ProtocolError as per:
            if per.errmsg == "Unauthorized":
                raise AuthFailure(per) from per
            raise NoConnection(per) from per
        except Exception as ex:
            raise ProxyException(ex) from ex

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """
        Magic method dispatcher
        """
        return xmlrpc.client._Method(self.__async_request, *args, **kwargs)

    def stop(self) -> None:
        """Stop depending services."""
        self._proxy_executor.shutdown(wait=False, cancel_futures=True)
