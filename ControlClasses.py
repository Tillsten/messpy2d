import numpy as np
from attr import attrs, attrib, Factory
from Config import config
import threading, time
import typing as T
from HwRegistry import _cam, _cam2, _dl, _dl2, _rot_stage, _shutter
import Instruments.interfaces as I

from qtpy.QtCore import QObject, Slot, Signal
from qtpy.QtWidgets import QApplication


@attrs
class ReadData:
    shots: int = attrib()
    det_a = attrib()
    det_b = attrib()
    ext = attrib()
    chopper = attrib()
    gives_full_data: bool = attrib(False)


@attrs(cmp=False)
class Cam(QObject):
    cam: I.ICam = attrib(_cam)
    shots: int = attrib(config.shots)
    sigShotsChanged: Signal = Signal('int')
    sigReadCompleted: Signal = Signal()
    back: tuple = attrib((0, 0))
    last_read: 'LastRead' = attrib(init=False)
    sigWavelengthChanged = Signal('float')
    wavelengths: np.ndarray = attrib(init=False)
    wavenumbers: np.ndarray = attrib(init=False)
    disp_axis: np.ndarray = attrib(init=False)
    disp_wavelengths: bool = True

    def __attrs_post_init__(self):
        super().__init__()
        self.last_read = LastRead(self)
        self.last_read.update()
        c = self.cam
        self.channels = c.channels
        self.lines = c.lines
        self.sig_lines = c.sig_lines
        self.changeable_wavelength = c.changeable_wavelength
        self.wavelengths = self.get_wavelengths()
        self.wavenumbers = 1e7/self.wavelengths
        self.disp_axis = self.wavelengths.copy()

        self.sigWavelengthChanged.connect(self._update_wl_arrays)

    def _update_wl_arrays(self, cwl=None):
        self.wavelengths[:] = self.get_wavelengths()
        self.wavenumbers[:] = 1e7 / self.wavelengths
        if self.disp_wavelengths:
            self.disp_axis[:] = self.wavelengths
        else:
            self.disp_axis[:] = self.wavenumbers

    def set_disp_wavelengths(self, use_wl):
        self.disp_wavelengths = not use_wl
        self._update_wl_arrays()

    def set_shots(self, shots):
        """Sets the number of shots recorded"""
        self.shots = shots
        self.cam.set_shots(int(shots))
        config.shots = shots
        self.sigShotsChanged.emit(shots)

    def read_cam(self):
        a, b, chopper, ext = self.cam.read_cam()
        a = a - self.back[0]
        b = b - self.back[1]
        rd = ReadData(shots=self.shots,
                      det_a=a,
                      det_b=b,
                      ext=ext.T,
                      chopper=chopper)
        self.sigReadCompleted.emit()
        return rd

    def set_wavelength(self, wl):
        self.cam.set_wavelength(wl)
        self.sigWavelengthChanged.emit(wl)

    def get_wavelength(self):
        return self.cam.get_wavelength()

    def get_wavelengths(self, center_wl=None):
        return self.cam.get_wavelength_array(center_wl)

    def get_bg(self):
        rd = self.read_cam()
        self.back = rd.det_a.mean(0, keepdims=1), rd.det_b.mean(0, keepdims=1)

    def remove_bg(self):
        self.back = (0, 0)


@attrs(cmp=False)
class Delayline(QObject):

    pos = attrib(0)
    _dl = attrib(I.IDelayLine)
    _thread = attrib(None)
    sigPosChanged = Signal('float')

    def __attrs_post_init__(self):
        super().__init__()
        self.pos = self._dl.get_pos_fs()

        self.sigPosChanged.emit(self.pos)

    def set_pos(self, pos_fs: float, do_wait=True):
        "Set pos in femtoseconds"
        try:
            pos_fs = float(pos_fs)
        except ValueError:
            raise
        self._dl.move_fs(pos_fs, do_wait=do_wait)
        if not do_wait and False:
            self._thread = threading.Thread(target=self.wait_and_update)
            self._thread.start()

        self.pos = self._dl.get_pos_fs()
        self.sigPosChanged.emit(self.pos)

    def wait_and_update(self):
        "Wait until not moving. Do update position while moving"
        while self._dl.is_moving():
            self.pos = self._dl.get_pos_fs()
            self.sigPosChanged.emit(self.pos)
            time.sleep(0.1)
        self.pos = self._dl.get_pos_fs()
        self.sigPosChanged.emit(self.pos)

    def get_pos(self) -> float:
        return self._dl.get_pos_fs()

    def set_speed(self, ps_per_sec: float):
        self._dl.set_speed(ps_per_sec)

    def set_home(self):
        self._dl.home_pos = self._dl.get_pos_mm()
        config.__dict__['Delay 1 Home Pos.'] = self._dl.get_pos_mm()


arr_factory = Factory(lambda: np.zeros(16))


@attrs(cmp=False)
class LastRead(QObject):
    cam: Cam = attrib()
    probe = attrib(arr_factory)
    probe_mean = attrib(arr_factory)
    probe_std = attrib(arr_factory)
    reference = attrib(arr_factory)
    reference_mean = attrib(arr_factory)
    reference_std = attrib(arr_factory)
    ext_channel = attrib(arr_factory)
    ext_channel_mean = attrib(arr_factory)
    ext_channel_ref = attrib(arr_factory)
    probe_signal = attrib(arr_factory)
    spec = attrib(arr_factory)
    fringe_count = attrib(None)  # type np.array
    probe_back = attrib(0)  # type np.array
    ref_back = attrib(0)  # type np.array
    chopper = attrib(None)

    sigProcessingCompleted = Signal()

    def __attrs_post_init__(self):
        super().__init__()

    def update(self):
        dr = self.cam.read_cam()
        x = np.linspace(-7, 7, 16)

        self.probe = dr.det_a

        self.probe_mean = self.probe.mean(0)
        self.probe_std = np.nan_to_num(self.probe.std(0) / abs(self.probe_mean) * 100)

        self.reference = dr.det_b
        self.reference_mean = self.reference.mean(0)
        self.reference_std = np.nan_to_num(self.reference.std(0) / abs(self.reference_mean) * 100)

        self.spec = np.stack((self.probe_mean, self.reference_mean))

        self.ext_channel_mean = 2 + np.random.rand(1) * 0.05
        sign = 1 if dr.chopper[0] else -1
        with np.errstate(divide='ignore', invalid='ignore'):
            self.probe_signal = sign * 1000 * np.log10(self.probe[::2, ...] / self.probe[1::2, ...]).mean(0)
            self.probe_signal = np.nan_to_num(self.probe_signal)
        self.probe_signal = self.probe_signal[None, :]
        self.probe_signal0 = self.probe_signal[0, :]
        self.sigProcessingCompleted.emit()


class Controller(QObject):
    """Class which controls the main loop."""
    cam: Cam
    cam2: T.Optional[Cam]
    cam_list: T.List[Cam]
    shutter: T.Optional[I.IShutter]
    delay_line: Delayline
    rot_stage: T.Optional[I.IRotationStage]

    def __init__(self):
        super().__init__()
        self.cam = Cam()
        self.cam.read_cam()
        self.shutter = _shutter
        self.cam_list = [self.cam]

        if _cam2 is not None:
            self.cam2 = Cam(cam=_cam2)
            self.cam2.read_cam()
            self.cam.sigShotsChanged.connect(self.cam2.set_shots)
            self.cam_list.append(self.cam2)
        else:
            self.cam2 = None

        self.delay_line = Delayline(dl=_dl)
        self.rot_stage = None

        if _dl2:
            self.delay_line_second = Delayline(dl=_dl2)
        else:
            self.delay_line_second = None

        self.plan = None
        self.pause_plan = False
        self.running_step = False
        self.thread = None
        self._stop = False

    @Slot()
    def looper(self):
        while True:
            self.loop()
            if self._stop:
                break
            #QApplication.instance().processEvents()
            time.sleep(0.01)

    def start_looper(self):
        self.thread = threading.Thread(target=self.looper)
        self.thread.start()

    def loop(self):
        t = time.time()

        if self.plan is None or self.pause_plan:
            t1 = threading.Thread(target=self.cam.last_read.update)
            t1.start()
            if self.cam2:
                t2 = threading.Thread(target=self.cam2.last_read.update)
                t2.start()
                t2.join()
            t1.join()

        else:
            try:
                self.plan.make_step()
            except StopIteration:
                self.pause_plan = True


        #print(time.time() - t)

    def shutdown(self):
        if _dl2 is not None:
            _dl2.shutdown()
        _dl.shutdown()
        _cam.shutdown()
        if _cam2 is not None:
            _cam2.shutdown()
