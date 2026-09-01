import math
from typing import Callable, Optional, Self, Union, overload

import attr
import numpy as np
from numba import njit, prange
from numpy.typing import NDArray
from scipy.constants import c

LOG10 = math.log(10)


@overload
def THz2cm(nu: float) -> float: ...


@overload
def THz2cm(nu: np.ndarray) -> np.ndarray: ...


def THz2cm(nu):
    return (nu * 1e10) / c


@overload
def cm2THz(cm: float) -> float: ...


@overload
def cm2THz(cm: np.ndarray) -> np.ndarray: ...


def cm2THz(cm):
    return c * cm / 1e10


@njit(cache=True)
def first(arr, val: float) -> int:
    for i, x in enumerate(arr):
        if x > val:
            return i
    return 0


def stats(probe, probe_max=None):
    mean, std, mi, ma = fast_stats2d(probe.astype("float64")).T
    probe_mean = mean
    probe_std = 100 * std / probe_mean
    if probe_max is not None:
        probe_max = np.nanmean(probe_max, 1)
    else:
        probe_max = ma
    return probe_mean, probe_std, probe_max


@njit(parallel=True, cache=True)
def fast_stats2d(arr):
    """
    For a given 2-dimensional array calculate mean, std, min_val and max_val along the second dimension
    in a single pass.
    """
    n = arr.shape[0]
    res = np.zeros((n, 4))
    for i in prange(n):
        res[i, :] = fast_stats(arr[i, :])
    return res


@njit(fastmath=True, cache=True)
def fast_stats(arr: NDArray[np.float64]) -> tuple[float, float, float, float]:
    """
    For a given 1-dimensional array calculate mean, std, min_val and max_val in a single pass.
    """
    s = 0
    sq_sum = 0
    n = 0
    min_val = max_val = arr[0]
    for x in arr:
        if not math.isnan(x):
            n += 1
        else:
            continue
        s += x
        sq_sum += x * x
        if x > max_val:
            max_val = x
        elif x < min_val:
            min_val = x
    mean = s / n
    var = (sq_sum - s * s / n) / n
    std = math.sqrt(var)
    return mean, std, min_val, max_val


@njit(fastmath=True, cache=True)
def fast_signal(arr: NDArray[np.float64]) -> float:
    """
    For a given 1-dimensional array calculate the signal.
    """
    sig = 0
    mean = 0
    n = arr.shape[0]

    for i in range(0, n, 2):
        sig += arr[i] - arr[i + 1]
        mean += arr[i]

    return 1000 / LOG10 * sig / mean


@njit(parallel=True, cache=True)
def fast_signal2d(arr) -> NDArray:
    """
    For a given 2-dimensional array calculate mean, std, min_val and max_val along the second dimension
    in a single pass.
    """
    n = arr.shape[0]
    res = np.zeros(n)
    for i in prange(n):
        res[i] = fast_signal(arr[i, :])
    return res


@njit(parallel=True, cache=True)
def fast_col_mean(arr, idx) -> NDArray[np.float64]:
    """
    Given a (pixel_a, pixel_b, shots) array together with a index array
    (pixel_a, pixel_b), return the mean value along the pixel_a (rows)
    dimension where the index array is true. (pixel_b, shots).

    Useful for filtering a two dimensional senor along the columns.
    """
    s = np.zeros(arr.shape[1:])
    for c in prange(arr.shape[1]):
        for r in range(arr.shape[0]):
            if idx[r, c]:
                s[c, :] += arr[r, c, :]
        s[c, :] /= idx[:, c].sum()
    return s


@attr.s(auto_attribs=True)
class Spectrum:
    data: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    max: Optional[np.ndarray]
    name: Optional[str] = None
    frame_data: Optional[np.ndarray] = None
    frames: Optional[int] = None
    first_frame: Optional[int] = None
    signal: Optional[np.ndarray] = None

    @classmethod
    def create(
        cls, data, data_max=None, name=None, frames=None, first_frame=None
    ) -> Self:
        mean, std, max = stats(data, data_max)
        signal = None
        if frames is not None:
            assert first_frame is not None
            frame_data = np.empty((mean.shape[0], frames))

            for i in range(frames):
                frame_data[:, i] = np.nanmean(data[:, i::frames], 1)
            frame_data = np.roll(frame_data, -first_frame, 1)
            if frames == 2:
                with np.errstate(invalid="ignore"):
                    signal = (
                        1000 / LOG10 * np.log1p(frame_data[:, 0] / frame_data[:, 1] - 1)
                    )
        else:
            frame_data = None

        return cls(
            data=data,
            mean=mean,
            std=std,
            name=name,
            max=max,
            signal=signal,
            frames=frames,
            frame_data=frame_data,
            first_frame=first_frame,
        )


@attr.s(auto_attribs=True, cmp=False)
class Reading:
    """Each array has the shape (n_type, pixel), except for full_data which has the shape (n_type, pixel, shots)"""

    lines: np.ndarray
    stds: np.ndarray
    signals: np.ndarray
    full_data: np.ndarray
    shots: int
    valid: bool


@attr.s(auto_attribs=True, cmp=False)
class Reading2D:
    """Has the shape (pixel, t2)"""

    spectra: Spectrum
    interferogram: np.ndarray
    t2_ps: np.ndarray
    window: Optional[Callable] = np.hanning
    upsample: int = 2
    rot_frame: float = 0
    freqs: np.ndarray = attr.ib()
    signal_2D: np.ndarray = attr.ib()
    frames: Optional[np.ndarray] = None
    ref_frames: Optional[np.ndarray] = None

    @classmethod
    def from_spectrum(
        cls,
        s: Spectrum,
        t2_ps: np.ndarray,
        rot_frame: float,
        save_frame_enabled: bool,
        ref_frames: Optional[np.ndarray] = None,
        **kwargs,
    ) -> "Reading2D":
        assert s.frame_data is not None
        f = s.frame_data
        n = s.frame_data.shape[1] / len(t2_ps)
        if n == 1:
            sig = f
        elif n == 2:
            sig = (f[:, 0::2] - f[:, 1::2]) * (-1000 / LOG10)
            sig /= 0.5 * (f[:, 0::2] + f[:, 1::2])
        elif n == 4:
            sig = ((f[:, 0::4] - f[:, 1::4]) + (f[:, 2::4] - f[:, 3::4])) * (
                -1000 / LOG10
            )  # type: np.ndarray
            sig /= f[:, 0::4] + f[:, 1::4] + f[:, 2::4] + f[:, 3::4]
        else:
            raise ValueError(f"Invalid number of frames {n}")
        assert sig.shape[1] == len(t2_ps)
        if save_frame_enabled:
            kwargs["frames"] = f
            if ref_frames is not None:
                kwargs["ref_frames"] = ref_frames
        return cls(
            spectra=s, interferogram=sig, t2_ps=t2_ps, rot_frame=rot_frame, **kwargs
        )

    @freqs.default
    def calc_freqs(self):
        freqs = np.fft.rfftfreq(
            len(self.t2_ps) * self.upsample, self.t2_ps[1] - self.t2_ps[0]
        )
        return THz2cm(freqs) + self.rot_frame

    @signal_2D.default
    def calc_2d(self):
        a = self.interferogram.copy()
        a[:, 0] *= 0.5
        if self.window is not None:
            win = self.window(a.shape[1] * 2)
            a = a * win[None, a.shape[1] :]
        return np.fft.rfft(a, a.shape[1] * self.upsample, 1).real


def signal_type(pump_on: bool, probe_on: bool) -> int:
    if pump_on and probe_on:
        return 0
    elif pump_on and not probe_on:
        return 1
    elif not pump_on and probe_on:
        return 2
    else:
        return 3


@njit(fastmath=True, cache=True)
def four_cycle_signal(
    arr: NDArray[np.float64], pump_on: NDArray[np.bool_], probe_on: NDArray[np.bool_]
) -> float:
    """
    Used when chopping both the pump and probe. For a given 1-dimensional array
    calculate the signal.
    """
    cur_window = np.zeros(4, dtype=np.float64)
    for i in range(0, arr.shape[0], 4):
        idx = signal_type(pump_on[i], probe_on[i])
        cur_window[idx] = arr[i]

    for i in range(4, arr.shape[0]):
        idx = signal_type(pump_on[i], probe_on[i])
        cur_window[idx] = arr[i]
        both_on, both_off = cur_window[0], cur_window[3]
        probe_only, pump_only = cur_window[2], cur_window[1]

        unpumped = probe_only - both_off
        pumped = both_on - pump_only
