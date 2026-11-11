import json
import pathlib
from threading import Lock
from typing import TYPE_CHECKING

import nidaqmx
import nidaqmx.constants as c
import numpy as np

try:
    from _imaqffi import ffi, lib
except ModuleNotFoundError:
    from ._imaqffi import ffi, lib

if TYPE_CHECKING:
    from cffi import FFI

    ffi: FFI

cur_dir = pathlib.Path(__file__).parent
with (cur_dir / "init_cmds.json").open("r") as f:
    init_cmd_list = json.load(f)

dead_pixel_list = [
    86,
    148,
    409,
    559,
    574,
    672,
    711,
    799,
    927,
    1277,
    1359,
    1487,
    1769,
    1777,
    1836,
    2763,
    2822,
    3213,
    3459,
    3741,
    3859,
    4176,
    4485,
    4631,
    5207,
    5394,
    5437,
    5473,
    5652,
    6167,
    6425,
    6440,
    6589,
    6700,
    7451,
    7580,
    8367,
    8522,
    9392,
    9442,
    9656,
    9855,
    10416,
    11443,
    11460,
    11905,
    12126,
    14302,
    14425,
    15030,
    15225,
]


class Cam:
    def __init__(self):
        self.reading_lock = Lock()
        self.i, self.s = self.init_imaq()
        self.task = self.init_nidaqmx()
        self.frames: int = 0

        if (p := (pathlib.Path(__file__).parent / "back.npy")).exists():
            self.background = np.load(p)
        else:
            self.background = None
        self.data = None
        self.line_data = None

    @staticmethod
    def init_imaq() -> tuple[int, int]:
        IMAQ = lib
        IID = ffi.new("INTERFACE_ID[1]")
        SID = ffi.new("SESSION_ID[1]")
        IMAQ.imgInterfaceOpen(b"img0", IID)
        IMAQ.imgSessionOpen(IID[0], SID)
        IMAQ.imgSessionTriggerConfigure2(
            SID[0],
            IMAQ.IMG_SIGNAL_EXTERNAL,
            IMAQ.IMG_EXT_TRIG0,
            0,
            1000,
            IMAQ.IMG_TRIG_ACTION_CAPTURE,
        )
        return IID[0], SID[0]

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
        # Set up the trigger to start the task upon receiving a pulse on PFI0
        task.triggers.start_trigger.cfg_dig_edge_start_trig("PFI0")
        # Route the start trigger to PFI12, will be used to start the camera
        task.export_signals.start_trig_output_term = "PFI12"
        return task

    def write_serial_cmd(self, cmd: bytes):
        """Write a command to the camera, always 4 bytes"""
        assert len(cmd) == 4
        lib.imgSessionSerialFlush(self.s)
        l = ffi.new("uint32_t[1]", [4])
        err = lib.imgSessionSerialWrite(self.s, ffi.from_buffer(cmd), l, 200)
        return err

    def read_serial_cmd(self) -> bytes:
        """Read a command from the camera, always 4 bytes"""
        out_buf = ffi.new("char[4]")
        l = ffi.new("uint32_t[1]", [4])
        lib.imgSessionSerialReadBytes(self.s, out_buf, l, 200)
        return ffi.buffer(out_buf)
    
    def check_if_initialized(self):
        """Here we check if the MCT is turned on and is initialized."""
        self.send_cmd()

    def send_cmd(self, cmd: bytes | tuple[int, int, int, int]) -> bytes:
        """Send a command to the camera and return the response"""
        if isinstance(cmd, tuple):
            cmd = bytes(cmd)
        self.write_serial_cmd(cmd)
        return self.read_serial_cmd()

    def send_init_cmds(self):
        """Send the initialization commands to the camera.

        Must be called once after camera is turned on.
        These commands are stored in init_cmds.json and may be
        specific to the camera model we have.
        """
        with self.reading_lock:
            for cmd in init_cmd_list[:2]:
                self.write_serial_cmd(bytes(cmd))
                time.sleep(0.3)
            for cmd in init_cmd_list[2:]:
                self.send_cmd(bytes(cmd))

    def set_amp_and_dark(self, i: int, darklevel: int):
        """Set the amplification and dark level of the camera.

        i: int, amplification level (0-7)
        darklevel: int, dark level (0-255)
        """
        assert 0 <= i < 8
        assert 0 <= darklevel < 256
        k = darklevel
        with self.reading_lock:
            self.send_cmd((113, 0, 0, 0))
            self.send_cmd((112, 79 - i, 0, 0))
            self.send_cmd((64, 1, k, 0))
            self.send_cmd((64, 2, k, 0))
            self.send_cmd((64, 64, k, 0))
            self.send_cmd((64, 128, k, 0))

    def set_shots(self, shots):
        self.reading_lock.acquire()
        IMAQ = lib
        self.task.timing.cfg_samp_clk_timing(
            1000,
            "PFI0",
            c.Edge.RISING,
            sample_mode=c.AcquisitionType.FINITE,
            samps_per_chan=shots,
        )
        self.data = np.empty((shots, 128, 128), dtype="uint16")

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
        lib.imgGetAttribute(self.s, lib.IMG_LAST_FRAME, fcount)
        return fcount[0]

    def read_cam(
        self, lines: list[tuple] | None = None, back: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        self.reading_lock.acquire()
        lib.imgSessionStartAcquisition(self.s)
        self.task.start()

        self.data = np.empty((self.shots, 128, 128), dtype="uint16")
        assert self.data is not None

        if lines is not None:
            self.lines = np.zeros((self.shots, len(lines), 128), dtype="float32")
            line_num = len(lines)
            line_buf = ffi.from_buffer(
                "float[%d]" % (line_num * 128 * self.shots), self.lines.data
            )  # type: ignore
            line_args = []
            for a, b in lines.values():
                line_args += [a, b]
        else:
            line_num = 0

            line_buf = ffi.NULL
            line_args = ffi.NULL

        outp = ffi.from_buffer(
            "uInt16[%d]" % (128 * 128 * self.shots), python_buffer=self.data.data
        )
        dp_arr = ffi.new("int[]", dead_pixel_list)
        lib.read_n_shots(
            self.shots,
            self.frames,
            self.s,
            outp,
            line_num,
            line_args,
            line_buf,
            ffi.NULL,
            dp_arr,
            len(dead_pixel_list),
        )

        self.frames += self.shots
        if lines:
            self.lines = self.lines.transpose()
        if back is not None:
            self.lines -= back[:, :, None]
        chop = self.task.read(c.READ_ALL_AVAILABLE)
        self.data = self.data
        self.task.stop()
        self.reading_lock.release()
        return self.data, chop

    def remove_background(self):
        self.background = None

    def set_background(self):
        assert self.data is not None
        self.background = self.data.mean(0)
        np.save("back.npy", self.background)


if __name__ == "__main__":
    read = 0

    import pyqtgraph as pg

    app = pg.mkQApp()
    timer = pg.Qt.QtCore.QTimer()
    win = pg.PlotWidget()
    img = pg.ImageItem()
    wid = pg.QtWidgets.QWidget()
    win.addItem(img)
    wid.setLayout(pg.QtWidgets.QHBoxLayout())
    wid.layout().addWidget(win)
    win2 = pg.PlotWidget()
    wid.layout().addWidget(win2)
    l = win2.plotItem.plot()
    take_bg = pg.QtWidgets.QPushButton("BG")
    wid.layout().addWidget(take_bg)
    wid.show()
    
    import threading
    import time

    cam = Cam()
    cam.set_shots(20)
    
    cam.read_cam()
    cnt = 161
    save = False
    import numpy as np
    lines = {"a": (50, 60)}
    bg = np.zeros((128, 128))
    def up():
        global cnt
        #cam.set_amp_and_dark(6, cnt)
        t = time.time()
        thr = threading.Thread(
            target=cam.read_cam,
            args=(lines,),
        )
        # o, ch = cam.read_cam()
        thr.start()
        while thr.is_alive():
            app.processEvents()
        #print(time.time() - t)
        print(cnt, cam.data[0].mean(), cam.data[0].std())
        img.setImage(cam.data[0].T-bg)
        #print(cam.lines.shape)
        y, x = np.histogram(cam.data[-1], 128)
        l.setData(x[:-1], y)
        if save:
            np.save('%d testread' % cnt, cam.data)
        cnt = (cnt + 1) % 255

    def take_bg_func():
        global bg 
        bg = cam.data.mean(0).T
    
    take_bg.clicked.connect(take_bg_func)
    timer.timeout.connect(up)
    timer.start(0)
    timer.setSingleShot(False)
    app.exec_()
    cam.task.close()
