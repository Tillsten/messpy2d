import functools
import concurrent.futures
import threading
import json
from pathlib import Path
from numpy._typing import NDArray
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Callable,
    ClassVar,
    Dict,
    Generator,
    Literal,
    Optional,
    Tuple,
)

import attr
import h5py
import numpy as np
from attr import attrib, attrs
from PySide6.QtCore import Signal

from MessPy.ControlClasses import Controller, config
from MessPy.Instruments.dac_px import AOM
from MessPy.Instruments.signal_processing import THz2cm, cm2THz

from .PlanBase import Plan, ScanPlan


h5py_ops = dict(
    compression="lzf", compression_opts=5, shuffle=True, chunk=True, track_order=True
)


@attrs(auto_attribs=True, kw_only=True)
class AOMTwoDPlan(ScanPlan):
    """Plan used for pump-probe experiments"""

    plan_shorthand: ClassVar[str] = "2D"
    # Instruments used, controller has cam and delay_line
    controller: Controller
    shaper: AOM

    # Waitingtime parameters
    t2: np.ndarray
    t2_idx: int = 0
    cur_t2: float = 0

    # AOM parameters
    max_t1: float = 4
    step_t1: float = 0.05
    mode: Literal["classic", "bragg"] = "bragg"
    rot_frame_freq: float = 0
    rot_frame2_freq: float = 0
    phase_frames: Literal[1, 2, 4] = 4
    aom_amplitude: float = 0.3
    repetitions: int = 1

    # Plan behavior
    initial_state: dict = attr.Factory(dict)
    do_stop: bool = False
    save_ref: bool = True
    save_frames_enabled: bool = False

    # Arrays to display
    disp_arrays: Dict[str, np.ndarray] = attr.Factory(dict)
    last_ir: Optional[np.ndarray] = None
    last_2d: Optional[Tuple[np.ndarray, np.ndarray]] = None

    # Signals
    sigStepDone: ClassVar[Signal] = Signal()
    sigNewSpectra: ClassVar[Signal] = Signal(dict)

    @functools.cached_property
    def probe_freqs(self) -> np.ndarray:
        return self.controller.cam.wavenumbers

    @functools.cached_property
    def t1(self) -> np.ndarray:
        t1: NDArray = np.arange(0, abs(self.max_t1) + 1e-3, self.step_t1)
        if self.max_t1 < 0:
            t1 = -t1
        return t1

    @functools.cached_property
    def pump_freqs(self) -> np.ndarray:
        THz = np.fft.rfftfreq(self.t1.size * 2, d=self.step_t1)
        return THz2cm(THz) + self.rot_frame_freq

    @functools.cached_property
    def data_file_name(self) -> Path:
        name = self.get_file_name()[0]
        if name.exists():
            name.unlink()
        with h5py.File(name, mode="a", track_order=True) as f:
            f["t1"] = self.t1
            f["t2"] = self.t2
            f["t1"].attrs["rot_frame"] = self.rot_frame_freq
            f["wn"] = self.controller.cam.wavenumbers
            f["wl"] = self.controller.cam.wavelengths

            grp = f.create_group("meta")
            grp.attrs["meta"] = json.dumps(self.meta)

            if config.last_results.get("ShaperCalib") is not None:
                calib = config.last_results["ShaperCalib"]
                f.create_dataset("ShaperCalib/x", data=calib["x"])
                f.create_dataset("ShaperCalib/y_train", data=calib["y_train"])
                f.create_dataset("ShaperCalib/y_single", data=calib["y_single"])
                f.create_dataset("ShaperCalib/y_full", data=calib["y_full"])
            # flat_dict(self.meta, grp)
        return name

    def scan(self):
        c = self.controller
        for self.t2_idx, self.cur_t2 in enumerate(self.t2):
            c.delay_line.set_pos(self.cur_t2 * 1000, do_wait=False)
            while c.delay_line.moving:
                yield

            yield from self.measure_point()
            self.time_tracker.point_ending()
            self.sigStepDone.emit()

    def setup_plan(self) -> Generator:
        for k in "amp", "phase", "chopped", "phase_cycle", "do_dispersion_compensation":
            self.initial_state[k] = getattr(self.shaper, k)
        self.initial_state["shots"] = self.controller.cam.shots

        self.shaper.chopped = False
        self.shaper.phase_cycle = False
        self.shaper.do_dispersion_compensation = True
        self.shaper.mode = self.mode
        self.shaper.double_pulse(
            self.t1,
            cm2THz(self.rot_frame_freq),
            cm2THz(self.rot_frame2_freq),
            self.phase_frames,
        )

        self.shaper.set_wave_amp(self.aom_amplitude)

        self.shaper.generate_waveform()
        self.controller.cam.set_shots(
            self.repetitions * (self.t1.size * self.phase_frames)
        )
        yield

    def calculate_scan_means(self):
        with h5py.File(self.data_file_name, mode="a", track_order=True) as f:
            f: h5py.File
            for line in f["ifr_data"]:  # type: ignore
                for t3_idx in f[f"ifr_data/{line}"]:  # type: ignore
                    data = []
                    specs = []
                    for scan in f[f"ifr_data/{line}/{t3_idx}"]:  # type: ignore
                        if scan == "mean":
                            continue
                        ifr = f"ifr_data/{line}/{t3_idx}/{scan}"
                        data.append(f[ifr])
                        spec = f"2d_data/{line}/{t3_idx}/{scan}"
                        specs.append(f[spec])
                    if "mean" in f[f"ifr_data/{line}/{t3_idx}/"]:  # type: ignore
                        del f[f"ifr_data/{line}/{t3_idx}/mean"]
                        del f[f"2d_data/{line}/{t3_idx}/mean"]
                    f[f"ifr_data/{line}/{t3_idx}/mean"] = np.mean(data, 0)
                    f[f"2d_data/{line}/{t3_idx}/mean"] = np.mean(specs, 0)

    def post_scan(self) -> Generator:
        thr = threading.Thread(target=self.calculate_scan_means)
        thr.start()
        self.save_meta()
        yield

    def restore_state(self):
        for k in "amp", "phase", "chopped", "phase_cycle", "do_dispersion_compensation":
            setattr(self.shaper, k, self.initial_state[k])
        self.shaper.load_full_mask()
        self.shaper.generate_waveform()
        self.controller.cam.set_shots(self.initial_state["shots"])

    def measure_point(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            self.time_tracker.point_starting()
            future = executor.submit(
                self.controller.cam.cam.make_2D_reading,
                self.t1,
                self.rot_frame_freq,
                self.repetitions,
                self.save_frames_enabled,
            )

        ret = future.result()
        self.last_spectra = ret[1]
        self.sigNewSpectra.emit(ret[1])
        self.time_tracker.point_ending()
        yield
        thr = threading.Thread(
            target=self.save_data,
            args=(
                ret[0],
                self.t2_idx,
                self.cur_scan,
            ),
        )
        thr.start()

    def save_data(self, ret, t2_idx, cur_scan):
        cur_date = datetime.now().isoformat()
        with h5py.File(self.data_file_name, mode="a", track_order=True) as f:
            data_ops = dict(
                dtype="float64", scaleoffset=2, compression="gzip", compression_opts=3
            )
            for line, data in ret.items():
                if line == "Ref":
                    if self.save_ref:
                        chunks = (1, data.frame_data.shape[1])
                        ds = f.create_dataset(
                            f"ref_data//{t2_idx}/{cur_scan}",
                            data=data.frame_data,
                            **data_ops,
                            chunks=chunks,
                        )
                        ds.attrs["creation date"] = cur_date
                        ds.attrs["time"] = self.cur_t2
                else:
                    ds = f.create_dataset(
                        f"ifr_data/{line}/{t2_idx}/{cur_scan}",
                        data=data.interferogram,
                        dtype="float32",
                    )
                    ds.attrs["time"] = self.cur_t2
                    ds.attrs["creation date"] = cur_date
                    ds = f.create_dataset(
                        f"2d_data/{line}/{t2_idx}/{cur_scan}",
                        data=data.signal_2D,
                        dtype="float32",
                    )
                    ds.attrs["time"] = self.cur_t2
                    ds.attrs["creation date"] = cur_date
                    if self.save_frames_enabled:
                        chunks = (1, data.frames.shape[1])
                        ds = f.create_dataset(
                            f"frames/{line}/{t2_idx}/{cur_scan}",
                            data=data.frames,
                            **data_ops,
                            chunks=chunks,
                        )
                        ds.attrs["creation date"] = cur_date
                    disp_2d = f.get(f"2d_data/{line}/{t2_idx}/mean", data.signal_2D)
                    disp_ifr = f.get(
                        f"ifr_data/{line}/{t2_idx}/mean", data.interferogram
                    )
                    # assert isinstance(disp_2d, h5py.Dataset)
                    # assert isinstance(disp_ifr, h5py.Dataset)

                    self.disp_arrays[line + "_spec2d"] = disp_2d[:]
                    self.disp_arrays[line + "_ifr"] = disp_ifr[:]

            self.last_2d = (
                np.array(self.disp_arrays["Probe1_spec2d"]),
                np.array(self.disp_arrays["Probe2_spec2d"]),
            )
            self.last_ir = np.array(disp_ifr)

    def stop_plan(self):
        self.do_stop = True
        super(AOMTwoDPlan, self).stop_plan()
