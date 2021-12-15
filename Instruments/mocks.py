from typing import Dict, Optional

import numpy as np
import attr
from Instruments.interfaces import ICam, IDelayLine, IRotationStage, \
    IShutter, Reading, Spectrum, ISpectrograph
import time
import threading

@attr.s(auto_attribs=True)
class MockState:
    wl: float = 0
    t: float = 0
    shutter: bool = False
    rot_stage_angle: float = 45

state = MockState()

@attr.s(auto_attribs=True)
class MockSpectrograph(ISpectrograph):
    name: str = 'MockSpec'
    changeable_wavelength: bool = True
    center_wl: float = 300
    _cur_grating: int = 0

    def set_wavelength(self, wl: float):
        self.center_wl = wl
        state.wl = wl
        self.sigWavelengthChanged.emit(wl)

    def get_wavelength(self):
        return self.center_wl

    @property
    def gratings(self) -> Dict[int, str]:
        return {0: "0", 1: "1"}

    def set_grating(self, idx: int):
        self._cur_grating = idx
        self.sigGratingChanged.emit(idx)

    def get_grating(self) -> int:
        return self._cur_grating


@attr.s(auto_attribs=True)
class CamMock(ICam):
    name: str = 'MockCam'
    shots: int = 20
    line_names: list = ['Test1', 'Test2']
    sig_names: list = ['Test1']
    std_names: list = ['Test1', 'Test2']
    channels: int = 200
    ext_channels: int = 3
    background: object = None
    spectrograph: Optional[ISpectrograph] = attr.Factory(MockSpectrograph)

    def set_shots(self, shots):
        self.shots = shots

    def read_cam(self):
        a = np.random.normal(loc=30, size=(self.channels, self.shots)).T
        b = np.random.normal(loc=20, size=(self.channels, self.shots)).T
        ext = np.random.normal(size=(self.ext_channels, self.shots)).T
        chop = np.array([True, False]).repeat(self.shots/2)
        time.sleep(self.shots/1000.)
        return a, b, chop, ext

    def make_reading(self) -> Reading:
        a, b, chopper, ext = self.read_cam()
        if self.background is not None:
            a -= self.background[0, ...]
            b -= self.background[1, ...]
        tmp = np.stack((a, b))
        tm = tmp.mean(1)
        signal = -np.log10(a[chopper, :].mean(0)/a[~chopper, :].mean(0))
        return Reading(
            lines=tm,
            stds=100*tmp.std(1)/tm,
            signals=signal[None, :],
            valid=True,
        )

    def get_spectra(self):
        pass

    def set_background(self, shots):
        pass

    def get_wavelength_array(self, center_wl=None):
        if not center_wl:
            center_wl = self.spectrograph.center_wl
        x = (np.arange(self.channels)-self.channels//2)
        return x*0.5 + center_wl


@attr.s(auto_attribs=True)
class DelayLineMock(IDelayLine):
    name: str = 'MockDelayStage'
    pos_mm: float = 0.
    mock_speed: float = 6.
    moving: bool = False
    current_move: tuple = None

    def move_mm(self, mm, do_wait=True):
        distance = mm - self.pos_mm
        duration = distance / self.mock_speed
        self.current_move = (time.time(), mm)
        self.moving = True
        self.pos_mm = mm

    def get_pos_mm(self):
        if self.moving:
            time_passed = self.current_move[0] - time.time()
        return self.pos_mm

    def is_moving(self):
        return False

    def move_fs(self, fs, do_wait=False):
        super().move_fs(fs, do_wait=do_wait)
        state.t = fs

@attr.s(auto_attribs=True)
class RotStageMock(IRotationStage):
    name: str = 'Rotation Mock'
    deg: float = 0

    def set_degrees(self, deg: float):
        self.deg = deg
        state.rot_stage_angle = deg

    def get_degrees(self) -> float:
        return self.deg

    def is_moving(self):
        return False


@attr.s(auto_attribs=True)
class ShutterMock(IShutter):
    name = 'ShutterMock'
    is_open: bool = True

    def is_open(self):
        return self.is_open

    def toggle(self):
        self.is_open = not self.is_open
        state.shutter = self.is_open


@attr.s(auto_attribs=True)
class AOMMock:
    pass

