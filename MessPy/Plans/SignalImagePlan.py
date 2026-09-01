import concurrent
import concurrent.futures
from typing import ClassVar

import numpy as np
from attr import attrib, define
from loguru import logger
from PySide6.QtCore import Signal

from MessPy.ControlClasses import Reading
from MessPy.Instruments.interfaces import ICam, ILissajousScanner
from MessPy.Plans.PlanBase import ScanPlan


@define(auto_attribs=True, slots=False)
class SignalImagePlan(ScanPlan):
    cam: ICam
    xy_stage: ILissajousScanner
    positions: np.ndarray
    wavelengths: np.ndarray

    cur_image: np.ndarray = attrib(init=False)

    cur_signal: Reading = attrib(init=False)
    mean_signal: np.ndarray = attrib(init=False)
    all_signals: np.ndarray = attrib(init=False)

    shots: int = 150
    plan_shorthand: ClassVar[str] = "SignalImage"
    sigPointRead: ClassVar[Signal] = Signal()

    def setup_plan(self):
        image_shape = (
            self.positions.shape[0],
            self.positions.shape[1],
            self.cam.sig_lines,
            self.cam.channels,
        )
        self.cur_image = np.zeros(image_shape)
        self.cam.set_shots(self.shots)
        self.xy_stage.set_pos_mm(self.positions.flat[0])
        yield

    def scan(self):
        x_pos = self.positions[..., 0]
        y_pos = self.positions[..., 1]
        for self.ix, x in enumerate(x_pos[0, :]):
            for self.iy, y in enumerate(y_pos[:, 0]):
                self.time_tracker.point_starting()
                self.xy_stage.set_pos_mm(x, y)
                while not self.xy_stage.is_moving():
                    yield
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.cam.make_reading)
                while not future.done():
                    yield
                self.cur_signal = future.result()
                self.cur_image[self.iy, self.ix, :, :] = self.cur_signal.signals
                self.sigPointRead.emit()
                self.time_tracker.point_ending()
                yield

    def post_scan(self):
        logger.info("Post scan, saving data, calculating mean image")
        if self.cur_scan == 0:
            self.all_signals = self.cur_image[None, ...]

        else:
            self.all_signals = np.append(
                self.all_signals, self.cur_image[None, ...], axis=0
            )
        self.mean_signal = np.mean(self.all_signals, 0)
        self.cur_image = np.zeros_like(self.cur_image)
        assert self.cur_image.shape == self.mean_signal.shape
        fname = self.get_file_name()[0]
        np.savez(fname, data=self.all_signals, positions=self.positions)

        yield
