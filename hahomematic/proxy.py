"""
Implementation of a locking ServerProxy for XML-RPC communication.
"""

import logging
import ssl
import threading
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
# noinspection PyProtectedMember,PyUnresolvedReferences
class LockingServerProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with lock when request is executing.
    """

    def __init__(self, is_async: bool, *args, **kwargs):
        """
        Initialize new proxy for server and get local ip
        """
        self._is_async = is_async
        self._tls = kwargs.pop("tls", False)
        self._verify_tls = kwargs.pop("verify_tls", True)
        self.lock = threading.Lock()
        if self._tls and not self._verify_tls and self._verify_tls is not None:
            kwargs["context"] = ssl._create_unverified_context()
        xmlrpc.client.ServerProxy.__init__(self, encoding="ISO-8859-1", *args, **kwargs)

    async def __async_request(self, *args, **kwargs):
        """
        Call method on server side
        """

        with self.lock:
            parent = xmlrpc.client.ServerProxy
            # pylint: disable=protected-access
            return parent._ServerProxy__request(self, *args, **kwargs)

    def __sync_request(self, *args, **kwargs):
        """
        Call method on server side
        """

        with self.lock:
            parent = xmlrpc.client.ServerProxy
            # pylint: disable=protected-access
            return parent._ServerProxy__request(self, *args, **kwargs)

    def __getattr__(self, *args, **kwargs):
        """
        Magic method dispatcher
        """
        if self._is_async:
            return xmlrpc.client._Method(self.__async_request, *args, **kwargs)
        else:
            return xmlrpc.client._Method(self.__sync_request, *args, **kwargs)


# pylint: disable=too-few-public-methods
# noinspection PyProtectedMember,PyUnresolvedReferences
class ThreadPoolServerProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with lock when request is executing.
    """

    def __init__(
        self, executor_func, *args, **kwargs
    ):
        """
        Initialize new proxy for server and get local ip
        """
        self._executor_func = executor_func
        self._tls = kwargs.pop("tls", False)
        self._verify_tls = kwargs.pop("verify_tls", True)
        if self._tls and not self._verify_tls and self._verify_tls is not None:
            kwargs["context"] = ssl._create_unverified_context()
        xmlrpc.client.ServerProxy.__init__(self, encoding="ISO-8859-1", *args, **kwargs)

    async def __async_request(self, *args, **kwargs):
        """
        Call method on server side
        """
        parent = xmlrpc.client.ServerProxy
        # pylint: disable=protected-access
        return await self._executor_func(parent._ServerProxy__request, self, *args, **kwargs)

    def __getattr__(self, *args, **kwargs):
        """
        Magic method dispatcher
        """
        return xmlrpc.client._Method(self.__async_request, *args, **kwargs)


# # pylint: disable=too-few-public-methods
# # noinspection PyProtectedMember,PyUnresolvedReferences
# class AsyncLockingServerProxy(aiohttp_xmlrpc.client.ServerProxy):
#     """
#     ServerProxy implementation with lock when request is executing.
#     """
#
#     def __init__(self, *args, **kwargs):
#         """
#         Initialize new proxy for server and get local ip
#         """
#         self._tls = kwargs.pop("tls", False)
#         self._verify_tls = kwargs.pop("verify_tls", True)
#         self.lock = threading.Lock()
#         if self._tls and not self._verify_tls and self._verify_tls is not None:
#             kwargs["context"] = ssl._create_unverified_context()
#         aiohttp_xmlrpc.client.ServerProxy.__init__(
#             self, url=args[0], encoding="ISO-8859-1"
#         )
#
#     async def __remote_call(self, method_name, *args, **kwargs):
#         with self.lock:
#             parent = aiohttp_xmlrpc.client.ServerProxy
#             # pylint: disable=protected-access
#             return await parent._ServerProxy__remote_call(
#                 self, method_name, *args, **kwargs
#             )
#
#     def __getitem__(self, method_name):
#         def method(*args, **kwargs):
#             return self.__remote_call(method_name, *args, **kwargs)
#
#         return method
#
#     def __getattr__(self, method_name):
#         return self[method_name]


# # pylint: disable=too-few-public-methods
# # noinspection PyProtectedMember,PyUnresolvedReferences
# class AsyncThreadPoolServerProxy(aiohttp_xmlrpc.client.ServerProxy):
#     """
#     ServerProxy implementation with lock when request is executing.
#     """
#
#     def __init__(self, proxy_executor: ThreadPoolExecutor, *args, **kwargs):
#         """
#         Initialize new proxy for server and get local ip
#         """
#         self._proxy_executor = proxy_executor
#         self._tls = kwargs.pop("tls", False)
#         self._verify_tls = kwargs.pop("verify_tls", True)
#         if self._tls and not self._verify_tls and self._verify_tls is not None:
#             kwargs["context"] = ssl._create_unverified_context()
#         aiohttp_xmlrpc.client.ServerProxy.__init__(
#             self, url=args[0], encoding="ISO-8859-1"
#         )
#
#     async def __remote_call(self, method_name, *args, **kwargs):
#         parent = aiohttp_xmlrpc.client.ServerProxy
#         # pylint: disable=protected-access
#         return await self._proxy_executor.submit(parent._ServerProxy__remote_call, self, method_name, *args, **kwargs).result()
#
#     def __getitem__(self, method_name):
#         def method(*args, **kwargs):
#             return self.__remote_call(method_name, *args, **kwargs)
#
#         return method
#
#     def __getattr__(self, method_name):
#         return self[method_name]
