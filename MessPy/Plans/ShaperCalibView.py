from pyqtgraph import PlotWidget

from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QSpinBox,
    QLabel,
    QCheckBox,
    QDialogButtonBox,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Signal, Slot
from pyqtgraph import TextItem, ScatterPlotItem
import attr
import numpy as np
from scipy.constants import c
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
from typing import Optional, ClassVar
from qtawesome import icon
from pyqtgraph.parametertree import Parameter, ParameterTree

import MessPy.Instruments.interfaces as I
from MessPy.Plans.ShaperCalibPlan import CalibPlan
from MessPy.Plans.ShaperCalibAnalyzer import CalibView
from MessPy.Config import config
from MessPy.Instruments.dac_px import AOM
from MessPy.ControlClasses import Cam


@attr.s(auto_attribs=True)
class CalibScanView(QWidget):
    cam: Cam
    dac: AOM
    plan: Optional[CalibPlan] = None

    sigPlanCreated: ClassVar[Signal] = Signal(object)

    def __attrs_post_init__(self):
        super().__init__()
        self.setLayout(QHBoxLayout())

        self.children = [
            dict(name="Start Wavelength (nm)", type="int", value=5500, step=500),
            dict(name="End Wavelength (nm)", type="int", value=6500, step=500),
            dict(name="Step (nm)", type="float", value=10, step=2),
            dict(name="Shots", type="int", value=90, step=10),
            dict(name="Start Calibration", type="action"),
        ]
        param = Parameter.create(
            name="Calibration Scan", type="group", children=self.children
        )
        if (s := "CalibSettings") in config.exp_settings:
            param.restoreState(
                config.exp_settings[s], addChildren=False, removeChildren=False
            )

        self.params: Parameter = param
        pt = ParameterTree()
        pt.setParameters(self.params)
        pt.setMaximumSize(300, 1000)

        self.layout().addWidget(pt)
        self.params.child("Start Calibration").sigActivated.connect(self.start)
        self.plot = PlotWidget(self)
        self.layout().addWidget(self.plot)
        self.info_label = QLabel()
        self.layout().addWidget(self.info_label)
        self.setMinimumSize(1200, 600)

    def start(self):
        s = self.params.saveState()
        config.exp_settings["CalibSettings"] = s
        start, stop, step = (
            self.params["Start Wavelength (nm)"],
            self.params["End Wavelength (nm)"],
            self.params["Step (nm)"],
        )
        config.save()

        self.params.setReadonly(True)
        # self.params.child("Start Calibration").setEnabled(False)
        self.plan = CalibPlan(
            cam=self.cam,
            dac=self.dac,
            points=np.arange(start, stop, step).tolist(),
            num_shots=self.params["Shots"],
        )
        self.sigPlanCreated.emit(self.plan)

        self.plan.sigPlanFinished.connect(self.analyse)
        self.plan.sigStepDone.connect(self.update_view)

    @Slot()
    def update_view(self):
        assert self.plan is not None
        plan = self.plan

        self.plot.plotItem.clear()
        n = len(plan.amps)
        x = plan.points[:n]
        y = np.array(plan.amps)

        self.plot.plotItem.plot(x, y[:, 0], pen="r")
        self.plot.plotItem.plot(x, y[:, 1], pen="g")
        self.plot.plotItem.plot(x, y[:, 2], pen="y")

        self.info_label.setText(f"""
        Point {n}/{len(plan.points)}
        Channel {plan.channel}
        """)

    def analyse(self):
        assert self.plan is not None
        plan = self.plan
        x = np.array(plan.points)
        y_train = np.array(plan.amps)[:, 0]
        y_single = np.array(plan.amps)[:, 1]
        y_full = np.array(plan.amps)[:, 2]
        np.save("calib.npy", np.column_stack((x, y_train, y_single, y_full)))
        single_arr = np.column_stack((x[:, None], plan.single_spectra.T))
        np.save(f"wl_calib_{plan.channel}.npy", single_arr)
        self._view = CalibView(
            single=plan.single,
            width=plan.width,
            dist=plan.separation,
            x=x,
            y_train=y_train - y_train.min(),
            y_single=y_single - y_single.min(),
            y_full=y_full - y_full.min(),
        )

        self._view.sigCalibrationAccepted.connect(plan.dac.set_calib)
        self._view.sigCalibrationAccepted.connect(
            lambda arg: plan.dac.generate_waveform()
        )
        self._view.sigCalibrationAccepted.connect(
            lambda: QMessageBox.information(self, "Calib applied", str(plan.dac.calib))
        )
        self._view.show()


@attr.s(auto_attribs=True)
class CalibView2(QWidget):
    x: np.ndarray
    y_train: np.ndarray
    y_single: np.ndarray
    y_full: Optional[np.ndarray] = None

    single: int = 15
    width: int = 150
    dist: int = 350

    prominence: float = 50
    distance: int = 3
    filter: float = 0

    coeff: Optional[np.ndarray] = None

    sigCalibrationAccepted = Signal(object)
    sigCalibrationCanceled = Signal()

    def __attrs_post_init__(self):
        super().__init__()
        self.setWindowTitle("Calibration")
        self.setWindowIcon(icon("fa5s.ruler-horizontal"))
        self.setLayout(QVBoxLayout())

        # Top and bottom plots using pyqtgraph
        self.plot_top = PlotWidget()
        self.plot_bottom = PlotWidget()
        # dark background
        try:
            self.plot_top.setBackground("k")
            self.plot_bottom.setBackground("k")
        except Exception:
            pass

        # set labels
        self.plot_top.setLabel("bottom", "Wavelength", units="nm")
        self.plot_top.setLabel("left", "Counts")
        self.plot_bottom.setLabel("bottom", "Pixel")
        self.plot_bottom.setLabel("left", "Freq / THz")

        # controls row
        self.row = QHBoxLayout()
        self.sb_filter = QSpinBox()
        self.sb_filter.setValue(int(self.filter))
        self.sb_filter.valueChanged.connect(self.analyze)
        self.row.addWidget(QLabel("Filter"))
        self.row.addWidget(self.sb_filter)

        self.sb_dist = QSpinBox()
        self.sb_dist.setValue(int(self.distance))
        self.sb_dist.valueChanged.connect(self.analyze)
        self.sb_dist.setMinimum(1)

        self.row.addWidget(QLabel("Peak distance"))
        self.row.addWidget(self.sb_dist)

        self.sb_prom = QSpinBox()
        self.sb_prom.setMaximum(20000)
        self.sb_prom.setValue(int(self.prominence))
        self.sb_prom.valueChanged.connect(self.analyze)
        self.row.addWidget(QLabel("Peak prominance"))
        self.row.addWidget(self.sb_prom)

        self.use_norm = QCheckBox("Normalize")
        self.use_norm.setChecked(True)
        self.use_norm.toggled.connect(self.analyze)
        self.row.addWidget(self.use_norm)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.row.addWidget(bb)
        # bb.setFixedWidth(400)
        bb.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.row.setContentsMargins(20, 20, 20, 20)
        self.row.setSpacing(10)
        bb.accepted.connect(lambda: self.sigCalibrationAccepted.emit(self.coeff))
        bb.rejected.connect(self.close)
        bb.rejected.connect(self.sigCalibrationCanceled.emit)
        bb.rejected.connect(self.close)

        self.layout().addWidget(self.plot_top)
        self.layout().addWidget(self.plot_bottom)
        self.layout().addLayout(self.row)

        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.analyze()

    def analyze(self):
        # Read control values
        self.prominence = self.sb_prom.value()
        self.distance = self.sb_dist.value()
        self.filter = self.sb_filter.value()

        # Filter / normalize
        if self.filter > 0:
            y_train = gaussian_filter1d(self.y_train, self.filter)
            y_single = gaussian_filter1d(self.y_single, self.filter)
            y_full = (
                gaussian_filter1d(self.y_full, self.filter)
                if self.y_full is not None
                else None
            )
        else:
            y_train, y_single, y_full = self.y_train, self.y_single, self.y_full
        if self.use_norm.isChecked() and (y_full is not None):
            y_train = 500 * (y_train / (y_full + 50))
            y_single = 500 * (y_single / (y_full + 50))

        p0, _ = find_peaks(y_train, prominence=self.prominence, distance=self.distance)
        p1, _ = find_peaks(y_single, prominence=self.prominence, distance=self.distance)

        # Clear plots
        self.plot_top.clear()
        self.plot_bottom.clear()

        # Top plot: lines
        x = self.x
        self.plot_top.plot(x, y_train, pen="w", name="train")
        self.plot_top.plot(x, y_single, pen="y", name="single")
        if self.y_full is not None and not self.use_norm.isChecked():
            self.plot_top.plot(x, self.y_full, pen="g", name="full")

        # Mark peaks using scatter
        if p0.size:
            spots0 = [
                {"pos": (float(xi), float(yi))} for xi, yi in zip(x[p0], y_train[p0])
            ]
            s0 = ScatterPlotItem(size=7, brush="r")
            s0.addPoints(spots0)
            self.plot_top.addItem(s0)
        if p1.size:
            spots1 = [
                {"pos": (float(xi), float(yi))} for xi, yi in zip(x[p1], y_single[p1])
            ]
            s1 = ScatterPlotItem(size=7, brush="r", symbol="t")
            s1.addPoints(spots1)
            self.plot_top.addItem(s1)

        # Bottom plot: alignment / frequency
        if len(p0) > 1 and len(p1) == 1:
            a = np.arange(-100, 101) * self.dist
            align = np.argmin(abs(x[p0] - x[p1]))
            pix0 = self.single
            pixel = a[: len(p0)] - a[align] + pix0

            freqs = c / x[p0] / 1e3
            freq0 = c / x[p1] / 1e3

            # plot single point
            self.plot_bottom.plot([pix0], [freq0], pen=None, symbol="o")

            # plot pixel vs freqs
            self.plot_bottom.plot(pixel, freqs, pen=None, symbol="x")

            all_pix = np.arange(int(pixel.min()), int(pixel.max()) + 1)
            self.coeff = np.polyfit(pixel, freqs, 2)
            fit = np.polyval(self.coeff, all_pix)

            # show fit line
            self.plot_bottom.plot(all_pix, fit, pen={"color": "lime"})

            # annotate coefficients
            txt = "\n".join(["%.3e" % i for i in self.coeff])
            ti = TextItem(txt, color="w")
            ti.setPos(float(all_pix.max()), float(fit.max()))
            self.plot_bottom.addItem(ti)


if __name__ == "__main__":
    from MessPy.Instruments.dac_px import AOM

    aom = AOM()
    app = QApplication([])
    x, y_train, y_single, y_full = np.load("calib.npy").T
    y_single -= y_single.min()
    y_train -= y_train.min()
    y_full -= y_full.min()
    view = CalibView(x=x, y_single=y_single, y_train=y_train, y_full=y_full)
    view.show()
    app.exec_()
