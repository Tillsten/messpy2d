import os.path
import threading
import time
import typing as T
from pathlib import Path

import attr

import numpy as np
from PySide6.QtCore import Signal

from MessPy.Config import config
from MessPy.ControlClasses import Cam
from MessPy.Instruments.dac_px import AOM
from MessPy.Plans.PlanBase import Plan


@attr.s(auto_attribs=True, cmp=False)
class GVDScan(Plan):
    cam: Cam
    aom: AOM
    gvd_list: T.List[float]
    gvd_idx: int = 0
    waiting_time: float = 0.1
    timeout: float = 3
    scan_mode: T.Literal["GVD", "TOD", "FOD"] = "GVD"
    gvd: float = 0
    tod: float = 0
    fod: float = 0
    shots: int = 50
    observed_channel: T.Optional[int] = None
    settings_before: dict = attr.Factory(dict)

    sigPointRead: T.ClassVar[Signal] = Signal()

    plan_shorthand: T.ClassVar[str] = "GVDscan"

    def __attrs_post_init__(self):
        super(GVDScan, self).__attrs_post_init__()
        n_disp = len(self.gvd_list)
        n_pix = self.cam.channels
        if self.aom.calib is None:
            raise ValueError("Shaper must have an calibration")
        self.wls = np.zeros((n_disp, n_pix))
        self.probe = np.zeros((n_disp, n_pix))
        self.probe2 = np.zeros((n_disp, n_pix))
        self.ref = np.zeros((n_disp, n_pix))
        self.signal = np.zeros((n_disp, n_pix, self.cam.sig_lines))
        self.settings_before["shots"] = self.cam.shots
        self.settings_before["disp"] = self.aom.gvd
        gen = self.make_step_gen()
        self.make_step = lambda: next(gen)

    def make_step_gen(self):
        self.aom.gvd = self.gvd * 1000
        self.aom.tod = self.tod * 1000
        self.aom.fod = self.fod * 1000
        self.cam.set_shots(self.shots)

        for self.gvd_idx, value in enumerate(self.gvd_list):
            # d = {self.scan_mode: value}
            setattr(self.aom, self.scan_mode.lower(), value * 1000)
            self.aom.update_dispersion_compensation()
            time.sleep(self.waiting_time)
            self.cam.read_cam()
            assert self.cam.last_read is not None
            probe = self.cam.last_read.lines[0, :]
            probe2 = self.cam.last_read.lines[1, :]
            ref = self.cam.last_read.lines[2, :]
            sig = self.cam.last_read.signals.T

            self.probe[self.gvd_idx, :] = probe
            self.probe2[self.gvd_idx, :] = probe2
            self.ref[self.gvd_idx, :] = ref
            self.signal[self.gvd_idx, ...] = sig
            self.sigPointRead.emit()
            yield

        self.save()
        yield
        self.cam.set_shots(self.settings_before["shots"])
        self.aom.gvd = self.settings_before["disp"]
        self.aom.update_dispersion_compensation()
        self.sigPlanFinished.emit()

    def save(self):
        return
