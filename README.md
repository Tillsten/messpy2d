# messpy2d

## Overview

This project is an experimental control for ultrafast spectroscopy. While it's
primarily designed for our specific use case, some of the device interfaces may
be useful for others.

![MessPy Screenshot](messpy_screenshot.png)

The software uses pixi as an enviroment manager, which allows for easy
installation and distribution. To get started install [pixi](https://pixi.sh)
and run the following commands in the repository folder:

```bash
pixi install
pixi run start
```

Pixi should automatically install all dependencies. However, for some hardware
specific drivers may be necessary. Please refer to the documentation of the
specific hardware for more information.


## Supported Hardware

### Detectors

- Phasetech 128 x 128 MCT
- Infrared Associates Arrays using NI-cards
- Avaspec Spectrometer
- Stresing CAM (PCI based)

### Spectrometers

- Triax
- SP2150i

### Linear & Rotation Stages

- Newport (serial connection)
- Thorlabs (using the .net interface)
- PI stages
- Smaract stage
- Faulhaber Motorcontroller

### Shutter

- Thorlabs SC-10
- Homebuild Arduino
- phideget
- TOPAS internal shutter

### Pulseshapers

- Phasetech

## Features

- Pump-Probe
- 2D-IR (including phase mask generation)
- live view of the measurments
- automatic time-zero determination
- automatic Shaper calibration
- Dispersion scan: gvd-, tod-, fod-scan
- advanced referencing methods

## Getting Started

To use the software the correct configuration of hardware is necessary. The
configuration is done in the HwRegistry.py file. For most hardware a simulated
version is avaiable. The simulated version is used by default. To use the real
hardware the simulated version has to be commented out and the real hardware
has to be assigned to the correct variable. In general, each hardware device
is based on an abstract class. The abstract class defines the methods that
have to be implemented by the specific hardware class. The abstract class
also defines the methods that are used by the software. The abstract class
is located in the instruments folder in instruments.py. The specific hardware
implementation is located in the instruments folder in the subfolder of the
specific hardware.

## Contributing

Raise an issue or submit a pull request on github.

## License

This project is licensed under the BSD License - see the LICENSE.md file for details
