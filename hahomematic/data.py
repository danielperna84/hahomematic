"""
Module to store data required for operation.
"""
# {instance_name, server}
INSTANCES = {}


def get_client_by_interface_id(interface_id):
    """Return client by interface_id"""
    for server in INSTANCES.values():
        client = server.clients.get(interface_id)
        if client:
            return client
