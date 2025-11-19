from typing import ClassVar, Iterable, List, Tuple

import attr
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import *

from MessPy.ControlClasses import Cam
from MessPy.Instruments.dac_px import AOM
from MessPy.Plans.PlanBase import Plan


@attr.s(auto_attribs=True, cmp=False, kw_only=True)
class CalibPlan(Plan):
    cam: Cam
    dac: AOM
    points: List[float]
    amps: List[Iterable[float]] = attr.Factory(list)
    single_spectra: np.ndarray = attr.ib(init=False)
    num_shots: int = 100
    separation: int = 500
    width: int = 50
    single: int = 6000
    start_pos: Tuple[float, float] = (0.0, 0.0)
    check_zero_order: bool = True
    channel: int = 67

    sigStepDone = Signal()
    plan_shorthand: ClassVar[str] = "Calibration"

    def __attrs_post_init__(self):
        super(CalibPlan, self).__attrs_post_init__()
        assert self.cam.changeable_wavelength
        self.single_spectra = np.zeros((self.cam.channels, len(self.points)))

    def make_step_gen(self):
        initial_shots = self.cam.shots
        initial_wl = self.cam.get_wavelength()
        self.sigPlanStarted.emit()
        yield
        self.cam.set_shots(self.num_shots)
        yield
        if self.check_zero_order:
            assert self.cam.cam.spectrograph is not None
            self.cam.set_wavelength(0, 10)
            reading, ch = self.cam.cam.get_spectra(3)
            pump_spec = reading["Probe2"]
            self.channel = int(np.argmax(pump_spec.mean))  # typing: ignore

        self.single_spectra = np.zeros((self.cam.channels, len(self.points)))
        logger.info('Loading Calib mask')
        self.dac.load_mask(
            self.dac.make_calib_mask(
                width=self.width, separation=self.separation, single=self.single
            )
        )
        for i, p in enumerate(self.points):
            self.read_point(i, p)
            yield
            self.sigStepDone.emit()
            yield
        self.cam.set_wavelength(initial_wl)
        self.cam.set_shots(initial_shots)
        self.sigPlanFinished.emit()

    def read_point(self, i, p):
        self.cam.set_wavelength(p, 10)
        spectra, ch = self.cam.cam.get_spectra(3)
        self.amps.append(spectra["Probe2"].frame_data[self.channel, :])  # type: ignore
        self.single_spectra[:, i] = spectra["Probe2"].frame_data[:, 1]  # type: ignore
