from collections.abc import Generator
from functools import cached_property
from itertools import cycle
from typing import Any, ClassVar

import h5py
import numpy as np
from attr import attrs, field
from numpy.typing import NDArray
from PySide6.QtCore import QThread, Signal  # type: ignore

from MessPy.Instruments.interfaces import (
    ICam,
    IDelayLine,
    IRotationStage,
    IShutter,
    Reading,
    TargetThread,
)

from .PlanBase import ScanPlan


@attrs(kw_only=True, auto_attribs=True)
class NewPumpProbePlan(ScanPlan):
    shots: int
    t_points: NDArray[np.float64]
    cam: ICam

    delay_line: IDelayLine

    cur_t_idx: int = 0
    cur_wl_idx: int = 0
    cur_scan_data: NDArray[np.float64] = field(init=False)
    rot_stage: IRotationStage | None = None
    rot_angles: list[float] | None = None
    rot_idx: int = 0
    shutter_probe: IShutter | None = None
    shutter_pump: IShutter | None = None

    center_wavelengths: NDArray[np.float64] = np.array([0.0])
    reader_thread: QThread | None = None
    sigStepDone: ClassVar[Signal] = Signal()

    @cached_property
    def wl_cycle(self) -> cycle:
        return cycle(self.center_wavelengths)

    @property
    def cur_wl(self) -> float:
        return self.center_wavelengths[self.cur_wl_idx]

    def move_rot_stage(self, angle: float) -> Generator[None, Any, None]:
        if self.rot_stage and len(self.center_wavelengths) > 1:
            self.rot_stage.set_degrees(angle)
            while self.rot_stage.is_moving():
                yield

    def move_delay_line(self, t: float) -> Generator[None, Any, None]:
        self.delay_line.move_fs(t, do_wait=False)
        while self.delay_line.is_moving():
            yield

    def setup_plan(self) -> Generator:
        yield from super().setup_plan()
        self.cam.set_shots(self.shots)
        if self.shutter_probe:
            self.shutter_probe.close()
            self.cam.get_background()
        if self.shutter_pump:
            self.shutter_pump.close()
        if self.rot_stage and self.rot_angles:
            yield from self.move_rot_stage(self.rot_angles[self.rot_idx])
        self.cur_scan_data = np.zeros(
            (len(self.t_points), self.cam.channels, self.cam.lines)
        )

    def pre_scan(self) -> Generator:
        yield from super().pre_scan()
        if self.rot_stage and len(self.center_wavelengths) > 1:
            self.rot_stage.set_degrees(self.center_wavelengths[self.cur_wl_idx])
            while self.rot_stage.is_moving():
                yield

    def scan(self) -> Generator:
        assert isinstance(self.cam, ICam)
        for self.cur_t_idx, t in enumerate(self.t_points):
            self.time_tracker.point_starting()
            yield from self.move_delay_line(t)
            yield from self.read_point()
            self.time_tracker.point_ending()
            self.sigStepDone.emit()

    def read_point(self):
        assert isinstance(self.cam, ICam)
        self.reader_thread = TargetThread(self.cam.make_reading)
        self.reader_thread.start()
        while self.reader_thread.isRunning():
            yield
        assert self.reader_thread.result is not None
        reading: Reading = self.reader_thread.result
        self.save_point(reading)

    def save_point(self, reading: Reading):
        fpath = self.get_file_name()[0]
        cur_h5_path = f"/{self.cur_scan}/{self.cur_wl_idx}/{self.cur_t_idx}/"
        with h5py.File(fpath, "a") as f:
            f.create_dataset(cur_h5_path + "signal", data=reading.signals)
            f.create_dataset(cur_h5_path + "std", data=reading.stds)
            f.create_dataset(cur_h5_path + "lines", data=reading.lines)
            f.create_dataset(cur_h5_path + "full_data", data=reading.full_data)
        self.cur_scan_data[self.cur_t_idx] = reading.signals

    def post_scan(self) -> Generator:
        # create mean signals from h5 file over all scans
        fpath = self.get_file_name()[0]
        with h5py.File(fpath, "a") as f:
            for t_idx in range(len(self.t_points)):
                for scan_idx in range(self.cur_scan):
                    signal = f[f"{scan_idx}/{self.cur_wl_idx}/{t_idx}/signal"]
                    if scan_idx == 0:
                        mean_signal = np.array(signal)
                    else:
                        mean_signal += signal  # type: ignore
                mean_signal /= self.cur_scan
                f.create_dataset(
                    f"mean_signal/{self.cur_wl_idx}/{t_idx}", data=mean_signal
                )
        yield
