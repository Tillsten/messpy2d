import attr
import numpy as np
import pyqtgraph.parametertree as pt
from pyqtgraph import (
    PlotWidget,
    ImageItem,
    PlotItem,
    colormap,
    GraphicsLayoutWidget,
    HistogramLUTItem,
    InfiniteLine,
    mkPen,
    PlotDataItem,
)
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QCheckBox,
    QRadioButton,
)
from PySide6.QtCore import Slot
from ..ControlClasses import Controller
from ..QtHelpers import vlay, PlanStartDialog, hlay, remove_nodes, make_entry, col
from .PlanParameters import DelayParameter
from ..QtHelpers import vlay, PlanStartDialog, hlay
from .AOMTwoPlan import AOMTwoDPlan
from .PlanBase import sample_parameters
from ..Instruments.signal_processing import cm2THz, THz2cm, Spectrum


@attr.define(auto_attribs=True, weakref_slot=False)
class TwoDMap(GraphicsLayoutWidget):
    probe_wn: np.ndarray = attr.field()
    pump_wn: np.ndarray = attr.field()
    spec2d: PlotItem = attr.field(factory=PlotItem)
    spec2d_item: ImageItem = attr.field(factory=ImageItem)
    spec_selector_line: InfiniteLine = attr.field(
        factory=lambda: InfiniteLine(angle=0, movable=True)
    )
    spec_plot: PlotItem = attr.field(factory=PlotItem)
    cur_spec: PlotDataItem = attr.field(factory=PlotDataItem)
    mean_spec: PlotDataItem = attr.field(factory=PlotDataItem)

    def __attr_post_init__(self):
        super().__init__()
        self.addItem(self.spec2d)
        self.spec2d.addItem(self.spec2d_item)
        self.spec2d.addItem(self.spec_selector_line)
        self.nextRow()
        self.addItem(self.spec_plot)
        self.spec_plot.addItem(self.cur_spec)
        self.spec_plot.addItem(self.mean_spec)

    @Slot(object)
    def update_image(self, image):
        rect = (
            self.probe_wn.max(),
            self.pump_wn[-1],
            -np.ptp(self.probe_wn),
            self.pump_wn[0] - self.pump_wn[-1],
        )
        self.spec2d_item.setImage(image, rect=rect)
        self.mean_spec.setData(self.probe_wn, np.mean(image, axis=0))


class AOMTwoDViewer(QWidget):
    def __init__(self, plan: AOMTwoDPlan, parent=None):
        super().__init__(parent=parent)
        self.plan = plan
        self.pump_freqs = plan.pump_freqs
        self.probe_freq = plan.probe_freqs

        gl = GraphicsLayoutWidget(self)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(gl)

        pw: PlotItem = gl.addPlot()
        pw.setLabels(bottom="Probe Freq", left="Pump Freq")
        cmap = colormap.get("CET-D1")
        pw.setAspectLocked(lock=True, ratio=1)

        self.spec_img = ImageItem()
        rect = (
            self.probe_freq.max(),
            self.pump_freqs[-1],
            -np.ptp(self.probe_freq),
            self.pump_freqs[0] - self.pump_freqs[-1],
        )
        self.spec_img.setImage(np.zeros((128, plan.pump_freqs.size)), rect=rect)

        pw.addItem(self.spec_img)
        self.spec_line = InfiniteLine(
            pos=self.pump_freqs[self.pump_freqs.size // 2],
            angle=0,
            bounds=(self.pump_freqs.min(), self.pump_freqs.max()),
            movable=True,
        )
        pw.addItem(self.spec_line)
        hist = HistogramLUTItem()
        hist.setImageItem(self.spec_img)
        hist.gradient.setColorMap(cmap)

        gl.addItem(hist)
        gl.ci.nextRow()
        # self.trans_plot = self.ci.addPlot(colspan=2)
        # self.trans_plot.setLabels(bottom="Time", left='Signal')
        self.spec_plot = gl.ci.addPlot(colspan=2)
        self.spec_plot.setLabels(bottom="Probe Freq", left="Signal")
        self.spec_cut_line = self.spec_plot.plot(pen="b")
        self.spec_mean_line = self.spec_plot.plot(pen="r")

        self.diag_plot = gl.ci.addPlot()
        names = ["Probe1", "Probe2", "Ref"]
        self.diag_lines = {}
        for i in range(3):
            self.diag_lines[names[i]] = self.diag_plot.plot(
                pen=mkPen(color=col[i], width=3)
            )

        gl.ci.nextRow()
        self.info_label = gl.ci.addLabel("Hallo", colspan=4)

        self.update_plots()
        self.spec_line.sigPositionChanged.connect(self.update_spec_lines)
        self.plan.sigStepDone.connect(self.update_data)
        self.plan.sigStepDone.connect(self.update_plots)
        self.plan.sigStepDone.connect(self.update_label)
        self.plan.sigNewSpectra.connect(self.update_diag_plots)
        self.time_str = ""
        self.plan.time_tracker.sigTimesUpdated.connect(self.set_time_str)
        self.pr_1_pb = QRadioButton("Probe1")
        self.pr_2_pb = QRadioButton("Probe2")
        self.cb_auto_levels = QCheckBox("Auto Levels")
        for pb in (self.pr_1_pb, self.pr_2_pb):
            pb.toggled.connect(self.update_plots)
            pb.toggled.connect(self.update_data)
        self.pr_1_pb.setChecked(True)
        self.layout().addWidget(self.pr_1_pb)
        self.layout().addWidget(self.pr_2_pb)
        self.layout().addWidget(self.cb_auto_levels)

    @property
    def pr_idx(self):
        if self.pr_1_pb.isChecked():
            return 0
        else:
            return 1

    @Slot()
    def update_data(self, al=True):
        if self.pr_1_pb.isChecked():
            i = 0
        else:
            i = 1
        if self.plan.last_2d is not None:
            al = self.cb_auto_levels.isChecked()
            self.spec_img.setImage(self.plan.last_2d[i][::, ::-1], autoLevels=True)

    @Slot()
    def update_plots(self):
        if self.plan.last_2d is not None:
            self.spec_mean_line.setData(
                self.probe_freq, self.plan.last_2d[self.pr_idx].mean(1)
            )

    @Slot(dict)
    def update_diag_plots(self, spectra: dict[str, Spectrum]):
        for i, (name, spec) in enumerate(spectra.items()):
            if name == 'back_line':
                continue
            self.diag_lines[name].setData(spec.mean)

    @Slot()
    def update_spec_lines(self, *args):
        idx = np.argmin(abs(self.pump_freqs - self.spec_line.pos()[1]))
        if self.plan.last_2d is not None:
            self.spec_cut_line.setData(
                self.probe_freq, self.plan.last_2d[self.pr_idx][:, idx]
            )

    def set_time_str(self, s):
        self.time_str = s

    @Slot()
    def update_label(self):
        p = self.plan
        s = f"""
            <h3>Current Experiment</h3>
            <big>
            <dl>
            <dt>Name:<dd>{p.name}
            <dt>Scan:<dd>{p.cur_scan} / {p.max_scan}
            <dt>Time-point:<dd>{p.t2_idx} / {p.t2.size}: {p.cur_t2: .2f} ps
            </dl>
            </big>
            """
        s = s + self.time_str
        self.info_label.setText(s)


class AOMTwoDStarter(PlanStartDialog):
    title = "New 2D-experiment"
    viewer = AOMTwoDViewer
    experiment_type = "2D Time Domain"

    def setup_paras(self):
        tmp = [
            {"name": "Filename", "type": "str", "value": "temp"},
            {"name": "Operator", "type": "str", "value": "Till"},
            {"name": "t1 (+)", "suffix": "ps", "type": "float", "value": -4},
            {"name": "t1 (step)", "suffix": "ps", "type": "float", "value": 0.1},
            {"name": "Phase Cycles", "type": "list", "limits": [1, 2, 4], "value": 4},
            {"name": "Rot. Frame", "suffix": "cm-1", "type": "int", "value": 2000},
            {"name": "Rot. Frame Fixed", "suffix": "cm-1", "type": "int", "value": 0},
            dict(name="Pump Axis", type="str", readonly=True),
            {"name": "Mode", "type": "list", "limits": ["classic", "bragg"]},
            {"name": "AOM Amp.", "type": "float", "value": 0.3, "min": 0, "max": 0.6},
            {"name": "Repetitions", "type": "int", "value": 1},
            DelayParameter(),
            {"name": "Save Frames", "type": "bool", "value": False},
            {"name": "Save Ref. Frames", "type": "bool", "value": False},
        ]

        two_d = {"name": "Exp. Settings", "type": "group", "children": tmp}
        params = [sample_parameters, two_d]
        self.paras = pt.Parameter.create(
            name="Pump Probe", type="group", children=params
        )
        self.paras.child("Exp. Settings").sigTreeStateChanged.connect(
            self.update_pump_axis
        )

    def update_pump_axis(self, *args):
        try:
            ex = self.paras.child("Exp. Settings")
            t1 = np.arange(0, ex["t1 (+)"], ex["t1 (step)"])
            THz = np.fft.rfftfreq(t1.size * 2, d=t1[1] - t1[0])
            freqs = THz2cm(THz) + ex["Rot. Frame"]
            ex.child("Pump Axis").setValue(
                f"{freqs.min():.2f} - {freqs.max():.2f} cm-1 step {freqs[1]-freqs[0]:.2f} cm-1"
            )
        except (ValueError, IndexError):
            pass

    def create_plan(self, controller: Controller) -> AOMTwoDPlan:
        p = self.paras.child("Exp. Settings")
        s = self.paras.child("Sample")
        t_list = p.child("Delay Times").generate_values()
        self.save_defaults()

        p = AOMTwoDPlan(
            name=p["Filename"],
            meta=make_entry(self.paras),
            t2=np.asarray(t_list),
            controller=controller,
            max_t1=p["t1 (+)"],
            step_t1=p["t1 (step)"],
            rot_frame_freq=p["Rot. Frame"],
            rot_frame2_freq=p["Rot. Frame Fixed"],
            shaper=controller.shaper,
            aom_amplitude=p["AOM Amp."],
            phase_frames=p["Phase Cycles"],
            mode=p["Mode"],
            repetitions=p["Repetitions"],
            save_frames_enabled=p["Save Frames"],
            save_ref=p["Save Ref. Frames"] and p["Save Frames"],
        )
        return p


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from ControlClasses import Controller

    app = QApplication([])
    p = AOMTwoDPlan(controller=Controller(), shaper=None, t3_list=[1, 2])
    w = AOMTwoDViewer(plan=p)
    w.show()
    app.exec_()
