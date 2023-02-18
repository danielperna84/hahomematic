"""Implementation of a locking ServerProxy for XML-RPC communication."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import errno
import logging
from typing import Any, Final, TypeVar
import xmlrpc.client

from hahomematic import central_unit as hmcu
from hahomematic.const import ATTR_TLS, ATTR_VERIFY_TLS
from hahomematic.exceptions import AuthFailure, ClientException, NoConnection
from hahomematic.support import get_tls_context

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")

ATTR_CONTEXT: Final = "context"
ATTR_ENCODING_ISO_8859_1: Final = "ISO-8859-1"

PROXY_GET_VERSION: Final = "getVersion"
PROXY_INIT: Final = "init"
PROXY_LIST_METHODS: Final = "system.listMethods"
PROXY_PING: Final = "ping"
VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION: Final[tuple[str, ...]] = (
    PROXY_GET_VERSION,
    PROXY_INIT,
    PROXY_LIST_METHODS,
    PROXY_PING,
)

NO_CONNECTION_ERROR_CODES: Final[dict[int, str]] = {
    errno.ECONNREFUSED: "Connection refused",
    errno.ENETUNREACH: "Network is unreachable",
    errno.ETIMEDOUT: "Operation timed out",
    errno.EHOSTUNREACH: "No route to host",
}


# noinspection PyProtectedMember,PyUnresolvedReferences
class XmlRpcProxy(xmlrpc.client.ServerProxy):
    """ServerProxy implementation with ThreadPoolExecutor when request is executing."""

    def __init__(
        self,
        max_workers: int,
        interface_id: str,
        connection_state: hmcu.CentralConnectionState,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize new proxy for server and get local ip."""
        self._tasks: set[asyncio.Future[Any]] = set()
        self.interface_id = interface_id
        self._connection_state: Final[hmcu.CentralConnectionState] = connection_state
        self._loop: Final[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        self._proxy_executor: Final[ThreadPoolExecutor] = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=interface_id
        )
        self._tls: Final[bool] = kwargs.pop(ATTR_TLS, False)
        self._verify_tls: Final[bool] = kwargs.pop(ATTR_VERIFY_TLS, True)
        if self._tls:
            kwargs[ATTR_CONTEXT] = get_tls_context(self._verify_tls)
        xmlrpc.client.ServerProxy.__init__(  # type: ignore[misc]
            self, encoding=ATTR_ENCODING_ISO_8859_1, *args, **kwargs
        )

    def _async_add_proxy_executor_job(
        self, func: Callable[..., _T], *args: Any
    ) -> asyncio.Future[_T]:
        """Add an executor job from within the event_loop for all device related interaction."""
        task = self._loop.run_in_executor(self._proxy_executor, func, *args)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    async def __async_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Call method on server side."""
        parent = xmlrpc.client.ServerProxy
        try:
            if args[
                0
            ] in VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION or not self._connection_state.has_issue(  # noqa: E501
                issuer=self
            ):
                _LOGGER.debug("__ASYNC_REQUEST: %s", args)
                result = await self._async_add_proxy_executor_job(
                    # pylint: disable=protected-access
                    parent._ServerProxy__request,  # type: ignore[attr-defined]
                    self,
                    *args,
                )
                self._connection_state.remove_issue(issuer=self)
                return result
            raise NoConnection(f"No connection to {self.interface_id}")
        except OSError as ose:
            message = f"OSError on {self.interface_id}: {ose.args}"
            if ose.args[0] in NO_CONNECTION_ERROR_CODES:
                if self._connection_state.add_issue(issuer=self):
                    _LOGGER.error(message)
                else:
                    _LOGGER.debug(message)
            else:
                _LOGGER.error(message)
            raise NoConnection(message) from ose
        except xmlrpc.client.Fault as fex:
            raise ClientException(fex) from fex
        except xmlrpc.client.ProtocolError as per:
            if not self._connection_state.has_issue(issuer=self):
                if per.errmsg == "Unauthorized":
                    raise AuthFailure(per) from per
                raise NoConnection(per) from per
        except NoConnection as noc:
            raise noc
        except Exception as ex:
            raise ClientException(ex) from ex

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Magic method dispatcher."""
        return xmlrpc.client._Method(self.__async_request, *args, **kwargs)

    def stop(self) -> None:
        """Stop depending services."""
        self._proxy_executor.shutdown()
