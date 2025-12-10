import asyncio
from typing import ClassVar, Literal

import attr
import lmfit
import numpy as np
from lmfit.model import ModelResult
from PySide6.QtCore import Signal
from scipy.special import erf

from MessPy.ControlClasses import Cam, DelayLine
from MessPy.Plans.PlanBase import Plan


@attr.s(auto_attribs=True)
class StepFitResult:
    success: bool
    params: object
    model: np.ndarray


def gaussian_step(x, x0, amp, back, sigma):
    return 0.5 * (1 + amp * erf((x - x0) / (sigma * 2))) - back


def fit_step_function(t, data) -> ModelResult:
    a = data[np.argmax(t)]
    b = data[np.argmin(t)]
    t0 = t[np.argmin(np.abs(data - (a - b) / 2))]
    sigma = 0.1
    step_amp = a - b
    back = b

    model = lmfit.Model(gaussian_step)
    fit_result = model.fit(data, x=t, amp=step_amp, back=back, sigma=sigma)
    return fit_result


@attr.s(auto_attribs=True, kw_only=True)
class AdaptiveTimeZeroPlan(Plan):
    cam: Cam
    delay_line: DelayLine
    mode: Literal["nanmean", "nanmax", "ptp"] = "nanmean"
    is_running: bool = True
    max_diff: float = 4
    auto_scale: bool = True
    start: float = -5
    stop: float = 5
    current_step: float = 0.2
    shots: int = 100
    min_step: float = 0.05
    plan_shorthand: ClassVar[str] = "AutoZero"
    positions: list[float] = attr.Factory(list)
    values: list[float] = attr.Factory(list)

    sigStepDone: ClassVar[Signal] = Signal(object)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._gen = self.make_step_generator()
        self.make_step = lambda: next(self._gen)

    def make_step_generator(self):
        yield
        dl = self.delay_line
        self.move_dl(self.start)
        cam = self.cam
        start_pos = dl.get_pos() / 1000.0
        self.cam.set_shots(self.shots)

        self.sigPlanStarted.emit()
        for i in np.arange(self.start, self.stop, self.current_step):
            self.move_dl(i)
            new_signal = self.read_point()
            self.values.append(new_signal)
            self.positions.append(i)
            self.sigStepDone.emit(self.get_data())
            cam.sigReadCompleted.emit()
            yield

        while (new_x := self.check_for_holes()) and self.is_running:
            self.check_pos(new_x)
            yield
        self.is_running = False
        self.sigPlanFinished.emit()

    def check_for_holes(self):
        x, y = self.get_data()
        xd = np.diff(x)
        yd = abs(np.diff(y) / np.ptp(y))
        i = (np.abs(yd) > self.max_diff) & (xd > self.min_step)
        if np.any(i):
            first = np.argmax(i)
            return (x[first + 1] + x[first]) / 2
        else:
            return False

    def read_point(self):
        reading = self.cam.read_cam()
        f = getattr(np, self.mode)
        return f(reading.signals[2])

    def check_pos(self, pos):
        self.move_dl(pos)
        new_signal = self.read_point()
        self.values.append(new_signal)
        self.positions.append(pos)
        self.sigStepDone.emit(self.get_data())

    def move_dl(self, pos):
        self.delay_line.set_pos(1000 * pos, True)

    def get_data(self):
        x, y = self.positions, self.values
        xa, ya = np.array(x), np.array(y)
        i = np.argsort(xa)
        xa = xa[i]
        ya = ya[i]
        return xa, ya

    def set_zero_pos(self, pos):
        self.delay_line.set_pos(pos * 1000)
        self.delay_line.set_home()
        x, y = self.get_data()
        self.positions = (x - pos).tolist()

    def save(self):
        self.save_meta()
        fpath = self.get_file_name()[0]
        x, y = self.get_data()
        np.savetxt(fpath.with_suffix(".txt"), np.column_stack((x, y)))
