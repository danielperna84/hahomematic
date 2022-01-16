# About RSSI values

If you are using the generated RSSI entities, you might notice that the values do not always match what you see in the CCU WebUI.
In short, this is because the values shown in the WebUI (and returned in the Homematic API) are wrong.
This integration applies strategies to fix the reported values as good as it can so you can use it without worrying about the technical details.

If you are interested in a further explanation, continue reading.

## Technical details

The RSSI ([Received Signal Strength Indicator](https://en.wikipedia.org/wiki/Received_signal_strength_indication)) value indicates how good the communication between two radio devices is (e.g. CCU and one of your Homematic devices).
It can be measured in various units, Homematic uses dBm ([decibel-milliwatts](https://en.wikipedia.org/wiki/DBm)).
The valid range is determined by the chipset used.
For Homematic it is -127 to 0 dBm.
The closer the value is to 0, the stronger the signal has been.

Unfortunately some implementation details in Homematic lead to values being reported outside this range.
This is probably because of wrong datatypes used for the conversion and internal conventions. It results in the following reported ranges:

- 0, 1, -256, 256, 128, -128, 65536, -65536: All used in one place or another to indicate "unknown"
- 1 to 127: A missing inversion of the value, so it is fixed by multiplying with -1
- 129 to 256: A wrongly used datatype, it is fixed by subtracting 256 from the value
- -129 to -256: A wrongly used datatype, it is fixed by subtracting 256 from the inverted value

These are the exact conversions that are applied in Home Assistant:

| Range | Converted value | Reason |
|--------------------|----------------|---------------------------------|
| <= -256             | None/unknown   | Invalid                                |
| > -256 and < -129 | (value * -1) - 256 | Translates to > -127 and < 0 |
| >= -129 and <= -127   | None/unknown   | Invalid                                |
| > -127 and < 0      | value          | The real range, used as is                  |
| >= 0 and <= 1   | None/unknown   | Translates to None/unknown                               |
| > 1 and < 127               | value * -1    | Translates to > -127 and < -1                               |
| >= 127 and <= 129     | None/unknown   | Invalid                                |
| > 129 and < 256 | value - 256 | Translates to > -127 and < 0 |
| >= 256     | None/unknown   | Invalid                                |
