import time

import attr
import numpy as np
from nicelib import (
    NiceLib,
    NiceObject,
    RetHandler,
    Sig,
    load_lib,
    ret_ignore,
    ret_return,
)
from serial import Serial


@RetHandler(num_retvals=0)
def ret_errcode(retval, funcargs, niceobj):
    if retval != 0:
        raise ValueError(retval)


class Avaspec(NiceLib):
    _info_ = load_lib("avaspec", __package__)
    _ret_ = ret_ignore
    _prefix_ = "AVS_"
    _use_numpy_ = True
    Init = Sig("in", ret=ret_return)
    UpdateUSBDevices = Sig(ret=ret_return)
    GetList = Sig("in", "out", "in")
    Activate = Sig("in", ret=ret_return)
    Done = Sig()

    class Device(NiceObject):
        _init_ = "Activate"
        PrepareMeasure = Sig("in", "in")
        GetNumPixels = Sig("in", "out")
        GetLambda = Sig("in", "arr[2048]")
        PollScan = Sig("in", ret=ret_return)
        GetScopeData = Sig("in", "out", "arr[2048]", ret=ret_errcode)
        UseHighResAdc = Sig("in", "in")
        GetDigIn = Sig("in", "in", "out", ret=ret_errcode)
        StopMeasure = Sig("in", ret=ret_return)
        # Measure = Sig('in', 'in', 'in')
        # MeasureCallback = Sig('in', '
        # in', 'in')


@attr.define
class MeasurmentSettings:
    start_pixel: int = 0
    stop_pixel: int = 2047
    int_time: float = 0.4# in ms
    int_delay: int = 0
    n_avg: int = 1
    dark_correct: bool = True
    smooth_pixel: int = 2
    saturation_detection: bool = False
    store_to_ram: int = 0
    trigger_type: tuple[int] = (2, 0, 0)

    """
    typedef struct {
    uint16              m_StartPixel;		   // 2
    uint16              m_StopPixel;           // 2
    float               m_IntegrationTime;     // 4
    uint32              m_IntegrationDelay;    // 4
    uint32              m_NrAverages;		   // 4
    DarkCorrectionType  m_CorDynDark;          // 2
    SmoothingType       m_Smoothing;		   // 3
    uint8               m_SaturationDetection; // 1
    TriggerType         m_Trigger;			   // 3
    ControlSettingsType m_Control;			   // 16
    } MeasConfigType;"""

    def make_struct(self, ffi):
        # print(self.start_pixel)
        mc = Avaspec._ffi.new("MeasConfigType*")
        mc.m_StartPixel = self.start_pixel
        mc.m_StopPixel = self.stop_pixel
        mc.m_IntegrationTime = self.int_time
        mc.m_IntegrationDelay = self.int_delay
        mc.m_NrAverages = self.n_avg
        mc.m_CorDynDark = (self.dark_correct, self.dark_correct * 50)
        mc.m_Smoothing = (self.smooth_pixel, self.smooth_pixel > 0)
        mc.m_SaturationDetection = self.saturation_detection
        trig = Avaspec._ffi.new("TriggerType*")
        trig.m_Mode = Avaspec._defs["SS_TRIGGER_MODE"]
        trig.m_Source = Avaspec._defs["EXTERNAL_TRIGGER"]
        trig.m_SourceType = Avaspec._defs["EDGE_TRIGGER_SOURCE"]
        mc.m_Trigger = trig[0]
        mc.m_Control = (0, 0, 0, 0, self.store_to_ram)
        return mc


@attr.define
class AvantesSpec:
    sn: str
    device: Avaspec.Device
    measurement_settings: MeasurmentSettings = attr.field(factory=MeasurmentSettings)
    wl: np.ndarray = attr.field()
    data: np.ndarray = attr.field(init=False)
    chopper: np.ndarray = attr.field(init=False)
    analog_in: np.ndarray = attr.field(init=False)
    shots: int = 30
    count: int = 0
    wl_range: tuple[float, float] = (0, 2000)
    wl_index: tuple[int, int] = attr.attrib()
    _cb: object = None
    is_reading: bool = False
    first_chop: bool = False
    port: str | None = "COM3"
    ardudino: Serial | None = attr.attrib()

    @classmethod
    def take_nth(cls, i=0):
        Avaspec.Init(0)
        num_dev = Avaspec.UpdateUSBDevices()
        if num_dev == 0:
            raise OSError("No Avantes spectrometer found")
        elif i + 1 > num_dev:
            raise ValueError(
                f"Only {num_dev} spectrometers found. {i}-th was requested"
            )
        ffi = Avaspec._ffi
        info = Avaspec._ffi.new("AvsIdentityType[%d]" % num_dev)
        Avaspec.GetList(ffi.sizeof(info), info)
        sn = ffi.string(info[i].SerialNumber)
        dev = Avaspec.Device(info[i])
        dev.UseHighResAdc(True)
        return cls(sn=sn, device=dev)

    @wl.default
    def wl_default(self):
        return self.device.GetLambda()

    @ardudino.default
    def make_connection(self):
        if self.port is not None:
            port = Serial(self.port, baudrate=115200)
            port.timeout = 0.3
            while port.read(1) != b'A':
                pass

            port.write(b'r10\n')
            print(port.read(20))
            port.timeout = 1.3
        else:
            port = None
        return port

    @wl_index.default
    def _wl_index_factory(self):
        a = np.argmin(np.abs(self.wl - self.wl_range[0]))
        b = np.argmin(np.abs(self.wl - self.wl_range[1]))
        print(a, b)
        return a, b

    def start_reading(self, shots: int, callback):
        if self.is_reading:
            raise OSError("Already reading")
        ffi = Avaspec._ffi
        self.shots = shots
        self.measurement_settings.store_to_ram = shots

        # self.measurement_settings.start_pixel = self.wl_index[0]
        # self.measurement_settings.stop_pixel = self.wl_index[1]
        self.device.PrepareMeasure(self.measurement_settings.make_struct(ffi))
        hdl = self.device._handles[0]
        if callback is None:
            callback = ffi.NULL
        self.data = np.empty((2048, self.shots))
        self.chopper = np.empty(self.shots, dtype=bool)
        self.analog_in = np.empty(self.shots, dtype="int")
        self.is_reading = True
        self.count = 0
        Avaspec.AVS_MeasureCallback(hdl, callback, -2)
        if self.ardudino:
            self.ardudino.write(b's%d\n' % 300)
            self.ardudino.write(b'r%d\n' % (self.shots+0))
        #ans = self.ardudino.read_until(b'\r\n')
        #print(ans)
        #assert(ans == '%d\r\n'%self.shots)

    def callback_factory(self, fin_cb=None):
        @Avaspec._ffi.callback("void(long*, int*)")
        def callback(handle, intp):
            scope_data = self.device.GetScopeData()[1]
            self.data[:scope_data.size, self.count] = scope_data#[:self.wl_index[1]-self.wl_index[0]]
            assert self.ardudino is not None
            out = self.ardudino.read(2)
            c, a = out
            #print(c, a)
            self.chopper[self.count] = a
            self.analog_in[self.count] = a
            self.count += 1
            #print(self.count)

            if self.count == self.shots:
                #out = self.ardudino.read(2*self.shots)
                #self.chopper[:] = np.frombuffer(out[::2], dtype=np.int8)
                #self.analog_in[:] = np.frombuffer(out[1::2], dtype=np.int8)
                #print(out)
                self.is_reading = False
                if fin_cb:
                    fin_cb()
                self.count = 0

        self._cb = callback
        return callback


if __name__ == "__main__":
    from PySide6.QtCore import QTimer

    spec = AvantesSpec.take_nth(0)

    while 0:
        print(spec.device.GetDigIn(0))
        print(spec.device.GetDigIn(1))
        print(spec.device.GetDigIn(2))
        print("--")

    import pyqtgraph as pg

    app = pg.mkQApp()
    pw = pg.PlotWidget()
    pw2 = pg.PlotWidget()
    l1 = pw.plotItem.plot([], [])
    l2 = pw2.plotItem.plot([], [])
    l3 = pw2.plotItem.plot([], [])
    i400 = np.argmin(abs(spec.wl - 350))
    i1200 = np.argmin(abs(spec.wl - 1200))
    print(i400, i1200)
    t = 0
    def read():
        global t
        if not spec.is_reading:
            if hasattr(spec, "data"):
                mean = spec.data.mean(1)
                spec.data -= mean[None, -300:].mean()
                l1.setData(spec.data[:, 0])
                sign = -1 if spec.analog_in[0] > 100 else 1
                #print(sign)
                #l2.setData(spec.wl, 1000*sign*np.log10(spec.data[:, ::2].mean(1)/spec.data[:, 1::2].mean(1)))
                l2.setData(spec.data[800, :])
                l3.setData(spec.analog_in)
                l3.setData(spec.chopper)
                #2.setData(100*spec.data.std(1)/spec.data.mean(1))
                #print(spec.analog_in[1-2:])
                #spec.ardudino.read(100)
                print(time.time() - t)
            spec.start_reading(20, spec.callback_factory())

            t = time.time()
        else:
            pass

    timer = QTimer()
    timer.timeout.connect(read)
    timer.start(130)
    pw.show()
    pw2.show()
    app.exec_()
