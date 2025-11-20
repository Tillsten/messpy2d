import pyqtgraph as pg
from pyqtgraph import PlotDataItem
import time
from PySide6.QtWidgets import (
    QWidget,
    QCheckBox,
    QApplication,
)
from PySide6.QtCore import Slot
import MessPy.QtHelpers as qh
from MessPy.ControlClasses import Controller

from attr import define, field



@define(slots=False)
class SignalAligenmentHelper(pg.GraphicsLayoutWidget):
    controller: Controller

    signal_plot: pg.PlotItem = field(init=False)
    hist_plot: pg.PlotItem = field(init=False)
    sig_lines: dict[str, PlotDataItem] = field(factory=dict)
    hist_lines: dict[str, PlotDataItem] = field(factory=dict)
    times: list[float] = field(factory=list)
    time_max: float = 20.0
    t0: float = field(factory=time.time)
    hist_lists: dict[str, list[float]] = field(factory=dict)
    time_list: list[float] = field(factory=list)
    region: pg.LinearRegionItem = field(init=False)
    sig_idx: int = 1

    def __attrs_post_init__(self):
        super().__init__()

        self.signal_plot = self.addPlot()
        self.signal_plot.setTitle("Signal Alignment")
        for i, s in enumerate(["signal", "fit", "residual"]):
            p = self.signal_plot.plot(name=s,
                                      pen=pg.mkPen(color=qh.col[i]))
            self.sig_lines[s] = p
        self.hist_plot = self.addPlot()
        self.hist_plot.setTitle("Histogram")
        for i, s in enumerate(["min", "max", "ptp"]):
            self.hist_lines[s] = self.hist_plot.plot(name=s,
                                                     pen=pg.mkPen(color=qh.col[i]))
            self.hist_lists[s] = []
        self.controller.loop_finished.connect(self.update_plots)
        x = self.controller.cam.get_wavelengths()
        self.region = pg.LinearRegionItem(values=(x[0], x[-1]))
        self.region.setZValue(-1)
        self.signal_plot.addItem(self.region)

    @Slot()
    def update_plots(self):
        import numpy as np

        cam = self.controller.cam
        assert cam.last_read is not None

        y = cam.last_read.signals[self.sig_idx, :]
        x = cam.get_wavelengths()

        reg = self.region.getRegion()
        idx = (x < reg[1]) & (x > reg[0])
        if idx.size -  idx.sum()  > 0:
            idx = ~idx
        f = np.polyval(np.polyfit(x[idx], y[idx], 1), x)

        self.sig_lines["signal"].setData(x, y)
        self.sig_lines["fit"].setData(x, f)
        self.sig_lines["residual"].setData(x, y-f)


        self.hist_lists['ptp'].append(np.ptp(y-f))
        self.hist_lists['max'].append(np.max(y-f))
        self.hist_lists['min'].append(-np.min(y-f))
        self.times.append(time.time() - self.t0)

        for s in self.hist_lists:
            self.hist_lines[s].setData(self.times, self.hist_lists[s])


        if len(self.times) > 10:
            if self.times[-1] - self.times[0] > 20:
                self.times.pop(0)
                for l in self.hist_lists.values():
                    l.pop(0)


class AlignmentHelper(QWidget):
    def __init__(self, controller: Controller, **kwargs):
        super().__init__(**kwargs)
        self.times = []
        self.time_max = 20
        self.t0 = time.time()
        self.controller = controller

        self.graph_layouter = pg.GraphicsLayoutWidget()
        self.plots = {}
        self.amp_lines = {}
        self.std_lines = {}
        self.sig_lines = {}
        self.check_boxes = []
        for cam in controller.cam_list:
            amp_plot: pg.PlotItem = self.graph_layouter.addPlot()
            amp_plot.setTitle("Amplitude")
            for line_name in range(len(cam.cam.line_names)):
                c = pg.mkPen(color=qh.col[line_name])
                line = amp_plot.plot(pen=c)
                self.amp_lines[(cam, line_name)] = line, []
                cb = QCheckBox(cam.cam.line_names[line_name])
                cb.setChecked(True)
                cb.toggled.connect(line.setVisible)
                self.check_boxes.append(cb)

            std_plot = self.graph_layouter.addPlot()
            std_plot.setTitle("Std")
            for std_name in range(len(cam.cam.std_names)):
                c = pg.mkPen(color=qh.col[std_name])
                line = std_plot.plot(pen=c)
                self.std_lines[(cam, std_name)] = line, []
                cb = QCheckBox(cam.cam.std_names[std_name])
                cb.setChecked(True)
                cb.toggled.connect(line.setVisible)
                self.check_boxes.append(cb)
            self.graph_layouter.nextRow()

            # for i, sig in enumerate(cam.sig_lines):
            #    c = pg.mkPen(color=qh.col[i])
            #    line = amp_plot.plot(pen=c, style=pg.QtCore.Qt.PenStyle.DashLine)

        self.setLayout(
            qh.hlay([self.graph_layouter, qh.vlay(self.check_boxes, add_stretch=True)])
        )
        controller.loop_finished.connect(self.update_plots)

    @Slot()
    def update_plots(self):
        t = time.time()
        self.times.append(t - self.t0)

        if self.times[-1] - self.times[0] > self.time_max:
            self.times = self.times[1:]
            do_pop = True
        else:
            do_pop = False

        for (cam, line), (p, data) in self.amp_lines.items():
            data.append(cam.last_read.lines[line].mean())
            if do_pop:
                data.pop(0)
            p.setData(self.times, data)

        for (cam, line), (p, data) in self.std_lines.items():
            data.append(cam.last_read.stds[line].mean())
            if do_pop:
                data.pop(0)
            p.setData(self.times, data)


if __name__ == "__main__":
    import time
    from PySide6.QtCore import QThread, QTimer

    c = Controller()
    c.cam.set_shots(50)
    c.cam.set_wavelength(250)
    app = QApplication([])

    b = SignalAligenmentHelper(c)

    class Reader(QThread):
        def run(self):
            self.running = True
            while self.running:
                c.loop()

    thr = Reader()
    app.aboutToQuit.connect(lambda: setattr(thr, "running", False))
    app.aboutToQuit.connect(thr.wait)
    thr.start()

    b.show()

    app.exec()
