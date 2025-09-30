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


from matplotlib.figure import Figure
from matplotlib import rcParams, style
from matplotlib.backends.backend_qt5agg import (
    FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
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

    prominence: float = 50
    distance: int = 3
    filter: float = 0

    coeff: Optional[np.ndarray] = None

    sigCalibrationAccepted = Signal(object)
    sigCalibrationCanceled = Signal()

    def __attrs_post_init__(self):
        super().__init__()
        dpi = self.logicalDpiX()
        self.setWindowTitle("Calibration")
        # self.setWindowIcon(icon("fa5s.ruler-horizontal"))
        self.fig = Figure(dpi=dpi, constrained_layout=True)
        self.ax0, self.ax2 = self.fig.subplots(2)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayout(QVBoxLayout())

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.setContentsMargins(0, 0, 0, 0)
        self.canvas.setContentsMargins(0, 0, 0, 0)

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
        self.row.setContentsMargins(20, 20, 20, 20)
        self.row.setSpacing(10)
        bb.accepted.connect(lambda: self.sigCalibrationAccepted.emit(self.coeff))
        bb.rejected.connect(self.close)
        bb.rejected.connect(self.sigCalibrationCanceled.emit)
        bb.rejected.connect(self.close)

        self.layout().addWidget(self.toolbar)
        self.layout().addWidget(self.canvas)
        self.layout().addLayout(self.row)

        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.analyze()
        self.fig.canvas.draw()

    def analyze(self, area=10):
        self.prominence = self.sb_prom.value()
        self.distance = self.sb_dist.value()
        self.filter = self.sb_filter.value()
        x = self.x
        if self.filter > 0:
            y_train = gaussian_filter1d(self.y_train, self.filter)
            y_single = gaussian_filter1d(self.y_single, self.filter)
            y_full = gaussian_filter1d(self.y_full, self.filter)
        else:
            y_train, y_single, y_full = self.y_train, self.y_single, self.y_full
        if self.use_norm.isChecked():
            y_train = 500 * (y_train / (y_full + 100))
            y_single = 500 * (y_single / (y_full + 100))

        p0, _ = find_peaks(y_train, prominence=self.prominence, distance=self.distance)
        p1, _ = find_peaks(y_single, prominence=self.prominence, distance=self.distance)
        self.ax0.cla()
        ppos = []
        for p in p0:
            reg = abs(x - x[p]) < area
            data = y_train[reg]
            xr = x[reg]
            import lmfit

            mod = lmfit.models.GaussianModel()
            params = mod.guess(data, x=xr)
            res = mod.fit(data, params, x=xr)
            self.ax0.plot(xr, data)
            self.ax0.plot(xr, res.best_fit, c="0.5", lw=1)
            ppos.append(res.params["center"])
        ppos = np.array(ppos)

        self.ax2.cla()
        self.ax0.plot(self.x, y_train)
        self.ax0.plot(self.x, y_single)
        if self.y_full is not None and not self.use_norm.isChecked():
            self.ax0.plot(self.x, y_full)
        ax1 = self.ax2

        self.ax0.plot(self.x[p0], y_train[p0], "|", ms=7, c="r")
        self.ax0.plot(self.x[p1], y_single[p1], "^", ms=7, c="r")

        self.ax0.plot(ppos, y_train[p0], "|", ms=7, c="r")
        if len(p0) > 1 and len(p1) > 1:
            import matplotlib.pyplot as plt

            p1 = [p1[np.argmax(y_single[p1])]]
            a = np.arange(0, len(p0)) * self.dist
            same_peak_idx = np.argmin(abs(x[p0] - x[p1]))
            pix0 = self.single
            pixel = a - a[same_peak_idx] + pix0

            freqs = c / ppos / 1e3
            freq0 = c / ppos[same_peak_idx] / 1e3
            # print(np.polyfit(ppos, freqs, 2))
            ax1.axhline(freq0)
            ax1.plot(pix0, freq0, marker="o", ms=10)
            ax1.set_xlabel("Pixel")
            ax1.set_ylabel("Freq / THz")
            self.ax0.set(xlabel="Wavelength / nm", ylabel="Counts")

            ax1.plot(pixel, freqs, marker="x", ms=10)
            all_pix = np.arange(pixel.min(), pixel.max())
            self.coeff = np.polyfit(pixel, freqs, 2)
            fit = np.polyval(self.coeff, all_pix)
            txt = "".join(["%.3e\n" % i for i in self.coeff])
            ax1.annotate(
                txt, (0.95, 0.93), xycoords="axes fraction", va="top", ha="right"
            )
            ax1.secondary_yaxis(
                "right", functions=(lambda f: c / f / 1e3, lambda f: c / f / 1e3)
            )
            # ax1.plot(all_pix, fit, color="xkcd:lime")

            self.fig.canvas.draw_idle()


if __name__ == "__main__":
    from MessPy.Instruments.dac_px import AOM

    # from qt_material import apply_stylesheet
    # apply_stylesheet(app, 'light_blue.xml')
    x, y_train, y_single, y_full = np.load("../calib.npy").T
    y_single -= y_single.min()
    y_train -= y_train.min()
    y_full -= y_full.min()
    y_norm = 100 * y_train / (y_full + 50)
    y_norm_s = 100 * y_single / (y_full + 50)
    import matplotlib.pyplot as plt

    p1, _ = find_peaks(y_norm, prominence=20, distance=3)
    ps, _ = find_peaks(y_norm_s, prominence=20, distance=3)
    pix_pos = (np.arange(len(p1)) - np.argmin(abs(p1 - ps))) * 300 + 6000

    fit = np.polyfit(pix_pos, nm2THz(x[p1]), 2)
    # plt.plot(pix_pos, nm2THz(x[p1]), 's')
    # plt.plot(pix_pos, np.polyval(fit, pix_pos))
    start_idx = np.int16(np.polyval(fit, pix_pos))

    def gauss_trains(
        x, y, single_idx, train_idx, start_width=0.1, dist=300, single=6000
    ):
        n = len(start_idx)
        same = np.argmin(abs(single_idx - train_idx))
        pix_pos = (np.arange(n) - same) * dist
        fit = np.polyfit(pix_pos, nm2THz(x[p1]), 2)

        starting_guess = np.hstack((fit, start_width, y[train_idx]))

        def eval(p):
            coefs = p[: len(fit)]
            width = p[len(fit)]
            # print(width)
            amps = p[len(fit) + 1 : len(fit) + n + 1]
            x_pos = np.polyval(coefs, pix_pos)
            return gauss(nm2THz(x), x_pos, amps, width) - y

        fr = least_squares(eval, starting_guess)
        return fr

    fr = gauss_trains(x, y_norm, p1, 0.1)
    print(fr["x"][:3])
    plt.plot(x, fr["fun"] + y_norm)

    plt.plot(x, y_norm)
    plt.show()
    # aom = AOM()
    # app = QApplication([])
    # view = CalibView(x=x, y_single=y_single, y_train=y_train, y_full=y_full)
    # view.sigCalibrationAccepted.connect(aom.set_calib)
    # view.show()
    # app.exec_()
