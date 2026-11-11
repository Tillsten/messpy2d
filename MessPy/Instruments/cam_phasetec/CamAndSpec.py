import concurrent
import concurrent.futures
from math import log
from pathlib import Path
from typing import ClassVar

import attr
import numpy as np
from PySide6.QtCore import Signal
from scipy.stats import trim_mean

from MessPy.Instruments.cam_phasetec.imaq_newcffi import Cam
from MessPy.Instruments.cam_phasetec.spec_sp2500i import SP2150i
from MessPy.Instruments.interfaces import ICam
from MessPy.Instruments.signal_processing import (
    Reading,
    Reading2D,
    Spectrum,
    fast_col_mean,
    first,
)

LOG10 = log(10)
PROBE_CENTER = 85
PROBE_CENTER_2 = 50
REF_CENTER = 15
k = 2
PROBE_RANGE = (PROBE_CENTER - k, PROBE_CENTER + k + 1)
PROBE2_RANGE = (PROBE_CENTER_2 - k, PROBE_CENTER_2 + k + 1)
REF_RANGE = (REF_CENTER - k, REF_CENTER + k + 1)

row_defaults = {
    "Probe1": PROBE_RANGE,
    "Ref": REF_RANGE,
    "Probe2": PROBE2_RANGE,
    "back_line": (90, 110),
}


def _back_default():
    try:
        return np.load(Path(__file__).parent / "back.npy")
    except OSError:
        return None


TWO_PROBES = True


@attr.s(auto_attribs=True, kw_only=True)
class PhaseTecCam(ICam):
    spectrograph: SP2150i = attr.Factory(SP2150i)
    rows: dict[str, tuple[int, int]] = row_defaults
    name: str = "Phasetec Array"
    shots: int = 50
    has_ref: bool = True

    line_names: list[str] = ["Probe1", "Probe2", "Ref", "max"]
    std_names: list[str] = ["Probe1", "Probe2", "Ref", "Probe/Ref"]
    sig_names: list[str] = ["SigNoRef", "Sig", "Sig2NoRef", "Sig2"]

    beta1: np.ndarray | None = None
    beta2: np.ndarray | None = None
    channels: int = 128
    ext_channels: int = 0
    changeable_wavelength: bool = True
    changeable_slit: bool = False
    background: np.ndarray | None = attr.Factory(_back_default)
    can_validate_pixel: bool = True
    valid_pixel: dict[str, np.ndarray] | None = None
    frame_channel: int = 0
    _cam: Cam = attr.ib(factory=Cam)
    darklevel: int = 0
    amplification: int = 7

    sigRowsChanged: ClassVar[Signal] = Signal()

    def get_state(self):
        # The following state is saved an restored after a restart

        d = {
            "shots": self.shots,
            "rows": self.rows,
            "darklevel": self.darklevel,
            "amplification": self.amplification,
        }
        return d

    def load_state(self, exclude=None):
        super().load_state(exclude)
        if self.shots > 1000:
            self.shots = 20
        self.set_shots(self.shots)

    def set_shots(self, shots: int):
        self._cam.set_shots(shots)
        self.shots = shots

    def read_cam(self):
        return self._cam.read_cam()

    def mark_valid_pixel(self, min_val=300, max_val=12000) -> None:
        """ "
        Reads the camera and for each row-region, marks pixels which have a value within given range.
        The result is saved in an attribute.
        """
        arr, ch = self._cam.read_cam()

        self.valid_pixel = {}
        for name, (lower, upper) in self.rows.items():
            sub_arr = arr[lower:upper, :, :].mean(-1)
            self.valid_pixel[name] = (min_val < sub_arr) & (sub_arr < max_val)

    def delete_valid_pixel(self):
        self.valid_pixel = None

    def get_spectra(
        self, frames=None, **kwargs
    ) -> tuple[dict[str, Spectrum], np.ndarray]:

        arr, ch = self._cam.read_cam(back=self.background, lines=self.rows)

        if frames is not None:
            first_frame: int = first(np.array(ch[self.frame_channel]), 1)
        else:
            first_frame = 0

        spectra = {}
        means = {}
        get_max = kwargs.get("get_max", None)
        for i, (name, (lower, upper)) in enumerate(self.rows.items()):
            if self.valid_pixel is not None:
                means[name] = fast_col_mean(
                    arr[:, lower:upper, :], self.valid_pixel[name]
                )
            else:
                means[name] = self._cam.lines[:, i, :]
                # means[name] = np.nanmean(arr[lower:upper, :, :], 0)

            if get_max and name == "Probe1":
                probemax = np.nanmax(arr[:10, :, :], 0).T
            else:
                probemax = None

            spectra[name] = Spectrum.create(
                means[name],
                data_max=probemax,
                name=name,
                frames=frames,
                first_frame=first_frame,
            )
        return spectra, ch

    def make_reading(self, frame_data=None) -> Reading:
        d, ch = self.get_spectra(frames=2, get_max=True)
        probe = d["Probe1"]
        ref = d["Ref"]

        with np.errstate(invalid="ignore", divide="ignore"):
            normed = probe.data / ref.data
            norm_std = 100 * np.nanstd(normed, 1) / np.nanmean(normed, 1)

            n = first(ch[0], 1)
            if (n % 2) == 0:
                f = -1000
            else:
                f = 1000

            pu = trim_mean(normed[:, ::2], 0.2, 1)
            not_pu = trim_mean(normed[:, 1::2], 0.2, 1)

            sig = f * np.log10(pu / not_pu)
            sig_noref = d["Probe1"].signal

            # print(sig.shape, ref_mean.shape, norm_std.shape, probe_mean.shape)

            probe2 = d["Probe2"]
            normed2 = probe2.data / ref.data

            if self.beta1 is not None:
                # ref calibration available
                assert self.beta2 is not None
                dp = probe.data[:, ::2] - probe.data[:, 1::2]
                dp2 = probe2.data[:, ::2] - probe2.data[:, 1::2]
                dr = ref.data[::1, ::2] - ref.data[::1, 1::2]
                dp = dp - self.beta1.T @ dr
                dp2 = dp2 - self.beta2.T @ dr

                sig = (-f / LOG10) * np.log1p(dp.mean(1) / probe.mean)
                sig_pr2 = (-f / LOG10) * np.log1p(dp2.mean(1) / probe2.mean)
            else:
                # no ref calibration
                pu2 = trim_mean(normed2[:, ::2], 0.2, 1)
                not_pu2 = trim_mean(normed2[:, 1::2], 0.2, 1)
                sig_pr2 = -f * np.log10(pu2 / not_pu2)

            pu2 = trim_mean(probe2.data[:, ::2], 0.2, 1)
            not_pu2 = trim_mean(probe2.data[:, 1::2], 0.2, 1)

            sig_pr2_noref = probe2.signal  # f * np.log10(pu2 / not_pu2)

            reading = Reading(
                lines=np.stack((probe.mean, probe2.mean, ref.mean, probe.max)),
                stds=np.stack((probe.std, probe2.std, ref.std, norm_std)),
                signals=np.stack((sig_noref, sig, sig_pr2_noref, sig_pr2)),
                full_data=np.stack((probe.data, probe2.data, ref.data)),
                shots=self.shots,
                valid=True,
            )
        return reading

    def make_2D_reading(
        self,
        t2: np.ndarray,
        rot_frame: float,
        repetitions: int = 1,
        save_frames: bool = False,
    ) -> tuple[dict[str, Reading2D], dict[str, Spectrum]]:
        spectra, ch = self.get_spectra(frames=self.shots // repetitions, get_max=False)

        two_d_data = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for name in ("Probe1", "Probe2"):
                future = executor.submit(
                    Reading2D.from_spectrum, spectra[name], t2, rot_frame, save_frames
                )
                two_d_data[name] = future
            for name in ("Probe1", "Probe2"):
                two_d_data[name] = two_d_data[name].result()
            two_d_data["Ref"] = spectra["Ref"]
        self.two_d_data_ = two_d_data
        return two_d_data, spectra

    def calibrate_ref(self):
        tmp_shots = self.shots
        self._cam.set_shots(4000)
        # arr, ch = self._cam.read_cam()
        specs, _ = self.get_spectra()
        self._cam.set_shots(tmp_shots)

        probe = specs["Probe1"].data
        probe2 = specs["Probe2"].data
        ref = specs["Ref"].data

        # dp1 = probe[:, ::2] - probe[:, 1::2]
        # dp2 = probe2[:, ::2] - probe2[:, 1::2]
        dp1 = np.diff(probe, axis=1)
        dp2 = np.diff(probe2, axis=1)
        dr = np.diff(ref, axis=1)[::1, :]

        self.beta1 = np.linalg.lstsq(dr.T, dp1.T, rcond=-1)[0]
        self.beta2 = np.linalg.lstsq(dr.T, dp2.T, rcond=-1)[0]
        self.deltaK1 = (
            1000 / LOG10 * np.log1p((dp1 - self.beta1.T @ dr).mean(1) / probe.mean(1))
        )
        self.deltaK2 = 1000 / LOG10 * (dp2 - self.beta2.T @ dr).mean(1) / probe2.mean(1)

    def set_background(self, shots=0):
        if self.background is not None:
            self.background = None
        else:
            self._cam.read_cam(lines=self.rows, back=None)[0]
            # back_probe = np.nanmean(arr[:, :, :], 2)
            self.background = self._cam.lines.mean(-1)
            fname = Path(__file__).parent / "back"
            np.save(fname, self.background)

    def remove_background(self):
        self.background = None

    def get_wavelength_array(self, center_wl=None):
        if center_wl is None:
            center_wl = self.spectrograph.get_wavelength()
        grating = self.spectrograph._last_grating
        disp = 7.8
        if grating == 1:
            disp *= 30 / 75

        center_ch = 67
        if center_wl < 1000:
            return np.arange(-64, 64, 1)
        else:
            return (np.arange(128) - center_ch) * disp + center_wl
