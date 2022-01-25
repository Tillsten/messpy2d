import attr
import numpy as np
import pyqtgraph.parametertree as pt
from pyqtgraph import PlotWidget, ImageItem, PlotItem, colormap, GraphicsLayoutWidget, HistogramLUTItem, InfiniteLine, \
    mkPen, PlotDataItem
from qtpy.QtWidgets import QWidget, QLabel, QTabWidget
from qtpy.QtCore import Slot
from ControlClasses import Controller
from QtHelpers import vlay, PlanStartDialog, hlay, remove_nodes, make_entry
from Plans.PlanParameters import DelayParameter
from QtHelpers import vlay, PlanStartDialog, hlay
from .AOMTwoPlan import AOMTwoDPlan
from .PlanBase import sample_parameters
from typing import Callable
import qasync

class AOMTwoDViewer(GraphicsLayoutWidget):
    def __init__(self, plan: AOMTwoDPlan, parent=None):
        super().__init__(parent=parent)
        self.plan = plan
        self.pump_freqs = plan.pump_freqs
        self.probe_freq = plan.probe_freqs

        pw = self.addPlot()
        pw: PlotItem
        pw.setLabels(bottom='Probe Freq', left='Time')
        cmap = colormap.get("CET-D1")
        self.ifr_img = ImageItem()
        rect = (self.probe_freq.max(), 0, -self.probe_freq.ptp(), plan.max_t1)
        self.ifr_img.setImage(np.zeros((128, plan.t1.size)), rect=rect)
        pw.addItem(self.ifr_img)
        self.spec_image_view = pw
        self.ifr_img.mouseClickEvent = self.ifr_clicked
        hist = HistogramLUTItem()
        hist.setImageItem(self.ifr_img)
        hist.gradient.setColorMap(cmap)
        self.addItem(hist)
        self.ifr_lines: dict[InfiniteLine, PlotDataItem] = {}
        self.ifr_free_colors = list(range(9))
        self.addPlot: Callable[[], PlotItem]

        pw = self.addPlot()
        pw.setLabels(bottom='Probe Freq', left='Pump Freq')
        cmap = colormap.get("CET-D1")

        self.spec_img = ImageItem()
        rect = (self.probe_freq.max(), self.pump_freqs[-1], -self.probe_freq.ptp(),
                self.pump_freqs[0]-self.pump_freqs[-1])
        self.spec_img.setImage(np.zeros((128, plan.pump_freqs.size)), rect=rect)

        pw.addItem(self.spec_img)
        self.spec_line = InfiniteLine(pos=self.pump_freqs[self.pump_freqs.size//2], angle=0,
                                      bounds=(self.pump_freqs.min(), self.pump_freqs.max()),
                                      movable=True)
        pw.addItem(self.spec_line)
        hist = HistogramLUTItem()
        hist.setImageItem(self.spec_img)
        hist.gradient.setColorMap(cmap)

        self.addItem(hist)
        self.ci.nextRow()
        self.trans_plot = self.ci.addPlot(colspan=2)
        self.trans_plot.setLabels(bottom="Time", left='Signal')
        self.spec_plot = self.ci.addPlot(colspan=2)
        self.spec_plot.setLabels(bottom="Probe Freq", left='Signal')
        self.spec_cut_line = self.spec_plot.plot()
        self.spec_mean_line = self.spec_plot.plot()
        self.ci.nextRow()
        self.info_label = self.ci.addLabel("Hallo", colspan=4)
        
        self.update_plots()
        self.spec_line.sigPositionChanged.connect(self.update_spec_lines)
        self.plan.sigStepDone.connect(self.update_data)
        self.plan.sigStepDone.connect(self.update_plots)
        self.plan.sigStepDone.connect(self.update_label)
        self.time_str = ''
        self.plan.time_tracker.sigTimesUpdated.connect(self.set_time_str)

    @qasync.asyncSlot()
    async def update_data(self, al=True):
        if self.plan.last_2d is not None:
            self.ifr_img.setImage(self.plan.last_ir, autoLevels=al)
            self.spec_img.setImage(self.plan.last_2d[:, ::], autoLevels=al)

    def ifr_clicked(self, ev):
        x, y = ev.pos()
        if len(self.ifr_free_colors) == 0:
            return
        _int_color = self.ifr_free_colors.pop(0)
        line = self.spec_image_view.addLine(x=self.probe_freq[round(x)], movable=True,
                                            bounds=(self.probe_freq.min(), self.probe_freq.max()),
                                            pen=mkPen(_int_color, width=1))
        line._int_color = _int_color
        cur_line = 'Probe2'
        self.ifr_lines[line] = self.trans_plot.plot(self.plan.t1, self.plan.disp_arrays[cur_line][1][round(x), :],
                                                    pen=line.pen)

        def update(line: InfiniteLine):
            idx = np.argmin(abs(self.probe_freq - line.pos()[0]))
            self.ifr_lines[line].setData(self.plan.t1, self.plan.last_ir[round(idx), :])

        def delete(line: InfiniteLine, ev):
            ev.accept()
            trans_line = self.ifr_lines.pop(line)
            self.trans_plot.removeItem(trans_line)
            self.spec_image_view.removeItem(line)
            self.ifr_free_colors.append(line._int_color)

        line.sigClicked.connect(delete)
        line.sigPositionChanged.connect(update)

    def update_plots(self):
        if self.plan.last_2d is not None:
            self.spec_mean_line.setData(self.probe_freq, self.plan.last_2d.mean(1))
            for line in self.ifr_lines.keys():
                line.sigPositionChanged.emit(line)  # Causes an update

    def update_spec_lines(self, *args):
        idx = np.argmin(abs(self.pump_freqs - self.spec_line.pos()[1]))
        self.spec_cut_line.setData(self.probe_freq, self.plan.last_2d[:, idx])

    def set_time_str(self, s):
        self.time_str = s

    def update_label(self):
        p = self.plan
        s = f'''
            <h3>Current Experiment</h3>
            <big>
            <dl>
            <dt>Name:<dd>{p.name}
            <dt>Scan:<dd>{p.cur_scan} / {p.max_scan}
            <dt>Time-point:<dd>{p.t2_idx} / {p.t2.size}: {p.cur_t2: .2f} ps
            </dl>
            </big>
            '''
        s = s + self.time_str

        self.info_label.setText(s)



class AOMTwoDStarter(PlanStartDialog):
    title = "New 2D-experiment"
    viewer = AOMTwoDViewer
    experiment_type = '2D Time Domain'

    def setup_paras(self):
        has_rot = self.controller.rot_stage is not None
        has_shutter = self.controller.shutter is not None

        tmp = [{'name': 'Filename', 'type': 'str', 'value': 'temp'},
               {'name': 'Operator', 'type': 'str', 'value': 'Till'},
               {'name': 't2 (+)', 'suffix': 'ps', 'type': 'float', 'value': -4},
               {'name': 't2 (step)', 'suffix': 'ps', 'type': 'float', 'value': 0.1},
               {'name': 'Phase Cycles', 'type': 'list', 'values': [1, 2, 4]},
               {'name': 'Rot. Frame', 'suffix': 'cm-1', 'type': 'int', 'value': 2000},
               {'name': 'Mode', 'type': 'list', 'values': ['classic', 'bragg']},
               {'name': 'Repetitions', 'type': 'int', 'value': 1},
               DelayParameter()
               ]

        two_d = {'name': 'Exp. Settings', 'type': 'group', 'children': tmp}
        params = [sample_parameters, two_d]
        self.paras = pt.Parameter.create(name='Pump Probe', type='group', children=params)

    def create_plan(self, controller: Controller):
        p = self.paras.child('Exp. Settings')
        s = self.paras.child('Sample')
        t_list = p.child("Delay Times").generate_values()
        self.save_defaults()

        p = AOMTwoDPlan(
            name=p['Filename'],
            meta=self.paras.getValues(),
            meta=make_entry(self.paras),
            t2=np.asarray(t_list),
            controller=controller,
            max_t2=p['t2 (+)'],
            step_t2=p['t2 (step)'],
            rot_frame_freq=p['Rot. Frame'],
            shaper=controller.shaper,
            phase_frames=p['Phase Cycles'],
            mode=p['Mode'],
            repetitions=p['Repetitions']
        )
        return p


if __name__ == '__main__':
    from qtpy.QtWidgets import QApplication
    from ControlClasses import Controller

    app = QApplication([])
    p = AOMTwoDPlan(controller=Controller(), shaper=None, t3_list=[1, 2])
    w = AOMTwoDViewer(plan=p)
    w.show()
    app.exec_()
