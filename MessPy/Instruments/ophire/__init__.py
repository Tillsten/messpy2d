import numpy as np
from PySide6 import QtCore, QtWidgets

"Class implemting the IPowerMeter interface for the Starbright power meter"
import sys

import attr
from serial import Serial

sys.path.append(r'C:\Users\Messknecht\PycharmProjects\messpy2d')
from MessPy.Instruments.interfaces import IPowerMeter


@attr.dataclass(kw_only=True)
class Starbright(IPowerMeter):
    """Class for the Starbright power meter

    Only read out is implemented. The power meter is connected via RS232.
    """
    name: str = 'Starbright'
    _serial: Serial = attr.Factory(lambda: Serial("COM6", baudrate=19200))

    def read_power(self) -> float:
        self._serial.write(b"$SP\r\n")
        ans = self._serial.read_until(b'\r\n')
        print(ans)
        return float(ans[1:-2])


class StarbrightUSB(IPowerMeter):
    
    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        # Use of Ophir COM object. 

        import time

        import win32com.client


        OphirCOM = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
        # Stop & Close all devices
        OphirCOM.StopAllStreams() 
        OphirCOM.CloseAll()
        # Scan for connected Devices
        DeviceList = OphirCOM.ScanUSB()
        print(DeviceList)
        
        DeviceHandle = OphirCOM.OpenUSBDevice(DeviceList[0])	
        self._handle = DeviceHandle# open first device
        exists = OphirCOM.IsSensorExists(DeviceHandle, 0)
        if exists:
            print(f'\n----------Data for S/N {DeviceList[0]} ---------------')
        # An Example for data retrieving
        OphirCOM.StartStream(DeviceHandle, 0)		# start measuring
        self._pm = OphirCOM

    def read_power(self) -> float:
        data = self._pm.GetData(self._handle, 0)
        return data[0][-1]

if __name__ == '__main__':
    import time

    import pyqtgraph as pg

    from MessPy.Instruments.rot_stage_thorlabs import TLRotStage
    rot = TLRotStage("Pol")
    rot.get_degrees()
    s = StarbrightUSB(name='SBUSB')
    app = pg.mkQApp()
    pw = pg.PlotWidget()
    pw.show()
    powers = []
    times = []
    l = pw.plot([])
    t0 = time.time()
    PolList = np.arange(0., 120., 2.)
    rot.set_degrees(PolList[0])
    out = []
    
    def step():
        for deg in PolList:
            rot.set_degrees(deg)
            
            while rot.is_moving():
                print(rot.is_moving())
                time.sleep(0.05)
            t = time.time() - t0
            times.append(t)
            out.append(deg)
            p = s.read_power()*1000
            time.sleep(0.2)
            p = s.read_power()*1000
            powers.append(p)
            print(p, powers,)
            l.setData(out, powers)
            np.savetxt('power_vs_time', np.column_stack((times, powers)))
            np.savetxt('power_vs_deg', np.column_stack((out, powers)))
            
            yield
    timer = pg.QtCore.QTimer()
    updater = step()
    def update():
        try:
            next(updater)
        except StopIteration:
            return
    timer.timeout.connect(update)
    timer.start(10)
    app.exec()