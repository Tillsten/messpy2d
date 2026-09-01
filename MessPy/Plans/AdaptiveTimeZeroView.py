import attr
import lmfit
import numpy as np
import pyqtgraph.parametertree as pt
from pyqtgraph import PlotWidget, mkPen
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox, QPushButton, QWidget
from scipy.special import erfc

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import (
    PlanStartDialog,
    col,
    hlay,
    make_default_cycle,
    make_entry,
    vlay,
)

from .AdaptiveTimeZeroPlan import AdaptiveTimeZeroPlan


def folded_exp(t, t0, amp, tau, sigma, c=0):
    k = 1 / tau
    t = t - t0
    y = amp * np.exp(k * (sigma * sigma * k / 4 - t))
    y *= 0.5 * erfc(-t / sigma + sigma * k / 2)
    return y + c


def gaussian(t, t0, amp, sigma_g):
    return amp * np.exp(-((t - t0) ** 2) / (2 * sigma_g**2))


def fit_folded_exp(x, y, add_gaussian=False):
    model = lmfit.Model(folded_exp, ["t"])
    if add_gaussian:
        model += lmfit.Model(gaussian, ["t"])
        model.set_param_hint("amp", value=y.max() - y.min())
        model.set_param_hint("sigma_g", expr="sigma")
    model.set_param_hint("sigma", min=0.001)
    model.set_param_hint("tau", min=0.001)
    i = np.argmax(abs(y))
    try:
        fit_res = model.fit(
            y, t=x, amp=y[i], tau=10, c=0, sigma=0.1, t0=0, nan_policy="raise"
        )
        return fit_res
    except ValueError:
        return False


@attr.s(auto_attribs=True)
class AdaptiveTZViewer(QWidget):
    plan: AdaptiveTimeZeroPlan
    plot_widget: PlotWidget = attr.ib(init=False)
    stop_button: QPushButton = attr.Factory(lambda: QPushButton("Stop"))
    fit_model_combo: QComboBox = attr.Factory(lambda: QComboBox())

    def __attrs_post_init__(self):
        super().__init__()
        self.plot_widget = PlotWidget(
            labels={"bottom": "Time [ps]", "left": self.plan.mode}
        )
        color = make_default_cycle()
        self.line = self.plot_widget.plotItem.plot(
            pen=mkPen(color=next(color), width=2), symbol="t"
        )
        self.line2 = self.plot_widget.plotItem.plot(
            pen=mkPen(color=next(color), width=2), symbol="t"
        )
        self.fit_text = QLabel()
        self.fit_text.setAlignment(Qt.AlignHCenter)
        self.setLayout(
            vlay(
                self.plot_widget,
                hlay(self.fit_text, pre_stretch=1, post_stretch=1),
                self.stop_button,
            )
        )

        self.plan.sigStepDone.connect(self.update_line, Qt.ConnectionType.QueuedConnection)
        
        self.stop_button.clicked.connect(
            lambda: setattr(self.plan, "is_running", False)
        )
        self.plan.sigPlanFinished.connect(self.show_stop_options)

        self.fit_model_combo.addItems(["Folded Exp.", "Folded Exp. + Gaussian"])

    @Slot(object)
    def update_line(self, obj):
        x, y = obj
        self.line.setData(x, y)

    @Slot()
    def show_stop_options(self):
        self.stop_button.setDisabled(True)
        self.set_zero_btn = QPushButton("Set t0")
        self.set_zero_btn.setDisabled(True)
        save_button = QPushButton("Save")
        fname = self.plan.get_file_name()
        save_button.clicked.connect(
            lambda: QMessageBox.information(
                self, "Saved", "Saved data at %s" % str(fname)
            )
        )
        save_button.clicked.connect(self.plan.save)
        self.layout().addWidget(self.set_zero_btn)
        self.layout().addWidget(save_button)
        self.fit_data()

    @Slot()
    def fit_data(self):
        x, y = self.plan.get_data()
        if self.fit_model_combo.currentText() == "Folded Exp.":
            fit_res = fit_folded_exp(x, y)
        elif self.fit_model_combo.currentText() == "Folded Exp. + Gaussian":
            fit_res = fit_folded_exp(x, y, add_gaussian=True)

        if fit_res and fit_res.success:
            xn = np.linspace(x.min(), x.max(), 300)
            yn = fit_res.eval(t=xn)
            self.plot_widget.plotItem.plot(xn, yn, pen=mkPen(color=col[1]))
            s = str(fit_res.params._repr_html_())
            self.fit_text.setText(s)
            self.adjustSize()
            self.set_zero_btn.setEnabled(True)
            t0 = fit_res.params["t0"].value
            self.set_zero_btn.clicked.connect(lambda: self.plan.set_zero_pos(t0))
            self.set_zero_btn.clicked.connect(
                lambda: QMessageBox.information(
                    self, "New t0", "Set Time-Zero to %.2f" % t0
                )
            )
            self.set_zero_btn.clicked.connect(lambda: self.set_zero_btn.setDisabled(True))
        else:
            self.fit_text.setText("Fit failed")


class AdaptiveTZStarter(PlanStartDialog):
    experiment_type = "AdaptiveTZFinder"
    title = "Adaptive Time-zero finder"
    viewer = AdaptiveTZViewer

    def setup_paras(self):
        params = [
            dict(name="Filename", type="str", value="temp_tz"),
            dict(name="Max. Diff", type="float", value=3),            
            dict(name="Start", type="float", value=-5),
            dict(name="Stop", type="float", value=5),
            dict(name="Initial Step", type="float", value=1),
            dict(name="Min. Step", type="float", value=0.02),
            dict(name="Mode", type="list", limits=["mean", "max"]),
            dict(name="Shots", type="int", value=100),
        ]

        two_d = {"name": "Exp. Settings", "type": "group", "children": params}
        params = [two_d]
        self.paras = pt.Parameter.create(
            name="Adaptive TZ", type="group", children=params
        )

    def create_plan(self, controller: "Controller"):
        p = self.paras.child("Exp. Settings")
        self.save_defaults()
        plan = AdaptiveTimeZeroPlan(
            cam=controller.cam,
            delay_line=controller.delay_line,
            max_diff=p["Max. Diff"],            
            name=p["Filename"],
            meta=make_entry(self.paras),
            start=p["Start"],
            stop=p["Stop"],
            current_step=p["Initial Step"],
            min_step=p["Min. Step"],
            mode=p["Mode"],
            shots=p["Shots"],
        )
        plan.sigStepDone.connect(lambda x: controller.loop_finished.emit())
        return plan
