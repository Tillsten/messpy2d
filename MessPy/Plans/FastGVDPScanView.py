import numpy as np
import pyqtgraph.parametertree as pt
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from qtawesome import icon

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import ObserverPlot, PlanStartDialog, vlay, make_entry
from .FastGVDScan import FastGVDScan

import lmfit


def gaussfit(x, y, offset=True):
    model = lmfit.models.GaussianModel() + lmfit.models.ConstantModel()
    params = model.make_params()
    if offset:
        params["c"].set(value=y.min(), vary=True)
    else:
        params["c"].set(value=0, vary=False)
    x_center = x[np.argmax(y)]
    params["center"].set(value=x_center)
    sigma = np.std(x) / 5
    height = y.max() - y.min()
    # convert height to amplitude taking sigma into account
    amplitude = height / (sigma * np.sqrt(2 * np.pi))
    params["amplitude"].set(value=amplitude)
    return model.fit(y, params, x=x)


class FastGVDScanView(QWidget):
    def __init__(self, gvd_plan: FastGVDScan, *args, **kwargs):
        super(FastGVDScanView, self).__init__(*args, **kwargs)
        self.plan = gvd_plan

        self.gvd_amp = ObserverPlot(
            obs=[lambda: self.plan.probe2.mean(1), lambda: self.plan.probe.mean(1)],
            signal=gvd_plan.sigPointRead,
            x=gvd_plan.gvd_list,
        )

        self.gvd_sig = ObserverPlot(
            obs=[
                lambda: self.plan.signal[:, :, 0].mean(1),
                lambda: self.plan.signal[:, :, 2].mean(1),
            ],
            signal=gvd_plan.sigPointRead,
            x=gvd_plan.gvd_list,
        )

        self.info_label = QLabel("Info")
        self.setLayout(vlay(self.gvd_sig, self.gvd_amp, self.info_label))
        self.plan.sigPointRead.connect(self.update_label)
        self.plan.sigPlanFinished.connect(self.analyze_lines)
        self.gvd_sig.plotItem.setLabels(left="Signal", bottom=gvd_plan.scan_mode)
        self.gvd_amp.plotItem.setLabels(left="Probe2 Mean", bottom=gvd_plan.scan_mode)
        self.setWindowTitle("GVD Scan")
        self.setWindowIcon(icon("fa5s.tired"))

    def update_label(self):
        p = self.plan
        s = f"Point {p.gvd_idx}/ {len(p.gvd_list)}"
        self.info_label.setText(s)

    def analyze_lines(self):
        x = self.plan.gvd_list
        y1 = self.plan.probe2.mean(1)
        y2 = self.plan.signal[:, :, 0].mean(1)
        y3 = self.plan.signal[:, :, 2].mean(1)
        y1_minpos = x[np.argmin(y1)]
        y2_maxpos = x[np.argmax(y2)]
        y3_maxpos = x[np.argmax(y3)]

        txt = f"Min Probe2: {y1_minpos:.2f}\nMax Signal1: {y2_maxpos:.2f}\nMax Signal2: {y3_maxpos:.2f}"

        # Try gaussfit with offset
        fit2 = gaussfit(x, y1)
        if fit2.success:
            self.gvd_sig.plot(x, fit2.best_fit, pen="g")
            txt += f"\nProbe2: {fit2.best_values['center']:.2f}"
        fit3 = gaussfit(x, y2)
        if fit3.success:
            self.gvd_sig.plot(x, fit3.best_fit, pen="r")
            txt += f"\nSignal1: {fit3.best_values['center']:.2f}"

        self.info_label.setText(txt)


class FastGVDScanStarter(PlanStartDialog):
    experiment_type = "FastGVDScan"
    title = "Fast GVD Scan"
    viewer = FastGVDScanView

    def setup_paras(self):
        tmp = [
            {"name": "Filename", "type": "str", "value": "temp_gvd"},
            {"name": "Reps", "type": "int", "max": 2000, "value": 20},
            {"name": "Start Val", "type": "float", "value": -300, "step": 1},
            {"name": "End Val", "type": "float", "value": -100, "step": 1},
            {"name": "Step", "type": "float", "value": 1, "step": 0.1},
            {
                "name": "Scan Mode",
                "type": "list",
                "limits": ["GVD", "TOD", "FOD"],
                "value": "GVD",
            },
            {"name": "GVD", "type": "float", "value": 0, "step": 1},
            {"name": "TOD", "type": "float", "value": 0, "step": 1},
            {"name": "FOD", "type": "float", "value": 0, "step": 1},
        ]
        self.p = pt.Parameter.create(name="Exp. Settings", type="group", children=tmp)
        params = [self.p]
        self.paras = pt.Parameter.create(
            name="Focus Scan", type="group", children=params
        )
        # config.last_pump_probe = self.paras.saveState()

    def create_plan(self, controller: Controller):
        p = self.paras.child("Exp. Settings")

        self.save_defaults()
        start = min(p["Start Val"], p["End Val"])
        end = max(p["Start Val"], p["End Val"])
        gvd_list = np.arange(start, end, p["Step"])
        fs = FastGVDScan(
            aom=controller.shaper,
            meta=make_entry(self.paras),
            gvd=p["GVD"],
            tod=p["TOD"],
            fod=p["FOD"],
            name=p["Filename"],
            cam=controller.cam,
            gvd_list=gvd_list,
            scan_mode=p["Scan Mode"],
            repeats=p["Reps"],
        )
        return fs
