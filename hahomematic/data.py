"""
Module to store data required for operation.
"""
# {instance_name, central_unit}
INSTANCES = {}


def get_client_by_interface_id(interface_id):
    """Return client by interface_id"""
    for central in INSTANCES.values():
        client = central.clients.get(interface_id)
        if client:
            return client
