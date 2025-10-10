import os
from collections import defaultdict
from typing import TYPE_CHECKING, List

import attr
import numpy as np
import pyqtgraph as pg
from loguru import logger
from pyqtgraph.parametertree import Parameter, ParameterTree
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from MessPy.Config import config
from MessPy.ControlClasses import Cam, Controller
from MessPy.Plans.PumpProbe import PumpProbeData, PumpProbePlan
from MessPy.QtHelpers import ObserverPlot, PlanStartDialog, make_entry, vlay

from .PlanBase import sample_parameters
from .PlanParameters import DelayParameter


class LineLabel(QLabel):
    def __init__(self, line, index: int, parent=None):
        super(LineLabel, self).__init__(parent=parent)
        assert isinstance(line, pg.InfiniteLine)
        line.sigPositionChanged.connect(self.update_label)
        self.line = line
        self.wl_idx = index
        self.color = line.pen.color().name()
        self.setAlignment(Qt.AlignHCenter)
        self.update_label()

    def update_label(self, ev=None):
        x = self.line.pos().x()
        self.setText(
            '<font size=15 style="bold" color="%s">%d: %.1f</font>'
            % (self.color, self.wl_idx, x)
        )


@attr.s
class IndicatorLine:
    pos: float = attr.ib()
    line: pg.InfiniteLine = attr.ib()
    entry_label: LineLabel = attr.ib()
    wl: np.ndarray = attr.ib()
    wl_idx: int = attr.ib()
    trans_line: pg.PlotCurveItem = attr.ib()
    hist_trans_line: pg.PlotCurveItem = attr.ib()
    channel: int = attr.ib(0)

    def __attrs_post_init__(self):
        self.line.sigPositionChanged.connect(self.update_pos)
        self.update_pos()

    def update_pos(self):
        self.pos = self.line.pos().x()
        self.channel = np.argmin(abs(self.pos - self.wl[self.wl_idx, :]))


class PumpProbeViewer(QTabWidget):
    def __init__(self, pp_plan: PumpProbePlan, parent=None):
        super(PumpProbeViewer, self).__init__(parent=parent)
        for ppd in pp_plan.cam_data:
            self.addTab(
                PumpProbeDataViewer(ppd, pp_plan, parent=self), ppd.cam.cam.name
            )


class PumpProbeDataViewer(QWidget):
    def __init__(self, pp_plan: PumpProbeData, pp: PumpProbePlan, parent=None):
        super(PumpProbeDataViewer, self).__init__(parent=parent)
        self.pp = pp
        self.pp_plan = pp_plan
        self._layout = QHBoxLayout(self)

        self.info_label = QLabel(self)
        self.info_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.update_info()

        lw = QVBoxLayout()
        vlay = QVBoxLayout()

        self.signal_channel = 0

        self.signal_ch_selector = QSpinBox()
        self.signal_ch_selector.setMinimum(0)
        self.signal_ch_selector.setMaximum(self.pp_plan.cam.sig_lines - 1)
        self.signal_ch_selector.valueChanged.connect(lambda x: self.update_trans())

        self.do_show_cur = QCheckBox("Current Scan", self)
        self.do_show_cur.setChecked(True)
        self.do_show_cur.stateChanged.connect(self.hide_current_lines)
        self.do_show_mean = QCheckBox("Mean of all scans", self)
        self.do_show_mean.setChecked(True)
        self.do_show_mean.stateChanged.connect(self.hide_history_lines)
        self.use_wavenumbers = QCheckBox("Use Wavenumbers", self)
        self.use_wavenumbers.stateChanged.connect(self.update_indicator_line_pos)

        vlay.addWidget(self.info_label)
        vlay.addWidget(self.signal_ch_selector)
        vlay.addWidget(self.do_show_cur)
        vlay.addWidget(self.do_show_mean)
        vlay.addWidget(self.use_wavenumbers)

        self.line_area = QVBoxLayout(self)
        vlay.addLayout(self.line_area)
        vlay.addStretch(1)
        self._layout.addLayout(vlay)
        self._layout.addLayout(lw)

        self.sig_plot = ObserverPlot([], pp_plan.sigStepDone, x=self.get_x)
        self.last_signal = np.zeros_like(self.get_x())
        self.mean_signal = np.zeros_like(self.last_signal)
        self.sig_plot.add_observed((self, "last_signal"))
        self.sig_plot.add_observed((self, "mean_signal"))
        self.sig_plot.click_func = self.handle_sig_click

        self.trans_plot = ObserverPlot([], pp_plan.sigStepDone, aa=True)

        lw.addWidget(self.sig_plot)
        lw.addWidget(self.trans_plot)

        self.inf_lines: List[List[IndicatorLine]] = [list() for i in pp_plan.cwl]

        for i in [self.update_info, self.update_trans]:
            self.pp_plan.sigStepDone.connect(i)
        pp_plan.sigWavelengthChanged.connect(self.handle_wl_change)

    def handle_sig_click(self, coords):
        x = coords.x()
        c = next(self.sig_plot.color_cycle)
        l = self.sig_plot.plotItem.addLine(x=x, pen=pg.mkPen(c, width=6))
        l.setMovable(True)
        lbl = LineLabel(l, self.pp_plan.wl_idx, self)
        self.line_area.addWidget(lbl)

        tl = self.trans_plot.plot(pen=pg.mkPen(c, width=2))
        tlh = self.trans_plot.plot(pen=pg.mkPen(c, width=4))

        il = IndicatorLine(
            wl_idx=self.pp_plan.wl_idx,
            wl=self.pp_plan.wavelengths,
            pos=x,
            line=l,
            trans_line=tl,
            hist_trans_line=tlh,
            entry_label=lbl,
        )

        self.inf_lines[self.pp_plan.wl_idx].append(il)
        l.sigPositionChanged.connect(self.update_trans)

        def remove_line(ev):
            lbl.deleteLater()
            self.sig_plot.plotItem.removeItem(l)
            self.trans_plot.plotItem.removeItem(tl)
            self.trans_plot.plotItem.removeItem(tlh)
            self.inf_lines[il.wl_idx].remove(il)

        lbl.mouseReleaseEvent = remove_line

    @Slot()
    def update_info(self):
        p = self.pp
        s = self.pp_plan
        if p.rot_stage_angles:
            rot_stage_pos = f"<dt>t pos:<dd>{s.t_idx + 1}/{len(s.t_list)}"
        else:
            rot_stage_pos = ""

        s = f"""
        <h3>Current Experiment</h3>
        <big>
        <dl>
        <dt>Name:<dd>{p.name}
        <dt>Shots:<dd>{p.shots}
        <dt>Scan:<dd>{s.scan}
        <dt>WL pos:<dd>{s.wl_idx + 1}/{len(s.cwl)}
        {rot_stage_pos}
        <dt>T pos:<dd>{s.t_idx}/{len(s.t_list)}
        <dt>Time per scan<dd>{p.time_per_scan}
        </dl>
        </big>
        """
        self.info_label.setText(s)

    def handle_wl_change(self):
        last_idx = self.pp_plan.wl_idx - 1

        for i in self.inf_lines[last_idx]:
            self.trans_plot.removeItem(i.trans_line)
            i.line.hide()
        for i in self.inf_lines[self.pp_plan.wl_idx]:
            self.trans_plot.addItem(i.trans_line)

            i.line.show()

    def hide_history_lines(self, i):
        all_lines = []
        for i in range(len(self.pp_plan.cwl)):
            all_lines += self.inf_lines[i]
        chk = self.do_show_mean.checkState()
        if not chk:
            for i in all_lines:
                self.trans_plot.removeItem(i.hist_trans_line)
        else:
            for i in all_lines:
                self.trans_plot.addItem(i.hist_trans_line)

    def hide_current_lines(self, i):
        all_lines = []
        for i in range(len(self.pp_plan.cwl)):
            all_lines += self.inf_lines[i]
        chk = self.do_show_cur.checkState()
        if not chk:
            for i in all_lines:
                self.trans_plot.removeItem(i.trans_line)
        else:
            for i in all_lines:
                self.trans_plot.addItem(i.trans_line)
            self.handle_wl_change()

    def update_spec(self):
        pass

    @Slot()
    def update_trans(self):
        pp = self.pp_plan
        if pp.t_idx == 0:
            return
        sig_ch = self.signal_ch_selector.value()
        self.last_signal = pp.last_signal[sig_ch, :]
        if pp.mean_signal is not None:
            self.mean_signal = pp.mean_signal[sig_ch, :]
        if self.do_show_cur.checkState():
            for i in self.inf_lines[pp.wl_idx]:
                i.trans_line.setData(
                    x=pp.t_list[: pp.t_idx],
                    y=pp.current_scan[pp.wl_idx, : pp.t_idx, sig_ch, i.channel],
                )

        if pp.completed_scans is not None and self.do_show_mean.checkState():
            for j in self.inf_lines:
                for i in j:
                    if i.hist_trans_line not in self.trans_plot.plotItem.dataItems:
                        continue
                    ym = np.nanmean(
                        pp.completed_scans[:, i.wl_idx, :, sig_ch, i.channel], 0
                    )
                    i.hist_trans_line.setData(x=pp.t_list, y=ym)

    def get_x(self):
        wl = self.pp_plan.wavelengths[self.pp_plan.wl_idx]
        if self.use_wavenumbers.isChecked():
            return 1e7 / wl
        else:
            return wl

    @Slot()
    def update_indicator_line_pos(self):
        for lsts in self.inf_lines:
            for l in lsts:
                l.wl = 1e7 / l.wl
                l.pos = 1e7 / l.pos
                l.line.setPos(l.pos)
                l.update_pos()

    def closeEvent(self, a0) -> None:
        self.pp_plan.sigWavelengthChanged.disconnect(self.handle_wl_change)
        super().closeEvent(a0)


class PumpProbeStarter(PlanStartDialog):
    title = "New Pump-probe Experiment"
    viewer = PumpProbeViewer
    experiment_type = "Pump-Probe"

    def setup_paras(self):
        has_rot = self.controller.rot_stage is not None
        has_shutter = self.controller.shutter is not None

        tmp = [
            {"name": "Filename", "type": "str", "value": "temp"},
            {"name": "Operator", "type": "str", "value": ""},
            {
                "name": "Shots",
                "type": "int",
                "min": 10,
                "max": 4000,
                "decimals": 5,
                "step": 500,
                "value": 100,
            },
            DelayParameter(),
            dict(
                name="Use Shutter",
                type="bool",
                value=True,
                enabled=has_shutter,
                visible=has_shutter,
            ),
            dict(
                name="Use Rotation Stage",
                type="bool",
                value=has_rot,
                enabled=has_rot,
                visible=has_rot,
            ),
            dict(
                name="Angles in deg.",
                type="str",
                value="0, 45",
                enabled=has_rot,
                visible=has_rot,
            ),
            dict(name="Save Full Data", type="bool", value=False),
        ]

        for c in self.controller.cam_list:
            if c.cam.spectrograph:
                name = c.cam.name
                tmp.append(dict(name=f"{name} center wls", type="str", value="0"))

        if len(self.controller.shutter) > 0 and False:
            # names = {self.controller.shutter}
            tmp.append(
                dict(
                    name="Pump Shutter",
                    type="list",
                    values=self.controller.shutter,
                    value=self.controller.shutter[0],
                )
            )

        two_d = {"name": "Exp. Settings", "type": "group", "children": tmp}

        params = [sample_parameters, two_d]
        self.paras = Parameter.create(name="Pump Probe", type="group", children=params)
        config.last_pump_probe = self.paras.saveState()

    def create_plan(self, controller: Controller):
        p = self.paras.child("Exp. Settings")
        s = self.paras.child("Sample")

        t_list = p.child("Delay Times").generate_values()

        if p["Use Rotation Stage"] and self.controller.rot_stage:
            s = p["Angles in deg."].split(",")
            angles = list(map(float, s))
        else:
            angles = None

        cwls = []
        for c in self.controller.cam_list:
            if c.cam.spectrograph:
                name = c.name
                l = p[f"{name} center wls"].split(",")
                try:
                    assert len(l) > 0                    
                    cam_cwls = []
                    for s in l:
                        if s[-1] == "c":
                            cam_cwls.append(1e7 / float(s[:-1]))
                        else:
                            cam_cwls.append(float(s))
                except:
                    raise ValueError("Parsing of cennter wls failed")
                cwls.append(cam_cwls)
            else:
                cwls.append([0.0])

        self.save_defaults()
        if "Pump Shutter" in p:
            p_shutter = p["Pump Shutter"]
        else:
            p_shutter = None
        p = PumpProbePlan(
            name=p["Filename"],
            meta=make_entry(self.paras),
            t_list=np.asarray(t_list),
            shots=p["Shots"],
            controller=controller,
            center_wl_list=cwls,
            pump_shutter=p_shutter,
            use_rot_stage=p["Use Rotation Stage"],
            rot_stage_angles=angles,
            save_full_data=p["Save Full Data"],
        )
        return p


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

    pp = PumpProbePlan(name="BlaBlub", controller=con)
    con.plan = pp
    pp.t_list = np.arange(-2, 2, 0.1)
    pp.center_wl_list = [300]
    ppi = PumpProbeViewer(pp)
    ppi.show()
    # formlayout.fedit(start_form)
    timer.start(50)
    try:
        app.exec_()
    except:
        print("fds")
