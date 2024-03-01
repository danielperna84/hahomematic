"""Implementation of a locking ServerProxy for XML-RPC communication."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, IntEnum, StrEnum
import errno
import logging
from ssl import SSLError
from typing import Any, Final, TypeVar
import xmlrpc.client

from hahomematic import central as hmcu
from hahomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    ClientException,
    NoConnection,
    UnsupportedException,
)
from hahomematic.support import get_tls_context, reduce_args

_LOGGER: Final = logging.getLogger(__name__)

_T = TypeVar("_T")

_CONTEXT: Final = "context"
_ENCODING_ISO_8859_1: Final = "ISO-8859-1"
_TLS: Final = "tls"
_VERIFY_TLS: Final = "verify_tls"


class XmlRpcMethod(StrEnum):
    """Enum for homematic json rpc methods types."""

    GET_VERSION = "getVersion"
    INIT = "init"
    PING = "ping"
    SYSTEM_LIST_METHODS = "system.listMethods"


_VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION: Final[tuple[str, ...]] = (
    XmlRpcMethod.GET_VERSION,
    XmlRpcMethod.INIT,
    XmlRpcMethod.PING,
    XmlRpcMethod.SYSTEM_LIST_METHODS,
)

_SSL_ERROR_CODES: Final[dict[int, str]] = {
    errno.ENOEXEC: "EOF occurred in violation of protocol",
}

_OS_ERROR_CODES: Final[dict[int, str]] = {
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
        self._supported_methods: tuple[str, ...] = ()
        if self._tls:
            kwargs[_CONTEXT] = get_tls_context(self._verify_tls)
        xmlrpc.client.ServerProxy.__init__(  # type: ignore[misc]
            self, encoding=_ENCODING_ISO_8859_1, *args, **kwargs
        )

    async def do_init(self) -> None:
        """Init the xml rpc proxy."""
        if supported_methods := await self.system.listMethods():
            # ping is missing in VirtualDevices interface but can be used.
            supported_methods.append(XmlRpcMethod.PING)
            self._supported_methods = tuple(supported_methods)

    @property
    def supported_methods(self) -> tuple[str, ...]:
        """Return the supported methods."""
        return self._supported_methods

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
            method = args[0]
            if self._supported_methods and method not in self._supported_methods:
                raise UnsupportedException(
                    f"__ASYNC_REQUEST: method '{method} not supported by backend."
                )

            if (
                method in _VALID_XMLRPC_COMMANDS_ON_NO_CONNECTION
                or not self._connection_state.has_issue(  # noqa: E501
                    issuer=self, iid=self.interface_id
                )
            ):
                args = _cleanup_args(*args)
                _LOGGER.debug("__ASYNC_REQUEST: %s", args)
                result = await self._async_add_proxy_executor_job(
                    # pylint: disable=protected-access
                    parent._ServerProxy__request,  # type: ignore[attr-defined]
                    self,
                    *args,
                )
                self._connection_state.remove_issue(issuer=self, iid=self.interface_id)
                return result
            raise NoConnection(f"No connection to {self.interface_id}")
        except BaseHomematicException:
            raise
        except SSLError as sslerr:
            message = f"SSLError on {self.interface_id}: {reduce_args(args=sslerr.args)}"
            if sslerr.args[0] in _SSL_ERROR_CODES:
                _LOGGER.debug(message)
            else:
                _LOGGER.error(message)
            raise NoConnection(message) from sslerr
        except OSError as ose:
            message = f"OSError on {self.interface_id}: {reduce_args(args=ose.args)}"
            if ose.args[0] in _OS_ERROR_CODES:
                if self._connection_state.add_issue(issuer=self, iid=self.interface_id):
                    _LOGGER.error(message)
                else:
                    _LOGGER.debug(message)
            else:
                _LOGGER.error(message)
            raise NoConnection(message) from ose
        except xmlrpc.client.Fault as fex:
            raise ClientException(
                f"XMLRPC Fault from backend: {fex.faultCode} {fex.faultString}"
            ) from fex
        except TypeError as terr:
            raise ClientException(terr) from terr
        except xmlrpc.client.ProtocolError as per:
            if not self._connection_state.has_issue(issuer=self, iid=self.interface_id):
                if per.errmsg == "Unauthorized":
                    raise AuthFailure(per) from per
                raise NoConnection(per) from per
        except Exception as ex:
            raise ClientException(ex) from ex

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
    if len(args) == 2:
        new_args: list[Any] = []
        for data in args[1]:
            if isinstance(data, dict):
                new_args.append(_cleanup_paramset(paramset=data))
            else:
                new_args.append(_cleanup_parameter(value=data))
        return (args[0], tuple(new_args))
    _LOGGER.error("XmlRpcProxy command: Too many arguments")
    return args


def _cleanup_parameter(value: Any) -> Any:
    """Cleanup a single parameter."""
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, Enum):
        _LOGGER.error("XmlRpcProxy command: Enum is not supported as parameter value")
    return value


def _cleanup_paramset(paramset: Mapping[str, Any]) -> dict[str, Any]:
    """Cleanup a single parameter."""
    new_paramset: dict[str, Any] = {}
    for name, value in paramset.items():
        new_paramset[name] = _cleanup_parameter(value=value)
    return new_paramset
