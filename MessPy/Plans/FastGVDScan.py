import typing as T
from pathlib import Path

import attr

import numpy as np
from PySide6.QtCore import Signal, Slot


from MessPy.ControlClasses import Cam
from MessPy.Instruments.dac_px import AOM
from MessPy.Plans.PlanBase import Plan


@attr.s(auto_attribs=True, cmp=False)
class FastGVDScan(Plan):
    """Fast GVD scan plan.

    We first calculate all shaper masks for the given GVD list and then
    read them all out at once. This is much faster than reading them out
    one by one.
    """

    cam: Cam
    aom: AOM
    gvd_list: T.List[float]
    gvd_idx: int = 0
    scan_mode: T.Literal["GVD", "TOD", "FOD"] = "GVD"
    gvd: float = 0
    tod: float = 0
    fod: float = 0
    repeats: int = 20
    observed_channel: T.Optional[int] = None
    settings_before: dict = attr.Factory(dict)

    sigPointRead: T.ClassVar[Signal] = Signal()

    plan_shorthand: T.ClassVar[str] = "FastGVDscan"

    def __attrs_post_init__(self):
        super(FastGVDScan, self).__attrs_post_init__()
        n_disp = len(self.gvd_list)
        n_pix = self.cam.channels
        if self.aom.calib is None:
            raise ValueError("Shaper must have an calibration")

        self.probe = np.zeros((n_disp, n_pix))
        self.probe2 = np.zeros((n_disp, n_pix))
        self.ref = np.zeros((n_disp, n_pix))
        self.signal = np.zeros((n_disp, n_pix))
        self.signal2 = np.zeros((n_disp, n_pix))
        self.settings_before["shots"] = self.cam.shots
        for p in ["gvd", "tod", "fod"]:
            self.settings_before[p] = getattr(self.aom, p)
        gen = self.make_step_gen()
        self.shots = self.repeats * len(self.gvd_list) * 2
        if self.shots > 10_000:
            raise ValueError(
                "Too many shots, please reduce the number of repeats or GVD Values"
            )
        self.make_step = lambda: next(gen)

    def generate_masks(self):
        self.aom: AOM
        masks = []
        gvd = self.gvd * 1000
        tod = self.tod * 1000
        fod = self.fod * 1000

        for i, val in enumerate(self.gvd_list):
            coefs = [0, gvd, tod, fod]
            if self.scan_mode == "GVD":
                coefs[1] = val * 1000
            elif self.scan_mode == "TOD":
                coefs[2] = val * 1000
            elif self.scan_mode == "FOD":
                coefs[3] = val * 1000

            phase = self.aom.generate_dispersion_compensation_phase(coefs)
            mask = self.aom.bragg_wf(self.aom.amp, -phase)
            masks.append(mask)
            # Since we also want to read out the pump-probe signal, we need to
            # add an 0 mask for the unpumped signal
            masks.append(0 * mask)

        masks = np.array(masks)
        self.aom.load_mask(masks)

    def make_step_gen(self):
        while self.status == "running":
            self.cam.set_shots(self.repeats * len(self.gvd_list))
            specs = self.cam.cam.get_spectra(len(self.gvd_list) * 2)[0]

            for s in ["Probe1", "Probe2"]:
                fd = specs[s].frame_data
                if fd is None:
                    raise RuntimeError(f"Frame data for {s} is None")
                mean = (fd[:, 0::2] + fd[:, 1::2]) / 2.0
                sig = fd[:, 0::2] - fd[:, 1::2]
                sig /= mean
                sig = -1000 * np.log10(sig)
                if s == "Probe1":
                    self.probe = mean
                else:
                    self.probe2 = mean
            yield

        self.save()
        yield

    def restore_state(self):
        self.cam.set_shots(self.settings_before["shots"])
        for p in ["gvd", "tod", "fod"]:
            setattr(self.aom, p, self.settings_before[p])
        self.aom.update_dispersion_compensation()
        self.sigPlanFinished.emit()

    def save(self):
        return

    @Slot()
    def stop_plan(self):
        self.status = "stopped"
        self.sigPlanStopped.emit()
        self.restore_state()
