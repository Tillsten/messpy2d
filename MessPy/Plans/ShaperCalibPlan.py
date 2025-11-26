from MessPy.Plans.PlanBase import Plan
from MessPy.ControlClasses import Cam
from MessPy.Instruments.dac_px import AOM
import numpy as np
from pyqtgraph.parametertree import Parameter, ParameterTree
import pyqtgraph as pg
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import *
from qasync import QEventLoop, asyncSlot
from typing import List, Callable, Tuple, ClassVar
from MessPy.Instruments.interfaces import ICam
import sys

import attr

sys.path.append("../")


@attr.s(auto_attribs=True, cmp=False, kw_only=True)
class CalibPlan(Plan):
    cam: Cam
    dac: AOM
    points: List[float]
    amps: List[List[float]] = attr.Factory(list)
    single_spectra: np.ndarray = attr.ib(init=False)
    num_shots: int = 100
    separation: int = 500
    width: int = 50
    single: int = 6000
    start_pos: Tuple[float, float] = 0
    check_zero_order: bool = True
    channel: int = 67

    sigStepDone = Signal()
    plan_shorthand: ClassVar[str] = "Calibration"

    def __attrs_post_init__(self):
        super(CalibPlan, self).__attrs_post_init__()
        self.single_spectra = np.zeros((self.cam.channels, len(self.points)))
        gen = self.make_step_generator()
        self.make_step = lambda: next(gen)
    
    def make_step_generator(self):
        yield
        self.sigPlanStarted.emit()
        self.cam.set_shots(self.num_shots)
    
        initial_wl = self.cam.get_wavelength()
        initial_shots = self.cam.shots
        if self.check_zero_order:
    
            self.cam.cam.spectrograph.set_wavelength(0, 10)
            
            reading, ch = self.cam.cam.get_spectra(3)
            pump_spec = reading["Probe2"]
            self.channel = np.argmax(pump_spec.mean)  # typing: ignore
            yield
        self.single_spectra = np.zeros((self.cam.channels, len(self.points)))
        self.dac.load_mask(
            self.dac.make_calib_mask(
                width=self.width, separation=self.separation, single=self.single
            )
        )
        for i, p in enumerate(self.points):
            self.read_point(i, p)
            self.sigStepDone.emit()
            yield
        self.cam.set_wavelength(initial_wl)
        self.cam.set_shots(initial_shots)
        self.sigPlanFinished.emit()

    def read_point(self, i, p):        
        self.cam.cam.spectrograph.set_wavelength(p, 10)
        spectra = self.cam.cam.get_spectra(3)[0]
        self.amps.append(spectra["Probe2"].frame_data[self.channel, :])
        self.single_spectra[:, i] = spectra["Probe2"].frame_data[:, 1]
