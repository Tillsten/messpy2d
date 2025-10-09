import numpy as np
import pyqtgraph.parametertree as pt
import pyqtgraph.parametertree.parameterTypes as pTypes

from pyqtgraph import PlotWidget
from PySide6.QtWidgets import QWidget

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import ObserverPlot, PlanStartDialog, make_entry, vlay


from .ScanFoldingMirrors import ScanFoldingMirrors


class ScanFoldingMirrorView(QWidget):
    def __init__(self, scan_plan: ScanFoldingMirrors, *args, **kwargs):
        super(ScanFoldingMirrorView, self).__init__(*args, **kwargs)
        self.plan = scan_plan

        self.top_plot = PlotWidget()
        self.bot_plot = PlotWidget()
        self.bot_plot.plotItem.setLabel("bottom", "Angle 2 / °")
        self.top_plot.plotItem.setLabel("bottom", "Angle 1 / °")

        self.setLayout(vlay([self.top_plot, self.bot_plot]))
        self.plan.sigPointRead.connect(self.plot_data)

    def plot_data(self):
        data = self.plan.data
        if len(data) == 0:
            return
        angles1, angles2 = zip(*data.keys())
        signals = list(data.values())
        angles1 = np.array(angles1)
        angles2 = np.array(angles2)
        signals = np.array(signals)

        # The top plot shows the signal vs angle2.
        # For each angle1, we plot a line
        self.top_plot.clear()
        for a1 in np.unique(angles1):
            mask = angles1 == a1
            self.top_plot.plot(
                angles2[mask],
                signals[mask],
                pen=None,
                symbol="o",
                symbolSize=5,
                name=f"Angle1={a1:.2f}°",
            )
        self.top_plot.addLegend()
        self.top_plot.setTitle("Signal vs Angle 2 for different Angle 1")
        self.top_plot.setLabel("left", "Signal (a.u.)")

        # The bottom plot shows the signal vs angle1.
        # Only the maximum signal for each angle1 is plotted
        self.bot_plot.clear()
        max_signals = []
        for a1 in np.unique(angles1):
            mask = angles1 == a1
            max_signals.append((a1, signals[mask].max()))
        max_signals = np.array(max_signals)
        self.bot_plot.plot(
            max_signals[:, 0], max_signals[:, 1], pen=None, symbol="o", symbolSize=5
        )
        self.bot_plot.setTitle("Max Signal vs Angle 1")
        self.bot_plot.setLabel("left", "Max Signal (a.u.)")


class ScanFoldingMirrorsStarter(PlanStartDialog):
    experiment_type = "ScanFoldingMirrors"
    viewer = ScanFoldingMirrorView
    title = "Scan Folding Mirrors"

    def setup_paras(self):
        tmp = [
            {
                "name": "Shots",
                "type": "int",
                "max": 4000,
                "decimals": 5,
                "step": 50,
                "value": 10,
            },
            {"name": "Estimated angle", "type": "float", "value": 1.0},
            {"name": "Angle range", "type": "float", "value": 0.2},
            {"name": "Steps", "type": "int", "value": 10, "min": 1},
            {"name": "2nd Mirror range", "type": "float", "value": 0.2},
            {"name": "2nd Mirror steps", "type": "int", "value": 10, "min": 1},
        ]

        p = pt.Parameter(name="Exp. Settings", type="group", children=tmp)
        params = [p]
        self.paras = pt.Parameter.create(
            name="Scan Folding Mirrors", type="group", children=params
        )
        self.paras.getValues()
        self.save_defaults()

    def create_plan(self, controller: Controller):
        p = self.paras.child("Exp. Settings")
        scan = ScanFoldingMirrors(
            aom=controller.aom,
            cam=controller.cam.cam,
            estimated_best_angle=p["Estimated angle"],
            angle_range=p["Angle range"],
            steps=p["Steps"],
            second_mirror_range=p["2nd Mirror range"],
            second_mirror_steps=p["2nd Mirror steps"],
            shots=p["Shots"],
        )
        self.save_defaults()
        return scan
