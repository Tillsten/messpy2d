
import numpy as np
import pyqtgraph as pg
import pyqtgraph.parametertree as pt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import ObserverPlot, PlanStartDialog, hlay, make_entry, vlay

from .FocusScan import FocusScan, Scan
from .PlanBase import sample_parameters


class FocusScanView(QWidget):
    def __init__(self, fsPlan: FocusScan, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = fsPlan
        self.plot_layout = QVBoxLayout(self)
        self.obs_plots = {}
        tab = QTabWidget()
        self.plot_layout.addWidget(tab)
        for iz, z in enumerate(self.plan.z_points):
            tabwidget = QWidget()
            tabwidget.setLayout(vlay())
            tab.addTab(tabwidget, f"z = {z:.3f} mm")
            for axis in ["x", "y"]:
                scan: Scan | None = fsPlan.scans["%s_%d" % (axis, iz)]
                print(scan)
                if scan is not None:
                    plots = []

                    def x_func(scan=scan):
                        return scan.get_data()[0]

                    n = 2 if fsPlan.power_meter is None else 3
                    for ix in range(1, n + 1):
                        self.obs_plots["%d_%s_%d" % (iz, axis, ix)] = ObserverPlot(
                            [lambda ix=ix, scan=scan: scan.get_data()[ix]],
                            x=x_func,
                            signal=fsPlan.sigStepDone,
                            title=f"{axis} z={z}",
                        )
                        plots.append(self.obs_plots["%d_%s_%d" % (iz, axis, ix)])
                    tabwidget.layout().addLayout(hlay(plots))
        self.tabwidget = tab
        self.button = QPushButton("Save Scan", self)
        self.button.setEnabled(False)
        self.button.clicked.connect(fsPlan.save)
        fsPlan.sigFitDone.connect(self.plot_fit)
        fsPlan.sigFitDone.connect(lambda: self.button.setEnabled(True))
        fname = fsPlan.get_file_name()[0]
        self.button.clicked.connect(
            lambda: QMessageBox.information(self, "Results Saved", "At %s" % str(fname))
        )

        self.plot_layout.addWidget(self.button)
        if len(self.plan.z_points) > 1:
            self.vis = pg.GraphicsLayoutWidget()
            self.summary = {}
            if self.plan.x_parameters is not None:
                self.summary["x"] = self.vis.addPlot(title="X")
            if self.plan.y_parameters is not None:
                self.summary["y"] = self.vis.addPlot(title="Y")

            self.plot_layout.addWidget(self.vis)

    def plot_fit(self, i):
        pen = pg.mkPen(color="#e377c2", width=2)
        self.tabwidget.setCurrentIndex(i)
        for axis in ("x", "y"):
            scan: Scan | None = self.plan.scans["%s_%d" % (axis, i)]
            if scan is not None:
                pr, ref, pw = scan.analyze()
                probe_plot, ref_plot = (
                    self.obs_plots[f"{i}_{axis}_1"],
                    self.obs_plots[f"{i}_{axis}_2"],
                )
                probe_plot.plot(pr.pos, pr.model, pen=pen)
                ref_plot.plot(ref.pos, ref.model, pen=pen)
                if pw is not None:
                    pw_plot = self.obs_plots[f"{i}_{axis}_3"]
                    pw_plot.plot(pw.pos, pw.model, pen=pen)
                else:
                    pw_plot = None
                for plot, data, fit in [
                    (probe_plot, scan.probe, pr),
                    (ref_plot, scan.ref, ref),
                    (pw_plot, scan.extra if pw is not None else None, pw),
                ]:
                    if data is not None:
                        text = pg.TextItem(fit.make_text(), anchor=(0, 1.0))
                        text.setPos(
                            scan.pos[int(len(scan.pos) / 2)],
                            (np.max(data) + np.min(data)) / 2.0,
                        )
                        plot.plotItem.addItem(text)
        if len(self.plan.z_points) > 1:
            for axis in ("x", "y"):
                scan = self.plan.scans[f"{axis}_{i}"]
                if scan is not None:
                    x, y = scan.get_data()[:2]
                    from scipy.signal import savgol_filter

                    deriv = np.diff(y) / np.diff(x)
                    i_max = np.argmax(np.abs(deriv))
                    if deriv[i_max] < 0:
                        deriv = -deriv
                        sign = -1
                    else:
                        sign = 1
                    self.summary[axis].plot(x[1:], deriv, pen="r")
                    if not self.plan.adaptive:
                        y = sign * savgol_filter(y, 5, 2, deriv=1, delta=x[1] - x[0])
                        self.summary[axis].plot(x[1:], y[1:], pen="b")


class FocusScanStarter(PlanStartDialog):
    experiment_type = "FocusScan"
    title = "Focus Scan"
    viewer = FocusScanView

    def setup_paras(self):
        tmp = [
            {"name": "Filename", "type": "str", "value": "temp_focus"},
            {"name": "Operator", "type": "str", "value": ""},
            {"name": "Shots", "type": "int", "max": 2000, "value": 100},
            {"name": "Scan x", "type": "bool", "value": True},
            {"name": "Scan y", "type": "bool", "value": True},
            {"name": "Start x", "type": "float", "value": 0, "step": 0.1},
            {"name": "End x", "type": "float", "value": 1, "step": 0.1},
            {"name": "Start y", "type": "float", "value": 0, "step": 0.1},
            {"name": "End y", "type": "float", "value": 1, "step": 0.1},
            {"name": "Scan z", "type": "bool", "value": True},
            {"name": "Start z", "type": "float", "value": 0, "step": 0.1},
            {"name": "End z", "type": "float", "value": 1, "step": 0.1},
            {"name": "Z step", "type": "float", "value": 0.3},
            {"name": "steps", "type": "float", "value": 0.02, "step": 0.01},
            {"name": "Power", "type": "bool", "value": True},
            {"name": "Adaptive", "type": "bool", "value": True},
            {"name": "Max rel. change", "type": "float", "value": 0.05, "step": 0.01},
            {"name": "Min step", "type": "float", "value": 0.01, "step": 0.01},
        ]

        self.candidate_cams = {c.cam.name: c for c in self.controller.cam_list}
        tmp.append(dict(name="Cam", type="list", limits=self.candidate_cams.keys()))
        self.p = pt.Parameter.create(name="Exp. Settings", type="group", children=tmp)
        params = [sample_parameters, self.p]
        self.paras = pt.Parameter.create(
            name="Focus Scan", type="group", children=params
        )
        # config.last_pump_probe = self.paras.saveState()

    def create_plan(self, controller: Controller):
        p = self.paras.child("Exp. Settings")
        s = self.paras.child("Sample")
        x_stepper = []
        y_stepper = []

        if p["Scan x"]:
            x_stepper = [p["Start x"], p["End x"], p["steps"]]
        if p["Scan y"]:
            y_stepper = [p["Start y"], p["End y"], p["steps"]]

        if p["Scan z"]:
            z_points = np.arange(p["Start z"], p["End z"] + 0.0001, p["Z step"])
        else:
            z_points = None

        self.save_defaults()
        if p["Power"]:
            power = getattr(controller, "power_meter", None)
        else:
            power = None
        fs = FocusScan(
            name=p["Filename"],
            cam=self.candidate_cams[p["Cam"]],
            meta=make_entry(p),
            shots=p["Shots"],
            x_parameters=x_stepper,
            y_parameters=y_stepper,
            adaptive=p["Adaptive"],
            max_rel_change=p["Max rel. change"],
            min_step=p["Min step"],
            z_points=z_points,
            fh=controller.sample_holder,
            power_meter=power,
        )
        return fs


if __name__ == "__main__":
    import sys

    sys._excepthook = sys.excepthook

    def exception_hook(exctype, value, traceback):
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)

    sys.excepthook = exception_hook

    app = QApplication([])
    con = Controller()
    timer = QTimer()
    timer.timeout.connect(con.loop)

    fs = FocusScan()
    con.plan = fs
    ppi = FocusScanViewViewer(fs)
    ppi.show()
    # formlayout.fedit(start_form)
    timer.start(50)
    try:
        app.exec_()
    except:
        print("fds")
