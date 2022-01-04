from typing import TYPE_CHECKING, ClassVar, Callable, Literal, Generator

import attr
import numpy as np
from attr import attrs, attrib

from ControlClasses import Controller
from .PlanBase import Plan, ScanPlan

if TYPE_CHECKING:
    pass
from Instruments.dac_px import AOM

# from qtpy.QtWidgets import QApplication
from Instruments.signal_processing import cm2THz, THz2cm
from qtpy.QtCore import Signal
import h5py

from typing import Optional

@attrs(auto_attribs=True, kw_only=True)
class AOMTwoDPlan(ScanPlan):
    """Plan used for pump-probe experiments"""
    plan_shorthand: ClassVar[str] = "2D"
    controller: Controller
    shaper: AOM
    t3: np.ndarray
    t3_idx: int = 0
    cur_t3: float = 0
    do_stop: bool = False
    max_t2: float = 4
    step_t2: float = 0.05
    t2: np.ndarray = attrib()

    pump_freqs: np.ndarray = attrib()
    probe_freqs: np.ndarray = attrib()

    phase_frames: Literal[1, 2, 4] = 4
    rot_frame_freq: float = 0
    data_file: h5py.File = attrib()
    initial_state: dict = attr.Factory(dict)

    last_data: Optional[np.ndarray] = None

    sigStepDone: ClassVar[Signal] = Signal()

    @probe_freqs.default
    def _read_freqs(self):
        return self.controller.cam.wavenumbers

    @t2.default
    def _t2_default(self):
        t2 = np.arange(0, abs(self.max_t2) + 1e-3, self.step_t2)
        if self.max_t2 < 0:
            t2 = -t2
        return t2

    @pump_freqs.default
    def _calc_freqs(self):
        THz = np.fft.rfftfreq(self.t2.size*2, d=self.step_t2)
        return THz2cm(THz) + self.rot_frame_freq

    @data_file.default
    def _default_file(self):
        name = self.get_file_name()[0]
        f = h5py.File(name, mode='w')
        return f
        f.create_dataset("t2", data=self.t2)
        f.create_dataset("t3", data=self.t3)
        f.create_group("data")
        f['t2'].attrs['rot_frame'] = self.rot_frame_freq
        f.create_dataset("wn", data=self.controller.cam.wavenumbers)
        f.create_dataset("wl", data=self.controller.cam.wavelengths)
        return f

    def scan(self):
        c = self.controller
        for self.t3_idx, self.cur_t3 in enumerate(self.t3):
            self.time_tracker.point_starting()
            c.delay_line.set_pos(self.cur_t3*1000, do_wait=False)
            while c.delay_line.moving:
                yield
            yield from self.measure_point()
            self.time_tracker.point_ending()
            self.sigStepDone.emit()

    def setup_plan(self) -> Generator:
        for k in 'amp', 'phase', 'chopped', 'phase_cycle', 'do_dispersion_compensation':
            self.initial_state[k] = getattr(self.shaper, k)
        self.initial_state['shots'] = self.controller.cam.shots

        amp, phase = self.shaper.double_pulse(self.t2, cm2THz(self.rot_frame_freq), self.phase_frames)
        self.shaper.set_amp_and_phase(amp, phase)
        self.shaper.chopped = False
        self.shaper.phase_cycle = False
        self.shaper.do_dispersion_compensation = True
        self.shaper.generate_waveform()
        self.controller.cam.set_shots(amp.shape[1])
        yield

    def post_plan(self) -> Generator:
        for k in 'amp', 'phase', 'chopped', 'phase_cycle', 'do_dispersion_compensation':
            setattr(self.shaper, k, self.initial_state[k])
        self.shaper.generate_waveform()
        self.controller.cam.set_shots(self.initial_state[k])

    def measure_point(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.controller.cam.cam.make_2D_reading, self.t2, self.rot_frame_freq)
            while not future.done():
                yield
            ret = future.result()
        for line, data in ret.items():
            ds = self.data_file.create_dataset(f'if_data/{self.cur_scan}/{line}/{self.t3_idx}', data=data.interferogram)
            ds.attrs['time'] = self.cur_t3
            ds = self.data_file.create_dataset(f'2d_data/{self.cur_scan}/{line}/{self.t3_idx}', data=data.signal_2D)
            ds.attrs['time'] = self.cur_t3

        self.last_2d = data.signal_2D
        self.last_ir = data.interferogram
        tmp = np.save(data.spectra.frame_data)
        self.last_freq = data.freqs
