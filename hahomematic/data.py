"""
Module to store data required for operation.
"""
# {instance_name, server}
INSTANCES = {}
# {interface_id, {address, channel_address}}
DEVICES = {}
# ---
DEVICES_ALL = {}
# {interface_id, {address, dev_descriptions}
DEVICES_RAW_DICT = {}
# ---
PROXIES = {}
# ---
REMOTES = {}
# {interface_id, client}
CLIENTS = {}
# {url, client}
CLIENTS_BY_INIT_URL = {}

# {unique_id, entity}
ENTITIES = {}
# {{channel_address, parameter}, event_handle}
EVENT_SUBSCRIPTIONS = {}
# {device_address, event_handle}
EVENT_SUBSCRIPTIONS_DEVICE = {}
# {device_address, device}
HA_DEVICES = {}
