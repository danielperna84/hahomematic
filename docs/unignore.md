# unignore

_Hahomematic_ maintains [multiple lists](https://github.com/danielperna84/hahomematic/blob/devel/hahomematic/caches/visibility.py#L86) of parameters that should be ignored when entities are created for _Home-Assistant_.
These parameters are filtered out to provide a better user experience for the majority of the users.

But there is also a group of users that wants to do more... _things_.

These advanced users can use the _unignore mechanism_ provided by _hahomematic_.

You must accept the following before using the _unignore mechanism_:

- Use at your own risk!
- Only one parameter per line
- Parameters are case sensitive
- Parameters added will be created as an entity for every device and on every channel where available
- Changes require a restart
- Customization to entities must be done with HA customisations

To use the _unignore mechanism_ create a file named `unignore`(no prefix!) in the `{ha config dir}/homematicip_local` and put the parameters in there.

## Examples:

### parameter only (only valid for paramset VALUES):

```
LEVEL
FROST_PROTECTION
```

### parameter with limitation to a device type, channel and paramset type:

```
LEVEL@HmIP-eTRV-2:1:VALUES
FROST_PROTECTION@HmIP-BWTH:1:VALUES
```
