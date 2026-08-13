import time
from threading import Lock
import attr
import numpy as np

from PySide6.QtCore import Signal, QObject
from typing import Optional

from MessPy.Instruments.interfaces import ICam, T
from MessPy.Instruments.signal_processing import Spectrum, Reading
from MessPy.Instruments.cam_avaspec.avaspec import AvantesSpec

if T.TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

LOWER_CHAN = 208
UPPER_CHAN = 1600

class Reader(QObject):
    dataReady = Signal()

    def __init__(self, device, parent: Optional["QObject"] = None) -> None:
        super().__init__(parent)
        self.device = device
        self.tmpdata = np.zeros((2048, 1000))
        self.cnt = 0
        self.t0 = 0
        self.shots = 1000

        @self.device._ffi.callback("void(long*, int*)")
        def cb(handle, para):
            self.tmpdata[:, self.cnt] = self.device.GetScopeData()[1]
            self.cnt += 1
            if self.cnt == self.shots:
                self.data = self.tmpdata
                self.tmpdata = np.zeros((2048, 1000))
                self.cnt = 0
                self.dataReady.emit()

        self.callback = cb


@attr.dataclass
class AvaCam(ICam):
    name: str = "AvaSpec"
    line_names: T.List[str] = ["Probe"]
    sig_names: T.List[str] = ["Probe"]
    std_names: T.List[str] = ["Probe"]
    shots: int = 50
    channels: int = UPPER_CHAN - LOWER_CHAN
    ext_channels: int = 0
    lock: Lock = attr.field(factory=Lock)
    _spec: AvantesSpec = attr.field(factory=AvantesSpec.take_nth)

    def __attrs_post_init__(self):
        super(AvaCam, self).__attrs_post_init__()
        if self.background is not None:
            self.background = np.array(self.background)

    def make_reading(self) -> Reading:
        spec = self.get_spectra(frames=2)[0]['Probe']
        return Reading(lines=spec.mean[None, :],
                       stds=np.clip(spec.std[None, :], 0, 100),
                       signals=spec.signal[None, :],
                       full_data=self._spec.data,
                       shots=self.shots,
                       valid=True)

    def get_spectra(
        self, frames: Optional[int] = None
    ) -> T.Tuple[T.Dict[str, Spectrum], T.Any]:
        # print('Starting', self.shots)
        s = self._spec
        self.lock.acquire(timeout=1)
        self._spec.start_reading(self.shots, self._spec.callback_factory())
        t_total = time.time()
        while self._spec.is_reading:
            time.sleep(0.030)
        self.lock.release()

        s.data = s.data[LOWER_CHAN:UPPER_CHAN, :]

        pump_on = self._spec.analog_in[:] < 150
        probe_on = s.data[500, :] > 10_000


        print(self._spec.analog_in[0:10])
        ff = int(pump_on[0])
        print(ff)

        # if ff == 0:
        #spec.signal *= -1
        if np.sum(probe_on[:4]) == 2:
            print(pump_on.sum(), probe_on.sum())
            both_on = (pump_on & probe_on)
            both_off = ~(pump_on | probe_on)
            pump_only = pump_on & (~probe_on)
            probe_only = (~pump_on & probe_on)

            back = s.data[:, both_off]
            probe_unpumped = s.data[:, probe_only] - back
            probe_pumped = s.data[:, both_on] - s.data[:, pump_only]
            signal = 1000*np.log10(probe_pumped.mean(1)/probe_unpumped.mean(1))
            spec = Spectrum.create(self._spec.data, name='Probe',
                        frames=frames, first_frame=ff)
            spec.signal = signal
        else:
            if self.background is not None:
                self._spec.data[:, ff::2] -= self.background[:, 0, None]
                self._spec.data[:, (1-ff)::2] -= self.background[:, 1, None]
            spec = Spectrum.create(self._spec.data, name='Probe',
                               frames=frames, first_frame=ff)
        return {"Probe": spec}, self._spec.chopper

    def set_shots(self, shots):
        self.lock.acquire()
        self.shots = shots
        self._spec.shots = shots
        self.lock.release()

    def set_background(self, shots):
        tmp = self.shots
        self.set_shots(shots)
        self.background = None
        spec = self.get_spectra(frames=2)[0]
        self.background = spec["Probe"].frame_data

        self.set_shots(tmp)

    def get_state(self) -> dict:
        if self.background is not None:
            back = self.background.tolist()
        else:
            back = None
        return {'background': back, 'shots': self.shots}

    def read_cam(self):
        self.get_spectra(2)

    def get_wavelength_array(self, center_wl):
        return self._spec.wl[LOWER_CHAN:UPPER_CHAN]

    def get_extra_widgets(self) -> "QWidget | None":
        return super().get_extra_widgets()


import PySide6.QtWidgets as qtw

@attr.dataclass
class AvacamSetting(qtw.QWidget):
    pass
    