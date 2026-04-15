from PySide6.QtWidgets import (
    QWidget,
    QSpinBox,
    QPushButton,
    QHBoxLayout,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
    QApplication,
    QCheckBox,
)
from PySide6.QtCore import Signal
from typing import Optional


from pyqtgraph import PlotWidget, TextItem, ScatterPlotItem, InfiniteLine, mkPen
import attr
import numpy as np
from scipy.constants import c
from scipy.optimize import least_squares
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d, gaussian_filter1d


def nm2THz(x):
    return c / x / 1e3


def THz2nm(x):
    return c / x / 1e3


def gauss(x, xc, A, sigma, sum_up=True):
    peaks = A * np.exp(-0.5 * ((x[:, None] - xc) / sigma) ** 2)
    if sum_up:
        return peaks.sum(1)
    else:
        return peaks


def gauss_trains(x, y, start_idx, start_width, dist=300):
    n = len(start_idx)
    pix_pos = np.arange(n) * dist
    fit = np.polyfit(pix_pos, nm2THz(x[p1]), 2)
    start = np.int16(np.polyval(fit, pix_pos))
    return gauss(
        nm2THz(x),
        start,
        y[start_idx],
        10,
    )


@attr.s(auto_attribs=True)
class CalibView(QWidget):
    x: np.ndarray
    y_train: np.ndarray
    y_single: np.ndarray
    y_full: Optional[np.ndarray] = None

    single: int = 6000
    width: int = 50
    dist: int = 500

    prominence: float = 30
    distance: int = 3
    filter: float = 0
    area: float = 25.0

    coeff: Optional[np.ndarray] = None

    sigCalibrationAccepted = Signal(object)
    sigCalibrationCanceled = Signal()

    def __attrs_post_init__(self):
        super().__init__()
        self.setWindowTitle("Calibration")
        self.setLayout(QVBoxLayout())

        # pyqtgraph plots
        self.plot_norm = PlotWidget()
        self.plot_calib = PlotWidget()
        self.plot_raw = PlotWidget()

        self.row = QHBoxLayout()
        self.sb_filter = QSpinBox()
        self.sb_filter.setValue(self.filter)
        self.sb_filter.valueChanged.connect(self.analyze)
        self.row.addWidget(QLabel("Filter"))
        self.row.addWidget(self.sb_filter)

        self.sb_dist = QSpinBox()
        self.sb_dist.setValue(self.distance)
        self.sb_dist.valueChanged.connect(self.analyze)
        self.sb_dist.setMinimum(1)

        self.sb_area = QSpinBox()
        self.sb_area.setMaximum(200)
        self.sb_area.setValue(self.area)
        self.sb_area.valueChanged.connect(self.analyze)
        self.row.addWidget(QLabel("Fit interval"))
        self.row.addWidget(self.sb_area)

        self.row.addWidget(QLabel("Peak distance"))
        self.row.addWidget(self.sb_dist)

        self.sb_prom = QSpinBox()
        self.sb_prom.setMaximum(20000)
        self.sb_prom.setValue(self.prominence)
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
        bb.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)

        self.row.setSpacing(50)
        bb.accepted.connect(lambda: self.sigCalibrationAccepted.emit(self.coeff))
        bb.rejected.connect(self.close)
        bb.rejected.connect(self.sigCalibrationCanceled.emit)
        bb.rejected.connect(self.close)

        self.layout().addWidget(self.plot_raw)
        self.layout().addWidget(self.plot_norm)
        self.layout().addWidget(self.plot_calib)
        self.layout().addLayout(self.row)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.plot_raw.plot(self.x, self.y_full, pen=mkPen("g", width=3))
        self.plot_raw.plot(self.x, self.y_single, pen=mkPen("y", width=3))
        self.plot_raw.plot(self.x, self.y_train, pen=mkPen("r", width=3))

        self.analyze()

    def analyze(self):
        self.prominence = self.sb_prom.value()
        self.distance = self.sb_dist.value()
        self.filter = self.sb_filter.value()
        self.area = self.sb_area.value()

        x = self.x
        if self.filter > 0:
            y_train = gaussian_filter1d(self.y_train, self.filter)
            y_single = gaussian_filter1d(self.y_single, self.filter)
            y_full = gaussian_filter1d(self.y_full, self.filter)
        else:
            y_train, y_single, y_full = self.y_train, self.y_single, self.y_full
        if self.use_norm.isChecked():
            assert y_full is not None
            y_train = 500 * (y_train / (y_full + 100))
            y_single = 500 * (y_single / (y_full + 100))

        y_train -= y_train.min()
        y_single -= y_single.min()

        p_trains, _ = find_peaks(
            y_train, prominence=self.prominence, distance=self.distance
        )
        p_single, _ = find_peaks(
            y_single, prominence=self.prominence, distance=self.distance
        )
        print(f"Found {len(p_trains)} train peaks and {len(p_single)} single peaks")
        # clear plots
        self.plot_norm.clear()
        self.plot_calib.clear()

        self.plot_norm.plot(x, y_train, pen=mkPen("r", width=2))
        self.plot_norm.plot(x, y_single, pen=mkPen("y", width=2))
        self.plot_norm.plot(x[p_trains], y_train[p_trains], pen=None, symbol="o")
        self.plot_norm.plot(x[p_single], y_single[p_single], pen=None, symbol="x")

        ppos = []
        pheight = []
        for p in p_trains:
            reg = abs(x - x[p]) < self.area

            data = y_train[reg]
            xr = x[reg]
            import lmfit

            mod = lmfit.models.GaussianModel()

            params = mod.guess(data, x=xr)
            res = mod.fit(data, params, x=xr)
            xr_upsampled = np.linspace(xr.min(), xr.max(), 10 * len(xr))
            self.plot_norm.plot(
                xr_upsampled,
                mod.eval(x=xr_upsampled, **res.params),
                pen="cyan",
            )
            self.plot_norm.plot(xr, data, pen="w", alpha=0.5)

            ppos.append(res.params["center"])
            pheight.append(res.params["height"])
        ppos = np.array(ppos)
        pheight = np.array(pheight)
        self.plot_norm.plot(ppos, pheight, pen=None, symbol="t")
        # markers: use simple plot symbols instead of ScatterPlotItem for simplicity
        if p_trains.size:
            self.plot_norm.plot(
                self.x[p_trains],
                y_train[p_trains],
                pen=None,
                symbol="o",
                symbolBrush="r",
                symbolSize=7,
            )
        if p_single.size:
            self.plot_norm.plot(
                self.x[p_single],
                y_single[p_single],
                pen=None,
                symbol="x",
                symbolBrush="r",
                symbolSize=7,
            )

        if len(p_trains) > 1 and len(p_single) > 0:
            p_single = [p_single[np.argmax(y_single[p_single])]]
            a = np.arange(0, len(p_trains)) * self.dist
            same_peak_idx = np.argmin(abs(self.x[p_trains] - self.x[p_single]))
            pix0 = self.single
            pixel = a - a[same_peak_idx] + pix0

            freqs = c / ppos / 1e3
            freq0 = c / ppos[same_peak_idx] / 1e3

            # points and fit
            self.plot_calib.plot([pix0], [freq0], pen=None, symbol="o")
            self.plot_calib.plot(pixel, freqs, pen=None, symbol="x")

            all_pix = np.arange(int(pixel.min()), int(pixel.max()) + 1)
            self.coeff = np.polyfit(pixel, freqs, 2)
            fit = np.polyval(self.coeff, all_pix)
            self.plot_calib.plot(all_pix, fit, pen={"color": "lime", "width": 2})

            txt = "\n".join(["%.3e" % i for i in self.coeff])
            ti = TextItem(txt, color="w")
            ti.setPos(float(all_pix.max()), float(fit.max()))
            self.plot_calib.addItem(ti)


if __name__ == "__main__":
    # from MessPy.Instruments.dac_px import AOM

    # from qt_material import apply_stylesheet
    # apply_stylesheet(app, 'light_blue.xml')
    x, y_train, y_single, y_full = np.load(
        r"C:\Users\TillStensitzki\Nextcloud\messpy2d-1\MessPy\calib.npy"
    ).T
    # y_single -= y_single.min()
    # y_train -= y_train.min()
    # y_full -= y_full.min()
    # y_norm = 100 * y_train / (y_full + 50)
    # y_norm_s = 100 * y_single / (y_full + 50)
    # import matplotlib.pyplot as plt

    # p1, _ = find_peaks(y_norm, prominence=20, distance=3)
    # ps, _ = find_peaks(y_norm_s, prominence=20, distance=3)
    # pix_pos = (np.arange(len(p1)) - np.argmin(abs(p1 - ps))) * 300 + 6000

    # fit = np.polyfit(pix_pos, nm2THz(x[p1]), 2)
    # # plt.plot(pix_pos, nm2THz(x[p1]), 's')
    # # plt.plot(pix_pos, np.polyval(fit, pix_pos))
    # start_idx = np.int16(np.polyval(fit, pix_pos))

    # def gauss_trains(
    #     x, y, single_idx, train_idx, start_width=0.1, dist=300, single=6000
    # ):
    #     n = len(start_idx)
    #     same = np.argmin(abs(single_idx - train_idx))
    #     pix_pos = (np.arange(n) - same) * dist
    #     fit = np.polyfit(pix_pos, nm2THz(x[p1]), 2)

    #     starting_guess = np.hstack((fit, start_width, y[train_idx]))

    #     def eval(p):
    #         coefs = p[: len(fit)]
    #         width = p[len(fit)]
    #         # print(width)
    #         amps = p[len(fit) + 1 : len(fit) + n + 1]
    #         x_pos = np.polyval(coefs, pix_pos)
    #         return gauss(nm2THz(x), x_pos, amps, width) - y

    #     fr = least_squares(eval, starting_guess)
    #     return fr

    # fr = gauss_trains(x, y_norm, p1, 0.1)
    # print(fr["x"][:3])
    # plt.plot(x, fr["fun"] + y_norm)

    # plt.plot(x, y_norm)
    # plt.show()
    # aom = AOM()
    print(x.shape, y_single.shape, y_train.shape, y_full.shape)
    app = QApplication([])
    app.setStyle("Fusion")
    import pyqtgraph as pg

    pg.setConfigOption("antialias", True)
    view = CalibView(x=x, y_single=y_single, y_train=y_train, y_full=y_full)
    # view.sigCalibrationAccepted.connect(aom.set_calib)
    view.show()
    app.exec_()
