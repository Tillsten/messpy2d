from attr import dataclass, attr

from matplotlib.colors import Colormap
from pyqtgraph import (
    GraphicsLayoutWidget,
    PlotItem,
    ImageItem,
    InfiniteLine,
    PlotDataItem,
    mkPen,
)
from pyqtgraph.colormap import getFromColorcet, ColorMap

from typing import ClassVar, Literal

import numpy as np

from PySide6.QtCore import Qt


@dataclass
class PumpProbeData:
    delay_times: np.ndarray
    wavelengths: np.ndarray
    data: np.ndarray

    def get_transient(self, wavelength: float) -> np.ndarray:
        idx = np.argmin(np.abs(self.wavelengths - wavelength))
        return self.data[:, idx]

    def get_spectrum(self, delay_time: float) -> np.ndarray:
        idx = np.argmin(np.abs(self.delay_times - delay_time))
        return self.data[idx, :]


@dataclass
class Crosshair:
    vline: InfiniteLine = attr(factory=lambda: InfiniteLine(angle=90, movable=False))
    hline: InfiniteLine = attr(factory=lambda: InfiniteLine(angle=0, movable=False))

    def get_position(self) -> tuple[float, float]:
        return self.vline.value(), self.hline.value()

    def set_position(self, x: float, y: float):
        self.vline.setValue(x)
        self.hline.setValue(y)


@dataclass
class PumpProbeView(GraphicsLayoutWidget):
    data: PumpProbeData
    observed_wavelenths: list[float] = attr(factory=list)
    observed_times: list[float] = attr(factory=list)

    crosshair: Crosshair = attr(factory=Crosshair)
    two_d_map: ImageItem = attr(init=False)
    trans_plot: PlotItem = attr(init=False)
    trans_plot_line: PlotDataItem = attr(init=False)

    spec_plot: PlotItem = attr(init=False)
    spec_plot_line: PlotDataItem = attr(init=False)
    cur_spec_plot: PlotItem = attr(init=False)
    x_unit: Literal["nm", "cm-1"] = "cm-1"
    display_mode: Literal["mean", "current"] = "mean"

    def __attrs_post_init__(self):
        super().__init__(border=True)
        self.setAntialiasing(True)
        self.setWindowTitle("Pump-Probe Shaper View")

        self.spec_plot = self.ci.addPlot(1, 0)
        self.spec_plot.setLabels(left="ΔA", bottom="Wavelength (nm)")
        self.spec_plot_line = self.spec_plot.plot(
            [], [], pen=mkPen("y", width=2), antialias=True
        )

        self.trans_plot = self.ci.addPlot(0, 1)
        self.trans_plot.setLabels(left="ΔA", bottom="Delay Time (ps)")

        self.trans_plot_line = self.trans_plot.plot(
            [], [], pen=mkPen("y", width=2), antialias=True
        )

        self.two_d_map = ImageItem()
        two_d_view = self.ci.addViewBox(1, 1)
        two_d_view.addItem(self.two_d_map)

        two_d_view.addItem(self.crosshair.vline)
        two_d_view.addItem(self.crosshair.hline)

        two_d_view.scene().sigMouseMoved.connect(self.move_cross_events)
        two_d_view.scene().sigMouseClicked.connect(self.click_event)
        two_d_view.setMenuEnabled(False)

        self.two_d_view = two_d_view
        cmap = getFromColorcet("CET_D1")
        # cmap.setMappingMode(ColorMap.DIVERGING)
        self.two_d_map.setColorMap(cmap)

        self.ci.layout.setColumnStretchFactor(1, 2)
        self.ci.layout.setRowStretchFactor(1, 2)
        self.ci.setBorder(2)

    def move_cross_events(self, ev):
        pos = ev
        if self.two_d_map.sceneBoundingRect().contains(pos):
            mousePoint = self.two_d_map.getViewBox().mapSceneToView(pos)
            self.crosshair.vline.setPos(mousePoint.x())
            self.crosshair.hline.setPos(mousePoint.y())
            self.update_plots()

    def click_event(self, ev):
        pos = ev.scenePos()
        if self.two_d_map.sceneBoundingRect().contains(pos):
            mousePoint = self.two_d_map.getViewBox().mapSceneToView(pos)

            if ev.button() == Qt.MouseButton.LeftButton:  # Left click
                wl = self.data.wavelengths[int(mousePoint.y() + 0.5)]
                self.observed_wavelenths.append(wl)
                self.trans_plot.plot(
                    self.data.delay_times,
                    self.data.get_transient(wl),
                    pen=mkPen("r", width=1),
                    name=f"{wl:.1f} nm",
                )
            elif ev.button() == Qt.MouseButton.RightButton:  # Right click
                dt = self.data.delay_times[int(mousePoint.x() + 0.5)]
                self.observed_times.append(dt)
                x = self.data.wavelengths
                if self.x_unit == "cm-1":
                    x = 1e7 / x
                self.spec_plot.plot(
                    x,
                    self.data.get_spectrum(dt),
                    pen=mkPen("g", width=1),
                    name=f"{dt:.1f} ps",
                )
            ev.accept()

    def update_plots(self):
        m = np.max(np.abs(self.data.data))
        self.two_d_map.setImage(self.data.data, levels=(-m, m))
        self.two_d_map.setRect(
            0, 0, self.data.delay_times.size, self.data.wavelengths.size
        )

        x_pos, y_pos = self.crosshair.get_position()

        old_activate = self.ci.layout.activate
        self.ci.layout.invalidate = (
            lambda: None
        )  # Disable layout activation temporarily
        self.trans_plot_line.setData(
            self.data.delay_times,
            self.data.data.T[int(y_pos + 0.5)],
        )

        x = self.data.wavelengths
        if self.x_unit == "cm-1":
            x = 1e7 / x
        self.spec_plot_line.setData(x, self.data.data[int(x_pos + 0.5), :])

        self.ci.layout.invalidate = old_activate  # Restore layout activation

    @property
    def observed_wn(self) -> list[float]:
        return [1e7 / wl for wl in self.observed_wavelenths]


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    import h5py

    with h5py.File(r"MessPy\Plans\25-08-05 15_44 PumpProbe cav_0.2benz_0.h5", "r") as f:
        # Load data from the HDF5 file
        wl = f["wl_Phasetec Array"][0, :]
        t = f["t"][:]
        data = f["data_Phasetec Array"][:]

    app = QApplication(sys.argv)
    print("Loaded data shape:", data.shape, wl.shape, t.shape)
    data = data.mean(0)[0, :, 0, :]
    pp_data = PumpProbeData(delay_times=t, wavelengths=wl, data=data)
    view = PumpProbeView(data=pp_data)
    view.update_plots()
    view.show()
    sys.exit(app.exec())
