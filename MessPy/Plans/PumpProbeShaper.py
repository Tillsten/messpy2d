import concurrent.futures
from collections.abc import Callable, Generator
from typing import (
    ClassVar,
)

import numpy as np
from attr import define, field
from PySide6.QtCore import Signal

from MessPy.ControlClasses import Controller
from MessPy.Instruments.dac_px import AOM

from .PlanBase import Plan


@define
class PumpProbeShaperPlan(Plan):
    aom: AOM
    controller: Controller
    delays: np.ndarray
    max_scan: int = 10_000
    cur_scan: int = 0
    scan_per_reading: int = 10
    is_stopping: bool = False
    plan_shorthand = "PPShaper"
    data: list[np.ndarray] = field(factory=list)
    mean_sig: np.ndarray | None = None
    make_step: Callable = field()
    sigStepDone: ClassVar[Signal] = Signal()

    def setup(self):
        amps, phases = self.aom.delay_scan(self.delays.repeat(2))
        self.aom.set_amp_and_phase(amps, phases)
        self.aom.chopped = True
        self.aom.phase_cycle = False
        n_frames = self.aom.generate_waveform()
        self.controller.cam.set_shots(n_frames * self.scan_per_reading)

    @make_step.default
    def _pump(self):
        return self.make_step.next()

    def make_step_gen(self):
        self.setup()
        self.sigPlanStarted.emit()
        while (self.cur_scan < self.max_scan) and not self.is_stopping:
            spectra, ext = yield from self.measure_point()
            chop_sign = 1 if ext[spectra["Probe2"]][1] > 1 else -1
            for line in ["Probe1", "Probe2"]:
                spec = spectra[line]
                signal = (
                    -1000 * chop_sign * np.log10(spec.frames[::2] / spec.frames[1::2])
                )
                self.data.append(signal)
                self.mean_sig = np.mean(self.data)
            self.sigStepDone.emit()
        self.sigPlanFinished.emit()

    def measure_point(self) -> Generator:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            self.time_tracker.point_starting()
            future = executor.submit(
                self.controller.cam.cam.get_spectra, 2 * self.delays.size
            )
            while not future.done():
                yield
        self.time_tracker.point_ending()
        spectra, ext = future.result()
        yield spectra, ext

    def save(self):
        name = self.get_file_name()[0]
        wl = self.controller.cam.wavelengths
        wn = self.controller.cam.wavenumbers
        full_data = np.stack(self.data)
        self.save_meta()
        np.savez(name, wn=wn, wl=wl, full_data=full_data, mean=self.mean_sig)
