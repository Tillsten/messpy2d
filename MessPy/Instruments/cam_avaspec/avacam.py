import time
from threading import Lock
import attr
import numpy as np

from PySide6.QtCore import Signal, QObject
from typing import Optional

from MessPy.Instruments.interfaces import ICam, T
from MessPy.Instruments.signal_processing import Spectrum, Reading
from MessPy.Instruments.cam_avaspec.avaspec import AvantesSpec


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


@attr.define
class AvaCam(ICam):
    name: str = "AvaSpec"
    line_names: T.List[str] = ["Probe"]
    sig_names: T.List[str] = ["Probe"]
    std_names: T.List[str] = ["Probe"]
    shots: int = 50
    channels: int = 1981 - 208
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
                       valid=True)

    def get_spectra(
        self, frames: Optional[int] = None
    ) -> T.Tuple[T.Dict[str, Spectrum], T.Any]:
        # print('Starting', self.shots)
        s = self._spec
        self.lock.acquire(timeout=1)
        self._spec.start_reading(self.shots, self._spec.callback_factory())
        while self._spec.is_reading:
            time.sleep(0.010)

        s.data = s.data[208:1981, :]

        if self.background is not None:
            self._spec.data -= self.background[:, None]
        self.lock.release()

        ff = int(self._spec.analog_in[0] < 50)
        print(ff)
        spec = Spectrum.create(self._spec.data, name='Probe',
                               frames=frames, first_frame=ff)
        # if ff == 0:
        #spec.signal *= -1
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
        self.background = spec["Probe"].mean

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
        return self._spec.wl[208:1981]
