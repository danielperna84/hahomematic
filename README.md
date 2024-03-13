# hahomematic

`hahomematic` is a Python 3 module for [Home Assistant](https://www.home-assistant.io/) to interact with [HomeMatic](https://www.eq-3.com/products/homematic.html) and [HomematicIP](https://www.homematic-ip.com/en/start.html) devices. Some other devices (f.ex. Bosch, Intertechno) might be supported as well.

This is intended to become the successor of [pyhomematic](https://github.com/danielperna84/pyhomematic).

It can be installed by using the [custom_component](https://github.com/danielperna84/custom_homematic).
Necessary installation instructions can be found [here](https://github.com/danielperna84/custom_homematic/wiki/Installation).

## Project goal and features

[pyhomematic](https://github.com/danielperna84/pyhomematic) has the requirement to manually add support for devices to make them usable in [Home Assistant](https://www.home-assistant.io/). `hahomematic` automatically create entities for each parameter on each channel on every device (if it not black listed). To achieve this, all paramsets (`VALUES`) are fetched (and cached for quick successive startups).

On top of that it is possible to add custom entity-classes to implement more complex entities, if it makes sense for a device, much like the [devicetypes](https://github.com/danielperna84/pyhomematic/tree/master/pyhomematic/devicetypes) of [pyhomematic](https://github.com/danielperna84/pyhomematic). This will be needed for thermostats, lights, covers, climate, lock, siren etc..

Helpers for automatic re-connecting after a restart of the CCU are provided as well.

## Requirements

Due to a bug in previous version of the CCU2 / CCU3, `hahomematic` requires at least the following version for usage with HomematicIP devices:

- CCU2: 2.53.27
- CCU3: 3.53.26

More information about this bug can be found here: https://github.com/jens-maus/RaspberryMatic/issues/843. Other CCU-like platforms that leverage the buggy version of the `HmIPServer` aren't supported as well.
