from pathlib import Path
import numpy as np
import wrapt
from Instruments.interfaces import ICam
from Instruments.signal_processing import Reading, Spectrum, first, fast_col_mean
from Config import config
import attr

# from ir_cam import PT_MCT
from .imaq_nicelib import Cam
from .spec_sp2500i import SP2500i
from typing import List, Optional, Tuple, Dict
from scipy.stats import trim_mean

LOG10 = np.log(10)
PROBE_CENTER = 115
PROBE_CENTER_2 = 70
REF_CENTER = 26
k = 3
PROBE_RANGE = (PROBE_CENTER - k, PROBE_CENTER + k + 1)
PROBE2_RANGE = (PROBE_CENTER_2 - k, PROBE_CENTER_2 + k + 1)
REF_RANGE = (REF_CENTER - k, REF_CENTER + k + 1)

TWO_PROBES = True


@attr.s(auto_attribs=True)
class PhaseTecCam(ICam):
    _spec: SP2500i = attr.ib()
    probe_rows: Tuple[int, int] = attr.ib()
    ref_rows: Tuple[int, int] = attr.ib()
    name: str = 'Phasetec Array'
    shots: int = config.shots

    if not TWO_PROBES:
        line_names: List[str] = ['Probe', 'Ref', 'max']
        std_names: List[str] = ['Probe', 'Ref', 'Probe/Ref']
        sig_names: List[str] = ['Sig', 'SigNoRef']
    else:
        probe2_rows: Tuple[int, int] = attr.ib()
        line_names: List[str] = ['Probe', 'Probe2', 'Ref', 'max']
        std_names: List[str] = ['Probe', 'Probe2', 'Ref', 'Probe/Ref']
        sig_names: List[str] = ['SigNoRef', 'Sig',  'Sig2NoRef', 'Sig2']
    beta1: Optional[object] = None
    beta2: Optional[object] = None
    channels: int = 128
    ext_channels: int = 0
    changeable_wavelength: bool = True
    changeable_slit: bool = False
    background: Optional[np.ndarray] = attr.ib()
    valid_pixel: Optional[List[np.ndarray]] = None
    _cam: Cam = attr.ib(factory=Cam)

    @probe_rows.default
    def _probe_rows_default(self):
        if hasattr(config, 'probe_rows'):
            return config.probe_rows
        else:
            return PROBE_RANGE

    @probe2_rows.default
    def _probe_rows_default(self):
        if hasattr(config, 'probe2_rows'):
            return config.probe_rows
        else:
            return PROBE2_RANGE

    @ref_rows.default
    def _ref_rows_default(self):
        if hasattr(config, 'probe_rows'):
            return config.probe_rows
        else:
            return REF_RANGE

    @_spec.default
    def _default_spec(self):
        return SP2500i(comport='COM4')

    @background.default
    def _back_default(self):
        try:
            return np.load(Path(__file__).parent / 'back.npy')
        except IOError:
            pass
        return None

    def __attr_post_init__(self):
        super(PhaseTecCam, self).__attr_post_init__()

    def get_state(self):
        d = {
            'shots': self.shots,
            'probe_rows': self.probe_rows,
            'ref_rows': self.ref_rows,
            'probe2_rows': self.probe2_rows
        }
        return d

    def load_state(self):
        super().load_state()
        self.set_shots(self.shots)

    def set_shots(self, shots: int):
        self._cam.set_shots(shots)
        self.shots = shots

    def read_cam(self):
        return self._cam.read_cam()

    def mark_valid_pixel(self,  min_val=1000, max_val=8000):
        arr, ch = self._cam.read_cam()

        pr_range = self.probe_rows
        ref_range = self.ref_rows
        pr2_range = self.probe2_rows

        self.valid_pixel = []
        for (l, u) in [pr_range, ref_range, pr2_range,]:
            sub_arr = arr[l:u, :, :]
            self.valid_pixel += [(min_val < sub_arr) & (sub_arr < max_val)]

    def delete_valid_pixel(self):
        self.valid_pixel = None

    def get_spectra(self, frames=None) -> Tuple[Dict[str, Spectrum], object]:
        arr, ch = self._cam.read_cam()
        if self.background is not None:
            arr = arr - self.background[:, :, None]
        if frames is not None:
            first_frame = first(np.array(ch[0]), 1)
        else:
            first_frame = None

        pr_range = self.probe_rows
        pr2_range = self.probe2_rows
        ref_range = self.ref_rows

        if self.valid_pixel is not None:
            probe = fast_col_mean(arr[pr_range[0]:pr_range[1], ...], self.valid_pixel[0])
            ref = fast_col_mean(arr[ref_range[0]:ref_range[1], ...], self.valid_pixel[1])
            if TWO_PROBES:
                probe2 = fast_col_mean(arr[pr2_range[0]:pr2_range[1], ...], self.valid_pixel[2])
        else:
            probe = np.nanmean(arr[pr_range[0]:pr_range[1], :, :], 0)
            ref = np.nanmean(arr[ref_range[0]:ref_range[1], :, :], 0)
            if TWO_PROBES:
                probe2 = np.nanmean(arr[pr2_range[0]:pr2_range[1], :, :], 0)

        probemax = np.nanmax(arr[:, :, :10], 0)
        probe = Spectrum.create(probe, probemax, name='Probe1', frames=frames, first_frame=first_frame)
        ref = Spectrum.create(ref, name='Ref', frames=frames, first_frame=first_frame)

        if TWO_PROBES:
            probe2 = Spectrum.create(probe2, name='Probe2', frames=frames, first_frame=first_frame)
        return {i.name: i for i in (probe, probe2, ref)}, ch

    def make_reading(self, frame_data=None):
        d, ch = self.get_spectra(frames=2)
        probe = d['Probe1']
        ref = d['Ref']

        with np.errstate(invalid='ignore', divide='ignore'):
            normed = probe.data / ref.data
            norm_std = 100 * np.nanstd(normed, 1) / np.nanmean(normed, 1)

            n = first(ch[0], 1)
            if (n % 2) == 0:
                f = 1000
            else:
                f = -1000


            pu = trim_mean(normed[:, ::2], 0.2, 1)
            not_pu = trim_mean(normed[:, 1::2], 0.2, 1)

            sig = f * np.log10(pu / not_pu)
            sig2 = d['Probe1'].signal

        # print(sig.shape, ref_mean.shape, norm_std.shape, probe_mean.shape)
        if not TWO_PROBES:
            reading = Reading(lines=np.stack(
                (probe.mean, ref.mean, probe.max)),
                              stds=np.stack((probe.std, ref.std, norm_std)),
                              signals=np.stack((sig, sig2)),
                              valid=True)

        else:

            probe2 = d['Probe2']
            normed2 = probe2.data / ref.data


            pu2 = trim_mean(normed2[:, ::2], 0.2, 1)
            not_pu2 = trim_mean(normed2[:, 1::2], 0.2, 1)
            sig_pr2 = f * np.log10(pu2 / not_pu2)

            pu2 = trim_mean(probe2.data[:, ::2], 0.2, 1)
            not_pu2 = trim_mean(probe2.data[:, 1::2], 0.2, 1)
            sig_pr2_noref = f * np.log10(pu2 / not_pu2)

            if self.beta1 is not None:
                dp = probe.data[:, ::2] - probe.data[:, 1::2]
                dp2 = probe2.data[:, ::2] - probe2.data[:, 1::2]
                dr = np.diff(ref.data[::16, :], axis=1)
                dp = (dp - self.beta1 @ dr)
                dp2 = (dp2 - self.beta2 @ dr)

                sig = f / LOG10 * np.log1p(dp.mean(1) / probe.mean(1))
                sig_pr2 = f / LOG10 * np.log1p(dp2.mean(1) / probe2.mean(1))

            which = 1 if (ch[0][0] > 1) else 0
            reading = Reading(lines=np.stack(
                (probe.mean, probe2.mean, ref.mean, probe.max)),
                              stds=np.stack(
                                  (probe.std, probe2.std, ref.std, norm_std)),
                              signals=np.stack(
                                  (sig2, sig, sig_pr2_noref, sig_pr2)),
                              valid=True)
            #
        return reading

    def calibrate_ref(self):
        tmp_shots = self.shots
        self._cam.set_shots(10000)
        arr, ch = self._cam.read_cam()
        self._cam.set_shots(tmp_shots)
        if self.background is not None:
            arr = arr - self.background[:, :, None]
        pr_range = self.probe_rows
        ref_range = self.ref_rows
        probe = np.nanmean(arr[pr_range[0]:pr_range[1], :, :], 0)
        dp1 = np.diff(probe, axis=1)
        ref = np.nanmean(arr[ref_range[0]:ref_range[1], :, :], 0)

        dr = np.diff(ref[::16, :], axis=1)
        self.beta1 = np.linalg.lstsq(dp1.T, dr.T)[0]
        self.deltaK1 = 1000 / LOG10 * np.log1p(
            (dp1 - self.beta1 @ dr).mean(1) / probe.mean(1))

        if TWO_PROBES:
            probe2 = np.nanmean(arr[PROBE2_RANGE[0]:PROBE2_RANGE[1], :, :], 0)
            dp2 = np.diff(probe2, axis=1)
            self.beta2 = np.linalg.lstsq(dp2.T, dr.T)[0]
            self.deltaK2 = 1000 / LOG10 * (
                dp2 - self.beta2 @ dr).mean(1) / probe2.mean(1)

    def get_wavelength(self):
        return self._spec.get_wavelength()

    def set_wavelength(self, wl, timeout):
        return self._spec.set_wavelength(wl, timeout=timeout)

    def set_background(self, shots=0):
        arr = self._cam.read_cam()[0]
        back_probe = np.nanmean(arr[:, :, :], 2)
        self.background = back_probe

        fname = Path(__file__).parent / 'back'
        np.save(fname, back_probe)

    def remove_background(self):
        self.background = None

    def get_wavelength_array(self, center_wl):
        center_wl = self.get_wavelength()
        disp = 7.69
        center_ch = 63
        if center_wl < 1000:
            return np.arange(-64, 64, 1)
        else:
            return (np.arange(128) - center_ch) * disp + center_wl

    @property
    def gratings(self) -> Dict[int, str]:
        return {0: '75', 1: '30'}

    def set_grating(self, idx: int):
        self._spec.set_grating(idx)

    def get_grating(self) -> int:
        return self._spec.get_grating()

_ircam = PhaseTecCam()
