import typing as T
from pathlib import Path

import attr
import numpy as np
from loguru import logger
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
    iter: int = 0
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

        self.probe = np.zeros((n_disp, n_pix)).T
        self.probe2 = np.zeros((n_disp, n_pix)).T
        self.ref = np.zeros((n_disp, n_pix)).T
        self.signal = np.zeros((n_disp, n_pix)).T
        self.signal2 = np.zeros((n_disp, n_pix)).T
        self.settings_before["shots"] = self.cam.shots

        for p in ["gvd", "tod", "fod", "do_dispersion_compensation", "chopped"]:
            self.settings_before[p] = getattr(self.aom, p)
            
        gen = self.make_step_gen()
        self.shots = self.repeats * len(self.gvd_list) * 2
        if self.shots > 10_000:
            raise ValueError(
                "Too many shots, please reduce the number of repeats or GVD Values"
            )
        self.make_step = lambda: next(gen)
        logger.info("Plan initialized")

    def generate_masks(self):
        logger.info("Generating Masks")
        masks = []

        gvd = self.gvd * 1000
        tod = self.tod * 1000
        fod = self.fod * 1000
        self.aom.do_dispersion_compensation = False
        self.aom.chopped = False
        for i, val in enumerate(self.gvd_list):
            coefs = [0, gvd, tod, fod]
            if self.scan_mode == "GVD":
                coefs[1] = val * 1000
            elif self.scan_mode == "TOD":
                coefs[2] = val * 1000
            elif self.scan_mode == "FOD":
                coefs[3] = val * 1000

            phase = self.aom.generate_dispersion_compensation_phase(coefs)
            masks.append(phase)
            masks.append(phase) # Amp will be set to zero.
            

            # Since we also want to read out the pump-probe signal, we need to
            # add an 0 mask for the unpumped signal
        phase_masks = np.array(masks).T
        amp_masks =   np.ones_like(phase_masks)
        amp_masks[:, ::2] = 0
        self.aom.set_amp_and_phase(phase=phase_masks, amp=amp_masks)
        self.aom.generate_waveform()

    def make_step_gen(self):
        self.status = 'running'
        self.generate_masks()
        self.cam.set_shots(self.repeats * 2 * len(self.gvd_list))
        
        while self.status == 'running':
            self.specs = self.cam.cam.get_spectra(len(self.gvd_list) * 2)[0]

            self.iter = self.iter+1
            for s in ["Probe1", "Probe2"]:
                fd = self.specs[s].frame_data

                if fd is None:
                    raise RuntimeError(f"Frame data for {s} is None")
                mean = (fd[:, 0::2] + fd[:, 1::2]) / 2.0
                with np.errstate(all='ignore'):
                    sig = fd[:, 0::2] / fd[:, 1::2]    
                    sig = 1000 * np.log10(sig)
                if s == "Probe1":
                    self.probe += mean 
                    self.cur_mean = mean
                    self.cur_sig = sig
                    self.signal += sig
                else:
                    self.cur_mean2 = mean
                    self.cur_sig2 = sig
                    self.probe2 += mean
                    self.signal2 += sig
            yield
            self.sigPointRead.emit()
        self.save()
        self.sigPlanStopped.emit()
        self.restore_state()
        yield
        self.sigPlanFinished.emit()

    def restore_state(self):
        self.cam.set_shots(self.settings_before["shots"])
        for p in ["gvd", "tod", "fod", "do_dispersion_compensation", "chopped"]:
            setattr(self.aom, p, self.settings_before[p])
        self.aom.update_dispersion_compensation()
        self.aom.reset_masks()
        self.generate_masks()

    def save(self):
        return

    @Slot()
    def stop_plan(self):
        self.status = "stopped"

