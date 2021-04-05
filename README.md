# hahomematic

### This project is still in early development!

`hahomematic` is a Python 3 (>= 3.6) module for [Home Assistant](https://www.home-assistant.io/) to interact with [HomeMatic](https://www.eq-3.com/products/homematic.html) and [homematic IP](https://www.homematic-ip.com/en/start.html) devices. Some other devices (f.ex. Bosch, Intertechno) might be supported as well.

No 3rd party Python dependencies are required.

This is intended to become the successor of [pyhomematic](https://github.com/danielperna84/pyhomematic).

## Project goal and features

[pyhomematic](https://github.com/danielperna84/pyhomematic) has the requirement to manually add support for devices to make them usable in [Home Assistant](https://www.home-assistant.io/). With `hahomematic` it is planned to automatically create entities for each parameter on each channel on every device. To achieve this, all paramsets (`VALUES`) are fetched (and cached for quick successive startups). Eventually it will expose pretty much __all__ parameters, like [ioBroker](https://www.iobroker.net/) does.

On top of that it will be allowed to add custom device-classes to implement more complex entities (__additionally__ to the auto-generated entities) if it makes sense for a device. Much like the [devicetypes](https://github.com/danielperna84/pyhomematic/tree/master/pyhomematic/devicetypes) of [pyhomematic](https://github.com/danielperna84/pyhomematic). This will be needed for thermostats, lights, covers etc..

Helpers for automatic re-connecting after a restart of the CCU are provided as well. How they are used depends on the application that integrates `hahomematic`.

## Requirements

Due to a bug in previous version of the CCU2 / CCU3, `hahomematic` requires at least the following version for usage with homematic IP devices:

- CCU2: 2.53.27
- CCU3: 3.53.26

More information about this bug can be found here: https://github.com/jens-maus/RaspberryMatic/issues/843. Other CCU-like platforms that leverage the buggy version of the `HmIPServer` aren't supported as well.