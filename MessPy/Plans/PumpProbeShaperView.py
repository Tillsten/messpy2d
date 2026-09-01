import numpy as np
import pyqtgraph.parametertree as pt
from PySide6.QtWidgets import QLabel, QWidget
from qtawesome import icon

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import ObserverPlot, PlanStartDialog, make_entry, vlay

from .PumpProbeShaper import PumpProbeShaperPlan


class PumpProbeShaperView(QWidget):
    def __init__(self, plan: PumpProbeShaperPlan, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan

        self.gvd_amp = ObserverPlot(
            obs=[lambda: self.plan.probe2.mean(1)],
            signal=plan.sigPointRead,
            x=plan.gvd_list,
        )

        self.gvd_sig = ObserverPlot()
        #    obs=[lambda: self.plan.signal[:, :, 0].mean(1), lambda: self.plan.signal[:, :, 2].mean(1)],
        #    signal=gvd_plan.sigPointRead,
        #    x=gvd_plan.gvd_list)

        self.info_label = QLabel("Info")
        self.setLayout(vlay(self.gvd_sig, self.gvd_amp, self.info_label))
        self.plan.sigPointRead.connect(self.update_label)
        self.setWindowTitle("GVD Scan")
        self.setWindowIcon(icon("fa5s.tired"))

    def update_label(self):
        p = self.plan
        s = f"Point {p.gvd_idx}/ {len(p.gvd_list)}"
        self.info_label.setText(s)


class PumpProbeShaperStarter(PlanStartDialog):
    experiment_type = "Pump Probe-Shaper"
    title = "Pump-Probe Shaper Scan"
    viewer = PumpProbeShaperView

    def setup_paras(self):
        tmp = [
            {"name": "Filename", "type": "str", "value": "temp_focus"},
            {"name": "Reps.", "type": "int", "value": 20, "min": 1},
            {
                "name": "Start Time",
                "type": "float",
                "value": -2,
                "step": 0.1,
                "unit": "ps",
            },
            {
                "name": "End Time",
                "type": "float",
                "value": 2,
                "step": 0.1,
                "unit": "ps",
            },
            {
                "name": "Step",
                "type": "float",
                "value": 0.04,
                "step": 0.01,
                "unit": "ps",
            },
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
        fs = GVDScan(
            aom=controller.shaper,
            meta=make_entry(self.paras),
            gvd=p["GVD"],
            tod=p["TOD"],
            fod=p["FOD"],
            name=p["Filename"],
            cam=controller.cam,
            gvd_list=gvd_list,
            scan_mode=p["Scan Mode"],
            waiting_time=p["Waiting time (s)"],
            shots=p["Shots"],
        )
        return fs
