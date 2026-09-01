"""
Created on Mon Sep 02 15:38:46 2013

@author: Owner
"""

# -*- coding: utf-8 -*-
r"""
Spyder Editor

This temporary script file is located here:
C:\Documents and Settings\Owner\Desktop\WinPython-32bit-2.7.5.2\settings\.spyder2\.temp.py
"""
import os
import time
from threading import Lock, Thread

import numpy as np
import PyDAQmx
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxTypes import *
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sleep = time.sleep

cur_dir = os.path.dirname(__file__)

"""
Initialize the PCI-6533 for Burst – Mode buffered data transfer of the Most
Significant data ports 2 and 3. Port 2 bit 0 is the LSB of a 16 Bit data word,
and Port 3 Bit 7 is the MSB of the 16 Bit Data Word. Signed Integer.
Setup Using PCLK2, REQ2 and ACK2.

Data Port 0 is used as data lines (0-255)
for the selection of the Integration Gate Delay and Width. These lines are
all output lines to the IR-3200, IR-3216, and IR6416. Unsigned integer.

Data Port 1 is used to communicate control signals to the PCI-6533 card.
 Port 1 bit 0 is the WRITE WIDTH CLOCK to write the data value on port
  0 into the Integration Gate Width Register. Bit 1 is the
  WRITE DELAY CLOCK to write the data value on port 0 into the Delay Register.
  Bit 2 is the External Reset line and should be set low for normal operation,
  and high to RESET. Bit 3out = np.zeros(8, dtype=np.bool)
is not used and MUST be set as an INPUT.
  Bit 4 is the Scan Dropped Flag input, it will be high if data is lost due to
  FIFO overflow. Bit 5 is the System Ready Flag input, High when the system is
  ready to be enabled. Bit 6 and Bit 7 are not used and MUST be set as INPUTS.
When the PCI-6533 card is setup as above, it will scan the FIFO for valid data
 and transfer when ready.
When the  FIFO is found to contain data,
the PCI-6533 will transfer the data to local PC memory for processing by
the user, or the LASPEC software.
"""


def interleave(a, b):
    """Interleave to arrays"""
    out = np.zeros(a.size * 2)
    out[::2] = a
    out[1::2] = b
    return out


def mk_idx():
    """
    Generate the indexes used by the ADC of IR systems.

    Converted from the LabView code.
    """
    ar = np.arange(256)
    a1, a2 = ar[::2], ar[1::2]
    out = np.zeros_like(ar)

    for j in range(0, 128, 16):
        a1e = a1[j : j + 8]
        a1o = a1[j + 8 : j + 16]
        a1f = interleave(a1e, a1o)

        a2e = a2[j : j + 8]
        a2o = a2[j + 8 : j + 16]
        a2f = interleave(a2e, a2o)

        af = np.hstack((a1f, a2f))
        out[2 * j : 2 * j + 32] = af
    return out


idx_array = mk_idx()
print(idx_array[:48])


def int_to_bool_array(val):
    string = np.binary_repr(val, width=8)
    return np.array([1 if i == "1" else 0 for i in string], dtype=np.uint8)[::-1]


def calc_int_steps(ns):
    steps = (int(ns) - 54) / 10
    steps = np.clip(steps, 0, 255)
    return np.uint8(steps)


def calc_int_ns(steps):
    return steps * 10 + 54


def calc_delay_steps(ns):
    steps = (int(ns) - 30) / 2
    steps = np.clip(steps, 0, 255)
    return np.uint8(steps)


def calc_delay_ns(steps):
    return steps * 2 - 30


class InfraAD:
    has_external = True

    def __init__(self):
        print("Init cam...")
        self.shots = 1000

        self.read_task = PyDAQmx.Task()
        self.read_task.CreateDIChan("dev1/port1/line5", "scan ready", 0)
        self.read_task.CreateDIChan("dev1/port1/line4", "scan dropped", 0)

        task = PyDAQmx.Task()
        task.CreateDOChan("dev1/port1/line0", "int clock", 0)
        task.CreateDOChan("dev1/port1/line1", "delay clock", 0)
        self.clock_task = task

        task = PyDAQmx.Task()
        task.CreateDOChan("dev1/port0/line0:7", "", 0)
        self.out_task = task

        task = PyDAQmx.Task()
        task.CreateDOChan("dev1/port1/line2", "ext reset", 0)
        self.reset_task = task

        task = PyDAQmx.Task()
        task.CreateDIChan("dev1/port0_32", "data", PyDAQmx.DAQmx_Val_ChanForAllLines)
        task.CfgBurstHandshakingTimingExportClock(
            PyDAQmx.DAQmx_Val_FiniteSamps,
            self.shots * 128,
            2e7,
            "PFI4",
            DAQmx_Val_ActiveLow,
            DAQmx_Val_High,
            DAQmx_Val_ActiveHigh,
        )
        self.transfer_task = task

        self.runner = None
        self.lock = Lock()

    #        self.reset()

    def write_out(self, val):
        written = int32()
        val = int_to_bool_array(val).copy()
        self.out_task.WriteDigitalLines(
            1, 1, 0.001, PyDAQmx.DAQmx_Val_GroupByScanNumber, val, byref(written), None
        )
        self.out_task.WaitUntilTaskDone(-1)

    def _write_lines(self, A, B):
        written = int32()
        to_write = np.ones(2, dtype=np.uint8)
        to_write[0] = A
        to_write[1] = B
        self.clock_task.WriteDigitalLines(
            1,
            1,
            0.001,
            PyDAQmx.DAQmx_Val_GroupByScanNumber,
            to_write,
            byref(written),
            None,
        )
        self.clock_task.WaitUntilTaskDone(-1)

    def reset(self):
        written = int32()
        to_write = np.ones(1, dtype=np.uint8)
        to_write[0] = False
        self.reset_task.WriteDigitalLines(
            1,
            1,
            0.001,
            PyDAQmx.DAQmx_Val_GroupByScanNumber,
            to_write,
            byref(written),
            None,
        )
        self.reset_task.WaitUntilTaskDone(-1)

        time.sleep(0.3)

        to_write[0] = True
        self.reset_task.WriteDigitalLines(
            1,
            1,
            0.001,
            PyDAQmx.DAQmx_Val_GroupByScanNumber,
            to_write,
            byref(written),
            None,
        )
        self.reset_task.WaitUntilTaskDone(-1)

    #        to_write[0] = True
    #        self.reset_task.WriteDigitalLines(1, 1, 0.001, PyDAQmx.DAQmx_Val_GroupByScanNumber, to_write,
    #                                      byref(written) , None)
    #        self.reset_task.WaitUntilTaskDone(-1)

    def set_int(self, ns, direct=False):
        self.write_out(0)
        self._write_lines(1, 1)
        sleep(0.001)
        if direct:
            self.write_out(np.array(ns))
        else:
            self.write_out(np.array(calc_int_steps(ns)))
        self._write_lines(0, 1)
        sleep(0.0001)
        self._write_lines(1, 1)

    def set_delay(self, ns, direct=False):
        self.write_out(0)
        self._write_lines(1, 1)
        sleep(0.001)
        if direct:
            self.write_out(np.array(ns))
        else:
            self.write_out(np.array(calc_delay_steps(ns)))
        self._write_lines(1, 0)
        sleep(0.0001)
        self._write_lines(1, 1)

    def transfer_data(self, shots, dat):
        read = int32()
        shots_to_read = shots
        nout = np.zeros(shots_to_read * 128, dtype=np.uint32)

        tt = PyDAQmx.Task()
        tt.CreateDIChan("dev1/port0_32", "data", PyDAQmx.DAQmx_Val_ChanForAllLines)

        tt.CfgBurstHandshakingTimingExportClock(
            PyDAQmx.DAQmx_Val_FiniteSamps,
            shots_to_read * 128,
            10e6,
            "PFI4",
            DAQmx_Val_ActiveLow,
            DAQmx_Val_High,
            DAQmx_Val_ActiveHigh,
        )

        tt.ReadDigitalU32(
            -1,
            10.0,
            PyDAQmx.DAQmx_Val_GroupByScanNumber,
            nout,
            nout.size,
            byref(read),
            None,
        )
        tt.WaitUntilTaskDone(10)

        ar = np.roll(nout, -1)
        # a1, a2 = ar.view(np.uint16)[::2], ar.view(np.uint16)[1::2]

        # a = a.reshape(-1, 48)

        out = ar.view(np.uint16)
        out = out.reshape(shots_to_read, 256)
        self.dat = out[:, idx_array] / 13107.0

        return self.dat

    def read_cam(self):
        """
        Returns deta, detb, chopper, ext
        """
        # self.lock.acquire()
        self.dat = 0
        self.runner = Thread(target=self.transfer_data, args=(self.shots, self.dat))
        self.runner.start()
        while self.runner.is_alive():
            QApplication.processEvents()
        # self.transfer_data()
        self.runner.join()
        a = self.dat

        d = a.T

        # np.save('back_a.npy', d[:16, :].mean(-1) )
        # np.save('back_b.npy', d[16:32, :].mean(-1))
        # self.lock.release()
        return (
            d[:16, :] - self.back_a[:, None],
            d[16:32, :] - self.back_b[:, None],
            a[:, 32 + 8] > 3.0,
            d[32:48, :],
        )

    def set_shots(self, shots):
        self.lock.acquire()
        self.shots = int(shots)

        self.lock.release()

    def check_ready(self):
        read = int32()
        num_bytes = int32()
        out = np.zeros(2, dtype=np.uint8)
        # self.read_task.ReadDigitalLines(1, 1, 0, out,  1, 0, 1)
        self.read_task.ReadDigitalLines(
            1,
            1.0,
            PyDAQmx.DAQmx_Val_GroupByScanNumber,
            out,
            8,
            byref(read),
            byref(num_bytes),
            None,
        )
        self.read_task.WaitUntilTaskDone(1)
        if out[0]:
            return True
        else:
            return False

    def get_bg(self):
        pass


cam = InfraAD()
cam.back_a = np.load(cur_dir + "/back_a.npy")
cam.back_b = np.load(cur_dir + "/back_b.npy")

# cam.reset()
# cam.set_int(180, direct=True)
# cam.set_delay(255, direct=True)
if __name__ == "__main__":
    import pyqtgraph as pg

    app = QApplication([])
    pw = pg.PlotWindow()
    plot = pw.plotItem.plot()
    plot2 = pw.plotItem.plot(pen=pg.mkPen(color="r"))

    cam.set_shots(1000)
    import time

    def update():
        try:
            t = time.time()
            # print(cam.check_ready())
            a, b, c, d = cam.read_cam()
            print(time.time() - t)
            print(c.sum())
        except:
            timer.stop()
            raise
        # print a.shape
        plot.setData(a.mean(1))
        # plot.setData(d[8,  :])
        # plot.setData(d[7, :])
        # plot2.setData(c)
        # plot2.setData((a[:, :].std(1)/a[:, :].mean(1))*100)

    pw.show()
    timer = QTimer()
    timer.timeout.connect(update)
    timer.start(0)
    app.exec_()

    #    k2 = []
###    vals = np.arange(0, 256, 1, dtype=np.uint8)
#    cam.set_int(10, direct=1)
#    vals = range(0, 256, 1)
#    for i in vals:
#        cam.set_delay(i, direct=1)
#        for j in range(1):
#            a, b, c, d = cam.read_cam()
##            plt.plot(b[17, :])
#            k.append(b[:, :].std(1).sum()/b[:, :].mean(1).sum())
#            k2.append(b[:, :].mean(1).sum())
##    print (time.time() - t) / 10.
#    plt.figure()
#    plt.subplot(211).plot(vals, k)
#    plt.subplot(212).plot(vals, k2)
#    plt.show()
##    cam.set_shots(10000)
##    a, b, c, d = cam.read_cam()
##    plt.plot(a[10, :])
##    plt.plot(d[0, :])
##    plt.show()
##    np.savez("dat",a=a, b=b, c=c, d=d)
