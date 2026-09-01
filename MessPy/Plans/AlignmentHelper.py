import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QWidget,
)

import MessPy.QtHelpers as qh
from MessPy.ControlClasses import Cam, Controller


class SignalAlignmentHelper(QWidget):
    """
    Signal Alignment Helper Class

    Keeps track of signal alignment over time.

    Show a baseline subtracted view of the signal and their
    evolution over time. (e.g. sig max and ptp)

    The baseline is subtracted by choosing two reference points in the signal.
    The points are set by the user using vertical lines in the plot.

    """

    def __init__(self, controller: Controller, **kwargs):
        super().__init__(**kwargs)
        self.controller = controller
        self.times: list[float] = []
        self.time_max = 20
        self.t0 = time.time()

        self.graph_layouter = pg.GraphicsLayoutWidget()
        self.ref_lines: dict[Cam, tuple[pg.InfiniteLine, pg.InfiniteLine]] = {}
        self.spectrum_curves = {}
        self.evo_lines = {}
        self.max_lines = {}
        self.check_boxes = []

        for cam in controller.cam_list:
            n_px = cam.cam.channels

            spec_plot: pg.PlotItem = self.graph_layouter.addPlot()
            spec_plot.setTitle(f"{cam.name} - baseline subtracted signal")
            for line_name in range(len(cam.cam.sig_names)):
                c = pg.mkPen(color=qh.col[line_name])
                curve = spec_plot.plot(pen=c)
                self.spectrum_curves[(cam, line_name)] = curve
                cb = QCheckBox(cam.cam.sig_names[line_name])
                cb.setChecked(True)
                cb.toggled.connect(curve.setVisible)
                self.check_boxes.append(cb)

            # reference points used to define the (linear) baseline
            ref1 = pg.InfiniteLine(pos=0, angle=90, movable=True, pen="r")
            ref2 = pg.InfiniteLine(pos=n_px - 1, angle=90, movable=True, pen="r")
            spec_plot.addItem(ref1)
            spec_plot.addItem(ref2)
            self.ref_lines[cam] = (ref1, ref2)

            evo_plot = self.graph_layouter.addPlot()
            evo_plot.setTitle(f"{cam.name} - ptp evolution")
            for line_name in range(len(cam.cam.sig_names)):
                c = pg.mkPen(color=qh.col[line_name])
                line = evo_plot.plot(pen=c)
                self.evo_lines[(cam, line_name)] = line, []

            max_plot = self.graph_layouter.addPlot()
            max_plot.setTitle(f"{cam.name} - max(abs(signal)) evolution")
            for line_name in range(len(cam.cam.sig_names)):
                c = pg.mkPen(color=qh.col[line_name])
                line = max_plot.plot(pen=c)
                self.max_lines[(cam, line_name)] = line, []

            self.graph_layouter.nextRow()

        self.setLayout(
            qh.hlay([self.graph_layouter, qh.vlay(self.check_boxes, add_stretch=True)])
        )
        controller.loop_finished.connect(self.update_plots)

    def baseline_subtracted(self, cam: Cam, line: int) -> np.ndarray:
        data = cam.last_read.signals[line]
        ref1, ref2 = self.ref_lines[cam]
        i1 = int(np.clip(ref1.value(), 0, len(data) - 1))
        i2 = int(np.clip(ref2.value(), 0, len(data) - 1))
        if i1 == i2:
            baseline = np.full_like(data, data[i1])
        else:
            lo, hi = sorted((i1, i2))
            baseline = np.interp(np.arange(len(data)), [lo, hi], [data[lo], data[hi]])
        return data - baseline

    @Slot()
    def update_plots(self):
        t = time.time()
        self.times.append(t - self.t0)

        if self.times[-1] - self.times[0] > self.time_max:
            self.times = self.times[1:]
            do_pop = True
        else:
            do_pop = False

        for cam in self.controller.cam_list:
            if cam.last_read is None:
                continue
            for line in range(len(cam.cam.sig_names)):
                subtracted = self.baseline_subtracted(cam, line)
                self.spectrum_curves[(cam, line)].setData(subtracted)

                p, data = self.evo_lines[(cam, line)]
                data.append(np.ptp(subtracted))
                if do_pop:
                    data.pop(0)
                p.setData(self.times, data)

                p, data = self.max_lines[(cam, line)]
                data.append(np.max(np.abs(subtracted)))
                if do_pop:
                    data.pop(0)
                p.setData(self.times, data)


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
    c = Controller()

    app = pg.mkQApp()
    a = AlignmentHelper(c)

    def looper():
        while True:
            c.loop()

    import threading

    t = threading.Thread(target=looper)
    t.start()
    app.aboutToQuit.conenct(t.s)
    a.show()
    app.exec_()
