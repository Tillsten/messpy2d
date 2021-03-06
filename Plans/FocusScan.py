import threading
import typing as T
from collections import namedtuple

import attr
import numpy as np
import scipy.optimize as opt
import scipy.special as spec
from qtpy.QtCore import Signal

from ControlClasses import Cam
from Instruments.interfaces import ILissajousScanner
from Plans.PlanBase import Plan


def gauss_int(x, x0, amp, back, w):
    return 0.5 * (1 + amp * spec.erf(np.sqrt(2)*(x - x0) / w)) - back

FitResult = namedtuple('FitResult', ['success', 'params', 'model'])

def fit_curve(pos, val):
    pos = np.array(pos)
    val = np.array(val)
    a = val[np.argmax(pos)]
    b = val[np.argmin(pos)]
    x0 = [pos[np.argmin(np.abs(val - (a - b) / 2))], a - b, b, 0.1]
    def helper(p):
        return np.array(val) - gauss_int(pos, *p)

    res = opt.leastsq(helper, x0)
    fit = gauss_int(pos, *res[0])
    return FitResult(success=res[1], params=res[0], model=fit)


def make_text(name, fr):
    text = '%s\nBeamwaist: %2.3f mm \n 1/e: %2.3f mm \nFWHM %2.3f mm\nPOS %2.2f' % (
        name, fr.params[-1],  0.59*fr.params[-1], 0.64 * fr.params[-1], fr.params[0])
    return text


@attr.define
class Scan:
    axis: str
    start: float
    end: float
    step: float
    pos: list[float] = attr.Factory(list)
    probe: list[float] = attr.Factory(list)
    ref: list[float] = attr.Factory(list)
    full: list[np.ndarray] = attr.Factory(list)

    def analyze(self):
        fit_probe = fit_curve(self.pos, self.probe)
        fit_probe_txt = make_text(f'{self.axis} probe', fit_probe)
        fit_ref = fit_curve(self.pos, self.ref)
        fit_reftxt = make_text(f'{self.axis} ref', fit_ref)
        return fit_probe, fit_probe_txt, fit_ref, fit_reftxt

    def scan(self, mover, reader):
        sign = np.sign(self.end - self.end)
        for x0 in np.arange(self.start, self.end, self.step):
            yield from mover(x0)
            for data, lines in reader():
                yield
            self.pos.append(x0)
            self.probe.append(data[0])
            self.ref.append(data[1])
            self.full.append(lines)


@attr.s(auto_attribs=True, eq=False)
class FocusScan(Plan):
    """
    x_parameters and y_parameters are List [start, end, step];
    if list empty it is not measured
    """
    cam: Cam
    fh: ILissajousScanner
    plan_shorthand: T.ClassVar[str] = "FocusScan"
    x_parameters: T.Optional[list]
    y_parameters: T.Optional[list]
    shots: int = 100
    sigStepDone: T.ClassVar[Signal] = Signal()
    sigFitDone: T.ClassVar[Signal] = Signal()

    scan_x: T.Optional[Scan] = None
    scan_y: T.Optional[Scan] = None

    def __attrs_post_init__(self):
        super(FocusScan, self).__attrs_post_init__()
        if self.x_parameters:
            self.scan_x = Scan(axis='x',
                               start=self.x_parameters[0],
                               end=self.x_parameters[1],
                               step=self.x_parameters[2],
                               )
        if self.y_parameters:
            self.scan_y = Scan(axis='x',
                               start=self.x_parameters[0],
                               end=self.x_parameters[1],
                               step=self.x_parameters[2],
                               )
        self.start_pos = self.fh.pos_home
        gen = self.make_scan_gen()
        self.make_step = lambda: next(gen)
        self.cam.set_shots(self.shots)

    def make_scan_gen(self):
        if self.scan_x:
            for _ in self.scan_x.scan(lambda x: self.mover("x", x), self.reader):
                self.sigStepDone.emit()
                yield
        self.fh.set_pos_mm(*self.start_pos)
        if self.scan_y:
            for _ in self.scan_y.scan(lambda x: self.mover("y", x), self.reader):
                self.sigStepDone.emit()
                yield

        self.fh.set_pos_mm(*self.start_pos)
        self.sigFitDone.emit()
        self.sigPlanFinished.emit()
        yield

    def mover(self, axis, pos):
        if axis == 'x':
            self.fh.set_pos_mm(self.start_pos[0] + pos, None)
        if axis == 'y':
            self.fh.set_pos_mm(None, self.start_pos[1] + pos)
        yield

    def reader(self):
        t = threading.Thread(target=self.cam.read_cam)
        t.start()
        while t.is_alive():
            yield False, None
        yield self.cam.last_read.lines.mean(1), self.cam.last_read.lines

    def save(self):
        name = self.get_file_name()[0]
        self.save_meta()
        data = {'cam': self.cam.name}

        if sx := self.scan_x:
            data['scan x'] = np.vstack((sx.pos, sx.probe, sx.ref))
            data['full x'] = np.array(sx.full)
        if sx := self.scan_y:
            data['scan y'] = np.vstack((sx.pos, sx.probe, sx.ref))
            data['full y'] = np.array(sx.full)
        np.savez(name, **data)
