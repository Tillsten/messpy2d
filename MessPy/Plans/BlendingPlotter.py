import numpy as np

from pyqtgraph import (
    PlotDataItem,
    PlotItem,
    PlotWidget,
    GraphicsLayoutWidget,
    mkPen,
    mkColor,
)


class BlendingPlotter(PlotWidget):
    def __init__(
        self,
        num_plots=20,
        color="y",
        width=4,
        parent=None,
        background="default",
        plotItem=None,
        **kargs,
    ):
        super().__init__(parent, background, plotItem, **kargs)
        self.setWindowTitle("Blending Plotter")
        self.plotItem = self.getPlotItem()
        self.num_plots = num_plots
        self.lines: list[PlotDataItem] = []
        for i in range(num_plots):
            if i < num_plots:
                color = mkColor(color)
                pen = mkPen(color, width=width, antialias=False)
            else:
                pen = mkPen(color="red", width=2, antialias=True)
            self.lines.append(
                self.plotItem.plot(
                    np.zeros(100), pen=pen, name=f"Plot {i + 1}", clear=False
                )
            )
            self.lines[-1].setZValue(-i)
            self.lines[-1].setOpacity((i / num_plots) ** 2)

        self.showGrid(x=True, y=True)
        self.current_line = 0  # Track which line to update next

    def update_plots(self, data: np.ndarray, x=None):
        if x is None:
            x = np.arange(data.shape[0])

        # Update the data of the current line
        self.lines[self.current_line].setData(x, data)

        # Update opacity and z-values for all lines
        for i in range(self.num_plots):
            # Calculate age: how many positions behind the current line
            age = (self.current_line - i) % self.num_plots
            # Newer lines have higher opacity
            opacity = ((self.num_plots - age) / self.num_plots) ** 2
            self.lines[i].setOpacity(opacity)
            # Newer lines are on top
            self.lines[i].setZValue(-age)

        # Move to next line (circular)
        self.current_line = (self.current_line + 1) % self.num_plots


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    import time

    app = QApplication(sys.argv)
    plotter = BlendingPlotter(num_plots=40, width=3, useOpenGL=False)
    plotter.show()
    timer = QTimer()
    last_time = time.time()
    n_frames = 0

    def add_line():
        global last_time, n_frames
        cur_time = time.time()
        last_time = cur_time - last_time
        n_frames += 1

        data = np.sin(np.linspace(0, 2 * np.pi, 128) + 0 * cur_time) * (
            np.sin(cur_time) * 10
        ) + np.random.normal(0, 0.5, 128)
        plotter.update_plots(data)
        if n_frames % 20 == 0:
            print(f"FPS: {1 / (last_time + 1e-6):.2f} {n_frames}", end="\r")
        last_time = cur_time

    # print fps

    timer.timeout.connect(add_line)
    timer.start(10)

    sys.exit(app.exec())
