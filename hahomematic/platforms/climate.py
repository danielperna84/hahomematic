"""
Module for entities implemented using the
climate platform (https://www.home-assistant.io/integrations/climate/).
This probably will just provide the intermediate class so
the Home Assistant integration can identify the custom device
as a climate entity.
"""
import logging

from hahomematic import config

LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name,too-few-public-methods
class BaseClimate:
    """
    Base class for climate entities.
    """

    def __init__(self, server, interface_id, address, unique_id):
        self._server = server
        self.interface_id = interface_id
        self.address = address
        self._client = self._server.clients[self.interface_id]
        self.proxy = self._client.proxy
        self.unique_id = unique_id
        self.name = self._server.names_cache.get(self.interface_id, {}).get(
            self.address, self.unique_id
        )
        self.ha_device = self._server.ha_devices[self.address]
        self.channels = list(
            self._server.devices[self.interface_id][self.address].keys()
        )
        # Subscribe for all events of this device
        if not self.address in self._server.event_subscriptions_device:
            self._server.event_subscriptions_device[self.address] = []
        self._server.event_subscriptions_device[self.address].append(self.event)
        self.update_callback = None
        if callable(config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = config.CALLBACK_ENTITY_UPDATE

    def event(self, interface_id, address, value_key, value):
        """
        Handle events for this device.
        """
        if interface_id != self.interface_id:
            return
        if address not in [f"{self.address}:1", f"{self.address}:2"]:
            return
        LOG.debug(
            "SimpleThermostat.event(%s, %s, %s, %s)",
            interface_id,
            address,
            value_key,
            value,
        )
        self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("Thermostat.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.unique_id)
