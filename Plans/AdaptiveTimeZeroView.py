import numpy as np
import pyqtgraph.parametertree as pt
from pyqtgraph import PlotWidget, PlotItem, mkPen, TextItem
from qtpy.QtWidgets import QWidget, QPushButton, QLabel, QMessageBox
from qtpy.QtCore import Qt
import attr
from ControlClasses import Controller
from QtHelpers import vlay, PlanStartDialog, make_default_cycle, col, hlay
from .AdaptiveTimeZeroPlan import AdaptiveTimeZeroPlan
from scipy.special import erfc
import lmfit


def folded_exp(t, t0, amp, tau, sigma):
    k = 1/tau
    t = t - t0
    y = amp*np.exp(k * (sigma * sigma * k / 4 - t))
    y *= 0.5 * erfc(-t / sigma + sigma * k / 2)
    return y


def fit_folded_exp(x, y):
    model = lmfit.Model(folded_exp, ['t'])
    model.set_param_hint('sigma', min=0.001)
    model.set_param_hint('tau', min=0.001)
    i = np.argmax(abs(y))
    try:
        fit_res = model.fit(y, t=x, amp=y[i], tau=10, sigma=0.1, t0=0, nan_policy='raise')
        return fit_res
    except ValueError:
        return False


@attr.s(auto_attribs=True)
class AdaptiveTZViewer(QWidget):
    plan: AdaptiveTimeZeroPlan
    plot_widget: PlotWidget = attr.ib(init=False)
    stop_button: QPushButton = attr.Factory(lambda: QPushButton("Stop"))

    def __attrs_post_init__(self):
        super(AdaptiveTZViewer, self).__init__()
        self.plot_widget = PlotWidget(labels={'bottom': "Time [ps]", 'left': self.plan.mode})
        color = make_default_cycle()
        self.line = self.plot_widget.plotItem.plot(pen=mkPen(color=next(color), width=2), symbol='t')
        self.fit_text = QLabel()
        self.fit_text.setAlignment(Qt.AlignHCenter)
        self.setLayout(vlay(self.plot_widget, hlay(self.fit_text, pre_stretch=1, post_stretch=1), self.stop_button))

        self.plan.sigStepDone.connect(lambda x: self.line.setData(*x))
        self.stop_button.clicked.connect(lambda: setattr(self.plan, 'is_running', False))
        self.plan.sigPlanFinished.connect(self.show_stop_options)

    def show_stop_options(self):
        self.stop_button.setDisabled(True)
        self.set_zero_btn = QPushButton('Set t0')
        self.set_zero_btn.setDisabled(True)
        save_button = QPushButton('Save')
        save_button.clicked.connect(lambda: QMessageBox.information(self, "Saved", "Saved data"))
        save_button.clicked.connect(self.plan.save)
        self.layout().addWidget(self.set_zero_btn)
        self.layout().addWidget(save_button)
        self.fit_data()

    def fit_data(self):
        x, y = self.plan.get_data()
        fit_res = fit_folded_exp(x, y)
        if fit_res and fit_res.success:
            xn = np.linspace(x.min(), x.max(), 300)
            yn = fit_res.eval(t=xn)
            self.plot_widget.plotItem.plot(xn, yn, pen=mkPen(color=col[1]))
            s = str(fit_res.params._repr_html_())
            self.fit_text.setText(s)
            self.adjustSize()
            self.set_zero_btn.setEnabled(True)
            t0 = fit_res.params['t0'].value
            self.set_zero_btn.clicked.connect(lambda: self.plan.set_zero_pos(t0))
        else:
            self.fit_text.setText("Fit failed")


class AdaptiveTZStarter(PlanStartDialog):
    experiment_type = 'AdaptiveTZFinder'
    title = "Adaptive Time-zero finder"
    viewer = AdaptiveTZViewer

    def setup_paras(self):
        params = [dict(name='Filename', type='str', value='temp_tz'),
                  dict(name='Max. Diff', type='float', value=3),
                  dict(name='Min. Diff', type='float', value=0.5),
                  dict(name='Start', type='float', value=-5),
                  dict(name='Stop', type='float', value=5),
                  dict(name='Initial Step', type='float', value=1),
                  dict(name='Min. Step', type='float', value=0.02),
                  dict(name='Mode', type='list', values=['mean', 'max']),
                  dict(name='Shots', type='int', value=100)
                  ]

        two_d = {'name': 'Exp. Settings', 'type': 'group', 'children': params}
        params = [two_d]
        self.paras = pt.Parameter.create(name='Adaptive TZ', type='group', children=params)

    def create_plan(self, controller: 'Controller'):
        p = self.paras.child('Exp. Settings')
        self.save_defaults()
        plan = AdaptiveTimeZeroPlan(
            cam=controller.cam,
            delay_line=controller.delay_line,
            max_diff=p["Max. Diff"],
            min_diff=p["Min. Diff"],
            name=p["Filename"],
            meta=self.paras.getValues(),
            start=p["Start"],
            stop=p["Stop"],
            current_step=p['Initial Step'],
            min_step=p['Min. Step'],
            mode=p['Mode'],
            shots=p['Shots']
        )
        plan.sigStepDone.connect(lambda x: controller.loop_finished.emit())
        return plan
