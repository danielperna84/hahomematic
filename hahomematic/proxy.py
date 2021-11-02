"""
Implementation of a locking ServerProxy for XML-RPC communication.
"""

import logging
import ssl
import threading
import xmlrpc.client

LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
# noinspection PyProtectedMember,PyUnresolvedReferences
class LockingServerProxy(xmlrpc.client.ServerProxy):
    """
    ServerProxy implementation with lock when request is executing.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize new proxy for server and get local ip
        """
        self._tls = kwargs.pop("tls", False)
        self._verify_tls = kwargs.pop("verify_tls", True)
        self.lock = threading.Lock()
        if self._tls and not self._verify_tls and self._verify_tls is not None:
            kwargs["context"] = ssl._create_unverified_context()
        xmlrpc.client.ServerProxy.__init__(self, encoding="ISO-8859-1", *args, **kwargs)

    def __request(self, *args, **kwargs):
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
        return xmlrpc.client._Method(self.__request, *args, **kwargs)
