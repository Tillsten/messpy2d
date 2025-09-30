import numpy as np
from qtpy import QtWidgets, QtCore
"Class implemting the IPowerMeter interface for the Starbright power meter"
import attr
from serial import Serial

from MessPy.Instruments.interfaces import IPowerMeter


@attr.dataclass(kw_only=True)
class Starbright(IPowerMeter):
    """Class for the Starbright power meter

    Only read out is implemented. The power meter is connected via RS232.
    """
    name: str = 'Starbright'
    _serial: Serial = Serial("COM6", baudrate=19200)

    def read_power(self) -> float:
        self._serial.write(b"$SP\r\n")
        ans = self._serial.read_until(b'\r\n')
        print(ans)
        return float(ans[1:-2])


if __name__ == '__main__':
    import pyqtgraph as pg
    import time
    s = Starbright()
    app = pg.mkQApp()
    pw = pg.PlotWidget()
    pw.show()
    powers = []
    times = []
    l = pw.plot([])
    t0 = time.time()
    def update():
        t = time.time() - t0
        times.append(t)
        p = s.read_power()*1000
        powers.append(p)
        l.setData(times, powers)
        np.savetxt('power_vs_time', np.column_stack((times, powers)))

    timer = pg.QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(1000)
    app.exec()