from MessPy.Instruments.interfaces import IDevice
from PySide6.QtCore import Signal, QMutex
from loguru import logger
from pathlib import Path
from typing import Optional, Literal
from typing import TYPE_CHECKING, Tuple

import attr
import numpy as np

from MessPy.Instruments.dac_px.shaper_calculations import (
    double_pulse_mask,
    delay_scan_mask,
    cm2THz,
    THz2cm,
)

if TYPE_CHECKING:
    from MessPy.Instruments.dac_px.pxdac import PXDAC

PIXEL = 4096 * 3  # 12288
MAX_16_Bit = (1 << 13) - 1


def default_dac():
    from MessPy.Instruments.dac_px.pxdac import PXDAC

    return PXDAC.DAC(1)


@attr.s(auto_attribs=True)
class AOM(IDevice):
    dac: "PXDAC.DAC" = attr.Factory(default_dac)
    name: str = "Phasetech AOM"
    lock: QMutex = attr.Factory(QMutex)

    amp_fac: float = 1.0
    wave_amp: float = 0.4
    calib: Optional[np.ndarray] = None
    nu: Optional[np.ndarray] = None
    nu0_THz: float = 55
    dac_freq_MHz: float = 1200
    rf_freq_MHz: float = 75
    pixel: np.ndarray = np.arange(PIXEL)

    compensation_phase: Optional[np.ndarray] = None
    compensation_amp: Optional[np.ndarray] = None
    phase: Optional[np.ndarray] = np.zeros((PIXEL, 1))
    amp: np.ndarray = np.ones((PIXEL, 1))
    total_phase: Optional[np.ndarray] = np.zeros(PIXEL)
    mask: np.ndarray = np.zeros_like(PIXEL)
    is_running: bool = False

    chopped: bool = True
    chop_mode: Literal["standard", "window"] = "standard"
    chop_window: tuple[float, float] = (-np.inf, np.inf)
    do_dispersion_compensation: bool = True
    phase_cycle: bool = True
    mode: Literal["bragg", "classic"] = "bragg"

    delay: float = 0
    gvd: float = 0
    tod: float = 0
    fod: float = 0

    sigCalibChanged = Signal(object)
    sigDispersionChanged = Signal(tuple)
    sigModeChanged = Signal(str)

    def __attrs_post_init__(self):
        super(AOM, self).__attrs_post_init__()
        self.setup_dac()

    def get_state(self) -> dict:
        d = {
            "calib": self.calib.tolist() if self.calib is not None else None,
            "delay": self.delay,
            "gvd": self.gvd,
            "fod": self.fod,
            "tod": self.tod,
            "wave_amp": self.wave_amp,
            "chopped": self.chopped,
            "do_dispersion_compensation": self.do_dispersion_compensation,
            "phase_cycle": self.phase_cycle,
            "mode": self.mode,
            "nu0_THz": self.nu0_THz,
            "amp_fac": self.amp_fac,
        }
        return d

    def load_state(self):
        super(AOM, self).load_state()

        if self.calib:
            self.set_calib(self.calib)
            self.update_dispersion_compensation()
        self.set_wave_amp(self.wave_amp)

    def setup_dac(self):
        self.lock.lock()
        dac = self.dac
        dac.SetDacSampleSizeXD48(2)
        log = logger
        log.info("Size: %s " % dac.GetDacSampleSizeXD48(1))
        log.info("Format: %s" % dac.GetDacSampleFormatXD48(1))

        log.info("Output Voltage %s" % dac.get_output_voltage())
        dac.set_output_voltage(ch1=200, ch2=1000)
        log.info("Output Voltage %s" % dac.get_output_voltage())
        dac.SetExternalTriggerEnableXD48(1)
        log.info("ExtTrigger %s" % dac.GetExternalTriggerEnableXD48(1))
        dac.SetTriggerModeXD48(0)
        dac.SetActiveChannelMaskXD48(0x1 | 0x2)
        dac.SetDacSampleSizeXD48(1)
        self.lock.unlock()


    def generate_dispersion_compensation_phase(self, coefs):
        """
        Generates the dispersion compensation phase from the coefficients.

        Parameters
        ----------
        coefs : list
            List of coefficients for the dispersion compensation polynomial.
            E.g. [delay, gvd, tod, fod]
        """
        if self.nu is None:
            raise ValueError("No calibration available")
        x = self.nu - self.nu0_THz
        x *= (2 * np.pi) / 1000
        # PHz -> disp params in fs^-n (n=2,3,4)
        coef = np.asarray(coefs) 
        coef = coef / np.array([1, 2, 6, 24])
        phase = x * coef[0] + x**2 * coef[1] + x**3 * coef[2] + x**4 * coef[3]
        return phase[:, None]

    def update_dispersion_compensation(self):
        """
        Updates the dispersion correction phase from the class attributes.
        """
        if self.nu is None:
            raise ValueError("No calibration available")
        x = self.nu - self.nu0_THz
        x *= (2 * np.pi) / 1000  # PHz -> disp params in fs^-n (n=2,3,4)
        coef = np.array([self.delay, self.gvd, self.tod, self.fod])
        phase = self.generate_dispersion_compensation_phase(coef)
        self.do_dispersion_compensation = True
        self.compensation_phase = -phase[:, None]
        logger.info(
            "Updating dispersion compensation %1.f %.2f %.2e %.2e %.2e",
            self.nu0_THz,
            self.delay,
            self.gvd,
            self.tod,
            self.fod,
        )
        self.sigDispersionChanged.emit((self.gvd, self.tod, self.fod))
        self.generate_waveform()

    def set_calib(self, p):
        """
        Sets a new calibration polynomial p.
        """
        self.calib = np.array(p)
        np.save(Path(__file__).parent / "calib_coef.npy", self.calib)
        self.nu = np.polyval(p, self.pixel)
        self.sigCalibChanged.emit(self.calib)
        self.save_state()

    def bragg_wf(self, amp, phase):
        """Calculates a Bragg-correct AOM waveform for given phase and shape"""
        assert self.calib is not None
        F = np.poly1d(np.polyint(self.calib))
        phase_term = (
            2
            * np.pi
            * F(self.pixel)
            / self.nu0_THz
            * self.rf_freq_MHz
            / self.dac_freq_MHz
        )
        phase_term = phase + phase_term[:, None]
        return amp * np.cos(phase_term)

    def classic_wf(self, amp, phase):
        """Calculates a uncorrected AOM waveform for given amplitude and shape"""
        f = self.dac_freq_MHz / self.rf_freq_MHz
        return amp * np.cos(self.pixel[:, None] / f * 2 * np.pi + phase)

    def double_pulse(
        self,
        taus: np.ndarray,
        rot_frame: float,
        rot_frame2: float,
        phase_frames: Literal[1, 2, 4] = 4,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the masks for creating a series a double pulses with phase cycling.
        """
        if self.nu is None:
            raise ValueError("Spectral calibration is required to calculate the masks.")
        phase = np.pi * np.array([(1, 1), (1, 0), (0, 0), (0, 1)])
        phase = phase[:phase_frames, :]
        phase = np.tile(phase, (taus.shape[0], 1))
        phi1 = phase[:, 0]
        phi2 = phase[:, 1]
        taus = taus.repeat(phase_frames)
        masks = double_pulse_mask(
            self.nu[:, None],
            rot_frame,
            taus[None, :],
            phi1[None, :],
            phi2[None, :],
            rot_frame2,
        )

        self.set_amp_and_phase(np.abs(masks), np.angle(masks))
        return masks

    def delay_scan(self, taus, phi=None):
        assert self.nu is not None
        taus = np.atleast_1d(taus)
        if phi is None:
            phi = np.zeros(PIXEL)
        mask = delay_scan_mask(self.nu[:, None], taus[None, :], phi[None, :])
        return np.ones(PIXEL), mask

    def set_amp_and_phase(
        self, amp: Optional[np.ndarray] = None, phase: Optional[np.ndarray] = None
    ):
        """
        Sets the amplitude and/or the phase of the spectral map.
        Notice that the compensation dispersion phase will be added separately.
        """
        if phase is not None:
            if len(phase.shape) == 1:
                phase = phase[:, None]
            self.phase = phase
        if amp is not None:
            if len(amp.shape) == 1:
                amp = amp[:, None]
            self.amp = amp

    def generate_waveform(self) -> int:
        """
        Actually generates the waveform from set phase and amp. If turned on,
        it will also add the dispersion compensation phase in addition.
        Depending on the `mode` attribute, it will either use a bragg corrected
        waveform or the classic waveform.

        Returns the number of frames
        """
        if self.compensation_phase is not None and self.do_dispersion_compensation:
            phase = self.phase - self.compensation_phase
        else:
            phase = self.phase

        self.total_phase = phase

        if self.compensation_amp is not None:
            total_amp = self.amp * self.compensation_amp
        else:
            total_amp = self.amp

        if self.mode == "bragg" and self.calib is not None:
            masks = self.bragg_wf(total_amp, self.total_phase)
        else:
            masks = self.classic_wf(total_amp, self.total_phase)

        if self.chopped:
            if self.chop_mode == "standard":
                masks = np.concatenate((0 * masks, masks), axis=1)
            elif self.chop_mode == "window":
                wn = THz2cm(self.nu)
                idx = (wn > self.chop_window[0]) & (wn < self.chop_window[1])
                mask2 = masks.copy()
                mask2[idx, :] = 0
                masks = np.concatenate((mask2, masks), axis=1)
        if self.phase_cycle:
            masks = np.concatenate((masks, -1 * masks), axis=1)
        return self.load_mask(masks)

    def voltage(self, i: int):
        if not (0 <= i < 1023):
            raise ValueError(i)
        self.lock.lock()
        self.dac.set_output_voltage(ch1=i)
        self.lock.unlock()

    def set_wave_amp(self, amp):
        """
        Sets the amplitude of RF-wave. This is archived in two ways. If possible, just the output voltage of the DAC
        is varied. Since this has a lower limit, a set-point below 0.56 is achieved by scaling the array containing
        the waveform, hence it requires a recalculation of the waveform which normally uses the full scale of the DAC.
        """
        if not (0 <= amp <= 1):
            raise ValueError("Amplitude has to be between 0 and 1")
        self.wave_amp = amp
        V = 1.4 * amp
        if V > 0.4:
            k = int((V - 0.4) * 1023)
            self.voltage(k)
            self.amp_fac = 1
        else:
            self.voltage(0)
            f = V / 0.4
            self.amp_fac = f
            self.load_mask()

    def load_mask(self, mask=None):
        if mask is not None:
            self.mask = mask

        if len(self.mask.shape) == 2:
            assert self.mask.shape[0] == PIXEL
            self.mask = self.mask.ravel(order="F")

        mask = (self.amp_fac * MAX_16_Bit * self.mask).astype("int16")
        self.scaled_mask = mask
        assert mask.dtype == np.int16
        assert (mask.size % PIXEL) == 0
        frames = mask.size // PIXEL
        self.end_playback()
        mask1 = np.zeros_like(mask)
        mask1[:PIXEL] = MAX_16_Bit
        full_mask = np.zeros(mask.size * 2, dtype=np.int16)
        full_mask[::2] = mask
        full_mask[1::2] = mask1
        self.full_mask = full_mask
        self.lock.lock()
        self.dac.LoadRamBufXD48(0, full_mask.size * 2, full_mask.ctypes.data, 0)
        self.start_playback()
        self.lock.unlock()
        return frames

    def start_playback(self):
        """Start playback of the current mask"""
        self.dac.BeginRamPlaybackXD48(0, self.full_mask.size * 2, PIXEL * 2 * 2)
        self.is_running = True

    def end_playback(self):
        """End playback of the current mask"""
        self.dac.EndRamPlaybackXD48()
        self.is_running = False

    def make_calib_mask(self, width=40, separation=350, single=6000):
        """
        Calculates a calibration mask onto the shaper.
        """
        full_mask = np.cos(np.arange(PIXEL) / 16 * 2 * np.pi)
        m = np.zeros_like(full_mask)
        cur_pos = single
        while cur_pos < PIXEL:
            m += np.exp(-0.5 * (self.pixel - cur_pos) ** 2 / width**2)
            cur_pos += separation
        cur_pos = single - separation
        while cur_pos > 0:
            m += np.exp(-0.5 * (self.pixel - cur_pos) ** 2 / width**2)
            cur_pos -= separation
        pulse_train_mask = m * full_mask
        m = np.exp(-0.5 * (self.pixel - single) ** 2 / width**2)
        single_mask = m * full_mask
        mask = np.stack((pulse_train_mask, single_mask, full_mask), axis=1)
        return mask

    def load_calib_mask(self, width=50, separation=350, n_single=15):
        """
        Sets a calibration mask onto the shaper.
        """
        mask = self.make_calib_mask(width, separation, n_single)
        self.load_mask(mask)

    def load_full_mask(self):
        """Loads a full mask using a frequency of 75 MHz"""
        self.set_amp_and_phase(np.ones(PIXEL), np.zeros(PIXEL))
        logger.info("Loading full mask")
        full_mask = np.cos(np.arange(PIXEL) / 16 * 2 * np.pi)
        self.load_mask(full_mask)

    def set_compensation_amp(self, x0=2150, width=200):
        assert self.nu is not None
        x0 = 1650
        x0_nu = cm2THz(x0)
        width = 50
        xw = abs(x0_nu - cm2THz(x0 + width))
        print(x0_nu, xw)
        amp_f = np.zeros_like(self.nu)
        amp_f[(self.nu < x0_nu + xw) & (self.nu > x0_nu - xw)] = 1
        amp = np.exp(-0.5 * (self.nu - x0_nu) ** 2 / xw**2)[:, None]
        self.compensation_amp = amp  # [:, None]


from MessPy.Instruments.interfaces import IShutter


@attr.dataclass(kw_only=True)
class AOMShutter(IShutter):
    name: str = "AOM Playback"
    aom: AOM = attr.ib()

    def toggle(self):
        if self.aom.is_running:
            self.aom.end_playback()
            self.sigShutterToggled.emit(True)
        else:
            self.aom.start_playback()
            self.sigShutterToggled.emit(False)

    def is_open(self) -> bool:
        return self.aom.is_running


if __name__ == "__main__":
    A = AOM()

    width = 40
    seperation = 400
    amp, phase = [], []
    for i in Path("C:\PhaseTech\masks").glob("*"):
        d = np.loadtxt(i)
        amp.append(d[:, 0])
        phase.append(d[:, 1])
    amp = np.array(amp).T
    phase = np.array(phase).T
    np.save("pt_masks_amp_2000_50.npy", amp)
    np.save("pt_masks_amp_2000_50.npy", phase)
    A.do_dispersion_compensation = False
    A.compensation_phase = None
    A.chopped = False
    A.phase_cycle = False
    A.mode = "classic"
    A.nu0_THz = cm2THz(2010)
    A.set_amp_and_phase(amp, phase)
    A.generate_waveform()
    exit()
    for i in np.arange(1960, 2060, 10):
        full_mask = np.cos(np.arange(PIXEL) / 16 * 2 * np.pi)
        full_mask *= np.exp(-0.5 * (THz2cm(A.nu) - i) ** 2 / 5**2)
        # A.load_mask(full_mask)
        # time.sleep(0.1)
    # full_mask += np.exp(-0.5*(THz2cm(A.nu)-2000)**2/5**2) * np.cos(np.arange(PIXEL) / 16 * 2 * np.pi)
    # m = A.make_calib_mask(separation=300, width=40)
    # A.load_mask(m[:, 0])
    om = 2 * np.pi * A.nu[:, None]
    # masks = np.cos(om * taus / 2) * np.exp(1j * om * taus)
    A.do_dispersion_compensation = False
    A.compensation_phase = None
    A.chopped = False
    A.phase_cycle = False
    A.mode = "classic"
    A.nu0_THz = cm2THz(2010)
    A.double_pulse(np.arange(0, 2.03, 0.05), 2, 2)

    print(A.amp.shape)

    # amp = np.float64(abs(THz2cm(A.nu)-1940) < 10)[:, None]
    # A.set_amp_and_phase(amp=amp, phase=np.zeros_like(amp))
    A.generate_waveform()
    # print(f"{amp.shape=}")

    print(A.calib)
    exit()
    import pyqtgraph as pg

    app = pg.mkQApp()
    pg.plot(full_mask).show()
    app.exec_()
