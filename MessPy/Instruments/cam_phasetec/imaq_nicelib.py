import pathlib
from threading import Lock

import nidaqmx
import nidaqmx.constants as c
import numpy as np
from cffi import FFI
from nicelib import NiceLib, RetHandler, Sig, load_lib


@RetHandler(num_retvals=0)
def ret_errcode(retval, funcargs, niceobj):
    if retval != 0:
        raise ValueError(IMAQ.imgShowError(retval))


class IMAQ(NiceLib):
    _info_ = load_lib("imaq", __package__)
    _ret_ = ret_errcode

    imgShowError = Sig("in", "buf[200]")
    imgInterfaceOpen = Sig("in", "out")
    imgSessionOpen = Sig("in", "out")
    imgCreateBufList = Sig("in", "out")
    imgSessionConfigure = Sig("in", "in")
    imgSessionStartAcquisition = Sig("in")
    imgSessionStopAcquisition = Sig("in")
    imgSessionCopyBufferByNumber = Sig("in", "in", "in", "in", "out", "out")
    imgSessionTriggerConfigure2 = Sig("in", "in", "in", "in", "in", "in")
    imgSessionStatus = Sig("in", "out", "out")


ffi: FFI = IMAQ._info._ffi  # typing: FFI


class Cam:
    def __init__(self):
        self.reading_lock = Lock()
        self.i, self.s = self.init_imaq()
        self.task = self.init_nidaqmx()
        self.frames = 0
        self.set_shots(200)

        if (p := (pathlib.Path(__file__).parent / "back.npy")).exists():
            self.background = np.load(p)
        else:
            self.background = None
        self.data = None
        self.line_data = None

    @staticmethod
    def init_imaq():
        i = IMAQ.imgInterfaceOpen("img0")
        s = IMAQ.imgSessionOpen(i)
        IMAQ.imgSessionTriggerConfigure2(
            s,
            IMAQ.IMG_SIGNAL_EXTERNAL,
            IMAQ.IMG_EXT_TRIG0,
            IMAQ.IMG_TRIG_POLAR_ACTIVEH,
            1000,
            IMAQ.IMG_TRIG_ACTION_CAPTURE,
        )
        return i, s

    def init_nidaqmx(self, first="Chopper"):
        task = nidaqmx.Task()
        if first == "Chopper":
            task.ai_channels.add_ai_voltage_chan("Dev1/AI0", min_val=0, max_val=2)
            task.ai_channels.add_ai_voltage_chan("Dev1/AI1", min_val=0, max_val=5)
        else:
            task.ai_channels.add_ai_voltage_chan(
                "Dev1/AI0", name_to_assign_to_channel="Shaper", min_val=0, max_val=1
            )
            task.ai_channels.add_ai_voltage_chan(
                "Dev1/AI1", name_to_assign_to_channel="Chopper", min_val=0, max_val=5
            )
        task.timing.cfg_samp_clk_timing(
            1000,
            "PFI0",
            c.Edge.RISING,
            sample_mode=c.AcquisitionType.FINITE,
            samps_per_chan=20,
        )

        # task.triggers.start_trigger.cfg_anlg_edge_start_trig("APFI0", trigger_level=2.5)
        task.triggers.start_trigger.cfg_dig_edge_start_trig("PFI0")
        task.export_signals.start_trig_output_term = "PFI12"
        return task

    def set_shots(self, shots):
        self.reading_lock.acquire()
        self.task.timing.cfg_samp_clk_timing(
            1000,
            "PFI0",
            c.Edge.RISING,
            sample_mode=c.AcquisitionType.FINITE,
            samps_per_chan=shots,
        )
        self.data = np.empty((128, 128, shots), dtype="uint16")

        self.buflist = ffi.new("void *[]", [ffi.NULL] * shots)
        self.skiplist = ffi.new("uInt32[]", [0] * shots)

        IMAQ.imgSequenceSetup(
            self.s, shots, ffi.cast("void **", self.buflist), self.skiplist, 0, 0
        )
        self.frames = 0
        self.shots = shots
        self.reading_lock.release()

    def set_trigger(self, mode):
        if mode != "Untriggered":
            self.task.triggers.start_trigger.cfg_anlg_edge_start_trig(
                "PFI0", trigger_level=2.5
            )
        else:
            pass

    def get_frame_count(self):
        fcount = ffi.new("long[1]")
        IMAQ.imgGetAttribute(self.s, 0x0076 + 0x3FF60000, fcount)
        return fcount[0]

    def read_cam(
        self,
        lines: dict[str, tuple] | None = None,
        back: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        self.reading_lock.acquire()
        IMAQ.imgSessionStartAcquisition(self.s)
        self.task.start()
        rows = 128
        colums = 128
        bi = np.empty((128, 128), dtype='uint16')        
        

        MAX_14_BIT = (1 << 14)

        assert self.data is not None

        if lines is not None:
            self.lines = np.empty((len(lines), 128, self.shots))

        for i in range(self.shots):
            IMAQ.imgSessionCopyBufferByNumber(
                self.s, i + self.frames, bi.ctypes.data, IMAQ.IMG_OVERWRITE_FAIL)
            a = np.swapaxes(bi.reshape(rows//4, colums, 4),
                            0, 1).reshape(rows, colums)
            self.data[:, :, i] = MAX_14_BIT - a.T
            if lines:
                for k, (l, u) in enumerate(lines.values()):
                    m = np.mean(self.data[l:u, :, i], 0)
                    if back is not None:
                        m = m - back[k]
                    self.lines[k, :, i] = m

        self.frames += self.shots
        chop = self.task.read(c.READ_ALL_AVAILABLE)

        self.task.stop()
        self.reading_lock.release()
        return self.data, chop

    def remove_background(self):
        self.background = None

    def set_background(self):
        assert self.data is not None
        self.background = self.data.mean(2)
        np.save("back.npy", self.background)


if __name__ == "__main__":
    read = 0

    import pyqtgraph as pg

    app = pg.mkQApp()
    timer = pg.Qt.QtCore.QTimer()
    win = pg.PlotWidget()
    l = win.plotItem.plot()
    win.show()

    import threading
    import time

    cam = Cam()
    cam.set_shots(20)
    cam.read_cam()

    cnt = 0
    import numpy as np

    def up():
        t = time.time()
        thr = threading.Thread(target=cam.read_cam)
        # o, ch = cam.read_cam()
        thr.start()
        while thr.is_alive():
            app.processEvents()
        print(time.time() - t)
        l.setData(cam.data[10, 10, :])
        global cnt
        np.save("%d testread" % cnt, cam.data)
        cnt += 1
        if cnt == 20:
            quit()

    timer.timeout.connect(up)
    timer.start(0)
    timer.setSingleShot(False)
    app.exec_()
    cam.task.close()
