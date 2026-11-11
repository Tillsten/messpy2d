import threading
import typing as T

import attr
import numpy as np
import scipy.optimize as opt
import scipy.special as spec
from PySide6.QtCore import Signal

from MessPy.ControlClasses import Cam
from MessPy.Instruments.interfaces import ILissajousScanner, IPowerMeter
from MessPy.Plans.PlanBase import Plan


def gauss_int(x, x0, amp, back, w):
    return 0.5 * amp * (1 + spec.erf(np.sqrt(2) * (x - x0) / w)) + back


@attr.dataclass
class FitResult:
    name: str
    success: bool
    params: np.ndarray
    pos: np.ndarray
    data: np.ndarray
    model: np.ndarray

    def make_text(self):
        text = "%s\nBeamwaist: %2.3f mm \n 1/e: %2.3f mm \nFWHM %2.3f mm\nPOS %2.2f" % (
            self.name,
            self.params[-1],
            0.59 * self.params[-1],
            0.64 * self.params[-1],
            self.params[0],
        )
        return text

    @classmethod
    def fit_curve(cls, pos, val, name):
        pos = np.array(pos)
        idx = np.argsort(pos)
        val = np.array(val)[idx]
        pos = pos[idx]
        a = val[np.argmax(pos)]
        b = val[np.argmin(pos)]
        x0 = [pos[np.argmin(np.abs(val - (a + b) / 2))], a - b, b, 0.1]

        def helper(p):
            return np.array(val) - gauss_int(pos, *p)

        res = opt.least_squares(helper, x0)
        fit = gauss_int(pos, *res.x)
        print(res.x)
        return cls(
            success=res.status > 0,
            params=res.x,
            model=fit,
            name=name,
            data=val,
            pos=pos,
        )


@attr.define
class Scan:
    axis: str
    start: float
    end: float
    step: float
    pos: list[float] = attr.Factory(list)
    probe: list[float] = attr.Factory(list)
    ref: list[float] = attr.Factory(list)
    extra: list[float] = attr.Factory(list)
    full: list[np.ndarray] = attr.Factory(list)
    min_step: float = 0.005
    max_diff: float = 0.1

    def analyze(self):
        fit_probe = FitResult.fit_curve(self.pos, self.probe, f"{self.axis} probe")
        fit_ref = FitResult.fit_curve(self.pos, self.ref, f"{self.axis} ref")
        if len(self.extra) > 0:
            fit_extra = FitResult.fit_curve(self.pos, self.extra, f"{self.axis} PW")
        else:
            fit_extra = None
        return fit_probe, fit_ref, fit_extra

    def scan(self, mover, reader):
        sign = np.sign(self.end - self.start)
        for x0 in np.arange(self.start, self.end, sign * self.step):
            yield from self.check_point(x0, reader, mover)
        while x0 := self.check_for_holes():
            yield from self.check_point(x0, reader, mover)

    def check_point(self, x, reader, mover):
        yield from mover(x)
        for data, lines, pw in reader():
            yield
        self.pos.append(x)
        self.probe.append(data[0])
        if pw is not None:
            self.extra.append(pw)
        self.ref.append(data[1])
        self.full.append(lines)

    def get_data(self):
        idx = np.argsort(self.pos)
        p, pr, ref = (
            np.array(self.pos)[idx],
            np.array(self.probe)[idx],
            np.array(self.ref)[idx],
        )
        if self.extra:
            ex = np.array(self.extra)[idx]
        else:
            ex = None
        return p, pr, ref, ex

    def check_for_holes(self):
        x, y, y3 = self.get_data()[:3]
        xd = np.diff(x)
        yd = np.diff(y) / y.ptp()
        yd3 = np.diff(y3) / y3.ptp()
        i = (np.abs(yd) > self.max_diff) & (xd > self.min_step)
        i2 = (np.abs(yd3) > self.max_diff) & (xd > self.min_step)
        i = np.logical_or(i, i2)
        if np.any(i):
            first = np.argmax(i)
            return (x[first + 1] + x[first]) / 2
        else:
            return False


@attr.s(auto_attribs=True, eq=False)
class FocusScan(Plan):
    """
    x_parameters and y_parameters are List [start, end, step];
    if list empty it is not measured
    """

    cam: Cam
    fh: ILissajousScanner
    plan_shorthand: T.ClassVar[str] = "FocusScan"
    x_parameters: list | None
    y_parameters: list | None
    z_points: list | None = None
    adaptive: bool = True
    max_rel_change: float = 0.1
    min_step: float = 0.005
    shots: int = 100
    sigStepDone: T.ClassVar[Signal] = Signal()
    sigFitDone: T.ClassVar[Signal] = Signal(int)

    scan_x: Scan | None = None
    scan_y: Scan | None = None
    scans: dict[str, Scan] = attr.Factory(dict)
    power_meter: IPowerMeter | None = None

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.z_points is None:
            self.z_points = [self.fh.get_zpos_mm()]
        self.scans = {}
        for i, z_pos in enumerate(self.z_points):
            if self.x_parameters:
                self.scans["x_%d" % i] = self.make_scan("x", self.x_parameters)
            else:
                self.scans["x_%d" % i] = None
            if self.y_parameters:
                self.scans["y_%d" % i] = self.make_scan("y", self.y_parameters)
            else:
                self.scans["y_%d" % i] = None
        self.start_pos = (0, 0)  # self.fh.pos_home
        gen = self.make_scan_gen()
        self.make_step = lambda: next(gen)
        self.cam.set_shots(self.shots)

    def make_scan(self, axis, parameters):
        return Scan(
            axis=axis,
            start=parameters[0],
            end=parameters[1],
            step=parameters[2],
            max_diff=self.max_rel_change if self.adaptive else 100,
            min_step=self.min_step,
        )

    def make_scan_gen(self):
        for i, z_pos in enumerate(self.z_points):
            self.fh.set_pos_mm(*self.start_pos)
            self.fh.set_zpos_mm(z_pos)
            while any(self.fh.is_moving()):
                yield
            if self.scans[f"x_{i}"]:
                for _ in self.scans[f"x_{i}"].scan(
                    lambda x: self.mover("x", x), self.reader
                ):
                    self.sigStepDone.emit()
                    yield
            self.fh.set_pos_mm(*self.start_pos)
            if self.scans[f"y_{i}"]:
                for _ in self.scans[f"y_{i}"].scan(
                    lambda x: self.mover("y", x), self.reader
                ):
                    self.sigStepDone.emit()
                    yield

            self.fh.set_pos_mm(*self.start_pos)
            self.sigFitDone.emit(i)
        self.sigPlanFinished.emit()
        yield

    def mover(self, axis, pos):
        if axis == "x":
            self.fh.set_pos_mm(self.start_pos[0] + pos, None)
        if axis == "y":
            self.fh.set_pos_mm(None, self.start_pos[1] + pos)
        while any(self.fh.is_moving()):
            yield
        yield

    def reader(self):
        t = threading.Thread(target=self.cam.read_cam)
        t.start()
        if self.power_meter is not None:
            f = self.power_meter.read_power()
        else:
            f = None
        while t.is_alive():
            yield False, None, None
        yield self.cam.last_read.lines.mean(1), self.cam.last_read.lines, f

    def save(self):
        name = self.get_file_name()[0]
        self.save_meta()
        data: dict[str, object] = {"cam": self.cam.name}
        data["z_points"] = self.z_points
        for i, z_pos in enumerate(self.z_points):
            for axis in ["x", "y"]:
                if sx := self.scans[f"{axis}_{i}"]:
                    data[f"z={i} scan {axis}"] = np.vstack((sx.pos, sx.probe, sx.ref))
                    data[f"z={i} full {axis}"] = np.array(sx.full)
                    if len(sx.extra) > 0:
                        data[f"z={i} extra {axis}"] = sx.extra
        np.savez(name, **data)
