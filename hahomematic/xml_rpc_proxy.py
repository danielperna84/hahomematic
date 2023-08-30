"""Implementation of a locking ServerProxy for XML-RPC communication."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum, StrEnum
import errno
import logging
from ssl import SSLError
from typing import Any, Final, TypeVar
import xmlrpc.client

from hahomematic import central_unit as hmcu
from hahomematic.exceptions import AuthFailure, ClientException, NoConnection
from hahomematic.support import get_tls_context, reduce_args

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

_CONTEXT: Final = "context"
_ENCODING_ISO_8859_1: Final = "ISO-8859-1"
_TLS: Final = "tls"
_VERIFY_TLS: Final = "verify_tls"
_VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION: Final[tuple[str, ...]] = (
    "getVersion",
    "init",
    "system.listMethods",
    "ping",
)

_NO_CONNECTION_ERROR_CODES: Final[dict[int, str]] = {
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
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        self.interface_id: Final = interface_id
        self._connection_state: Final = connection_state
        self._loop: Final = asyncio.get_running_loop()
        self._proxy_executor: Final = (
            ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=interface_id)
            if max_workers > 0
            else None
        )
        self._tls: Final[bool] = kwargs.pop(_TLS, False)
        self._verify_tls: Final[bool] = kwargs.pop(_VERIFY_TLS, True)
        if self._tls:
            kwargs[_CONTEXT] = get_tls_context(self._verify_tls)
        xmlrpc.client.ServerProxy.__init__(  # type: ignore[misc]
            self, encoding=_ENCODING_ISO_8859_1, *args, **kwargs
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
            ] in _VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION or not self._connection_state.has_issue(  # noqa: E501
                issuer=self
            ):
                args = _cleanup_args(*args)
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
        except SSLError as sslerr:
            message = f"SSLError on {self.interface_id}: {reduce_args(args=sslerr.args)}"
            _LOGGER.error(message)
            raise NoConnection(message) from sslerr
        except OSError as ose:
            message = f"OSError on {self.interface_id}: {reduce_args(args=ose.args)}"
            if ose.args[0] in _NO_CONNECTION_ERROR_CODES:
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
                    raise AuthFailure(reduce_args(args=per.args)) from per
                raise NoConnection(reduce_args(args=per.args)) from per
        except NoConnection:
            raise
        except Exception as ex:
            raise ClientException(reduce_args(args=ex.args)) from ex

    def __getattr__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Magic method dispatcher."""
        return xmlrpc.client._Method(self.__async_request, *args, **kwargs)

    def stop(self) -> None:
        """Stop depending services."""
        if self._proxy_executor:
            self._proxy_executor.shutdown()


def _cleanup_args(*args: Any) -> Any:
    """Cleanup the type of args."""
    if len(args[1]) == 0:
        return args
    new_args: list[Any] = []
    for arg in args[1]:
        if isinstance(arg, StrEnum):
            new_args.append(str(arg))
        elif isinstance(arg, IntEnum):
            new_args.append(int(arg))
        else:
            new_args.append(arg)
    return (args[0], tuple(new_args))
