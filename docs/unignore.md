# unignore

_Hahomematic_ maintains [multiple lists](https://github.com/danielperna84/hahomematic/blob/devel/hahomematic/caches/visibility.py#L86) of parameters that should be ignored when entities are created for _Home-Assistant_.
These parameters are filtered out to provide a better user experience for the majority of the users.

But there is also a group of users that wants to do more... _things_.

These advanced users can use the _unignore mechanism_ provided by _hahomematic_.

You must accept the following before using the _unignore mechanism_:

- Use at your own risk!
- Only one parameter per line
- Parameters are case sensitive
- Changes require a restart
- Customization to entities must be done with HA customisations
- Excessive writing of parameters from `MASTER` paramset can cause damage of the device

To use the _unignore mechanism_ create a file named `unignore`(no prefix!) in the `{ha config dir}/homematicip_local` and put the parameters in there.
When adding parameters from `MASTER` paramset the [cache must be cleared](https://github.com/danielperna84/custom_homematic?tab=readme-ov-file#homematicip_localclear_cache) before restart.

## Examples:

### parameter only (only valid for paramset VALUES):

```
LEVEL
FROST_PROTECTION
```

### parameter with limitation to a device type, channel and paramset type (> 1.55.0):

```
GLOBAL_BUTTON_LOCK:MASTER@HmIP-eTRV-2:0 
LEVEL:VALUES@HmIP-BROLL:3
GLOBAL_BUTTON_LOCK:MASTER@HM-TC-IT-WM-W-EU: (channel is empty!)
```
Wildcards can be used for device_type and channel for parameters from VALUES the paramaset:
```
LEVEL:VALUES@all:3  # (LEVEL on channel 3 for all device types)
LEVEL:VALUES@HmIP-BROLL:all  # (LEVEL on all channels for HmIP-BROLL)
LEVEL:VALUES@all:all  # (LEVEL on all channels for all device types) equivalent to just LEVEL
```

# Known limitations

Parameters from `MASTER` paramset of HM-Classic (BidCos) devices can be changed, but need a manual refresh, by calling the service `homeassistant.update_entity`.
