import attr
import pyqtgraph.parametertree as pt
from pyqtgraph import PlotWidget, ImageItem
from qtpy.QtWidgets import QWidget
import numpy as np
from ControlClasses import Controller
from QtHelpers import vlay, PlanStartDialog, hlay
from .common_meta import sample_parameters
from .AOMTwoPlan import AOMTwoDPlan

@attr.s(auto_attribs=True)
class AOMTwoDViewer(QWidget):
    plan: AOMTwoDPlan
    plot: PlotWidget = attr.ib(init=False)
    plot2: PlotWidget = attr.ib(init=False)
    plot3: PlotWidget = attr.ib(init=False)
    data_image: ImageItem = attr.ib(init=False)

    def __attrs_post_init__(self):
        super(AOMTwoDViewer, self).__init__()
        self.plan.sigStepDone.connect(self.update_image)
        self.plot = PlotWidget()
        self.plot2 = PlotWidget()
        self.plot3 = PlotWidget()
        self.plot4 = PlotWidget()
        self.data_image = ImageItem()
        self.spec_image = ImageItem()
        self.plot3.addItem(self.spec_image)
        self.plot3.plotItem.setTitle("2D Spectrum")
        self.plot.addItem(self.data_image)
        self.plot.plotItem.setTitle("Inferogram")
        self.setLayout(vlay(hlay(self.plot, self.plot3), hlay(self.plot2, self.plot4)))
        self.l1 = self.plot2.plotItem.plot([1,2,3])
        self.l3 = self.plot4.plotItem.plot([1, 2, 3])

    def update_image(self):
        self.data_image.setImage(self.plan.last_ir)
        self.spec_image.setImage(self.plan.last_2d[:, :])
        #self.plot2.clear()
        #self.plot2.plot(self.plan.last_ir[64, :])
        #self.plot2.plot(self.plan.last_ir[0, :])
        #self.plot2.plot(self.plan.last_ir[-1, :])
        self.plot4.clear()
        self.plot4.plot(self.plan.last_freq[:], self.plan.last_2d[64, :])
        self.plot4.plot(self.plan.last_freq[:], self.plan.last_2d[0, :])
        self.plot4.plot(self.plan.last_freq[:], self.plan.last_2d[-1, :])
        self.plot4.plot(self.plan.last_freq[:], self.plan.last_2d.sum(0))
        #self.l3.setData(self.plan.last_ir[:, 50])


class AOMTwoDStarter(PlanStartDialog):
    title = "New 2D-experiment"
    viewer = AOMTwoDViewer
    experiment_type = '2D Time Domain'

    def setup_paras(self):
        has_rot = self.controller.rot_stage is not None
        has_shutter = self.controller.shutter is not None

        tmp = [{'name': 'Filename', 'type': 'str', 'value': 'temp'},
               {'name': 'Operator', 'type': 'str', 'value': 'Till'},
               {'name': 't2 (+)', 'suffix': 'ps', 'type': 'float', 'value': 4},
               {'name': 't2 (step)', 'suffix': 'ps', 'type': 'float', 'value': 0.1},
               {'name': 'Rot. Frame', 'suffix': 'cm-1', 'type': 'float', 'value': 2000},
               {'name': 'Linear Range (-)', 'suffix': 'ps', 'type': 'float', 'value': 0},
               {'name': 'Linear Range (+)', 'suffix': 'ps', 'type': 'float', 'value': 1},
               {'name': 'Linear Range (step)', 'suffix': 'ps', 'type': 'float', 'min': 0.2},
               {'name': 'Logarithmic Scan', 'type': 'bool'},
               {'name': 'Logarithmic End', 'type': 'float', 'suffix': 'ps',
                'min': 0.},
               {'name': 'Logarithmic Points', 'type': 'int', 'min': 0},
               dict(name="Add pre-zero times", type='bool', value=False),
               dict(name="Num pre-zero points", type='int', value=10, min=0, max=20),
               dict(name="Pre-Zero pos", type='float', value=-60., suffix='ps'),
               #dict(name='Use Shutter', type='bool', value=True, enabled=has_shutter, visible=has_shutter),
               #dict(name='Use Rotation Stage', type='bool', value=True, enabled=has_rot, visible=has_rot),
               #dict(name='Angles in deg.', type='str', value='0, 45', enabled=has_rot, visible=has_rot),
               ]

        #for c in self.controller.cam_list:
        #    if c.cam.changeable_wavelength:
        #        name = c.cam.name
        #        tmp.append(dict(name=f'{name} center wls', type='str', value='0'))

        two_d = {'name': 'Exp. Settings', 'type': 'group', 'children': tmp}

        params = [sample_parameters, two_d]
        self.paras = pt.Parameter.create(name='Pump Probe', type='group', children=params)

    def create_plan(self, controller: Controller):
        p = self.paras.child('Exp. Settings')
        s = self.paras.child('Sample')
        t_list = np.arange(p['Linear Range (-)'],
                           p['Linear Range (+)'],
                           p['Linear Range (step)']).tolist()
        if p['Logarithmic Scan']:
            t_list += (np.geomspace(p['Linear Range (+)'], p['Logarithmic End'], p['Logarithmic Points']).tolist())

        if p['Add pre-zero times']:
            n = p['Num pre-zero points']
            pos = p['Pre-Zero pos']
            times = np.linspace(pos - 1, pos, n).tolist()
            t_list = times + t_list

        #if p['Use Rotation Stage'] and self.controller.rot_stage:
        #    s = p['Angles in deg.'].split(',')
        #    angles = list(map(float, s))
        #else:
        #    angles = None

        self.save_defaults()
        p = AOMTwoDPlan(
            name=p['Filename'],
            meta=self.paras.getValues(),
            t3_list=np.asarray(t_list),
            controller=controller,
            max_t2=p['t2 (+)'],
            step_t2=p['t2 (step)'],
            rot_frame_freq=p['Rot. Frame'],
            shaper=controller.shaper,
            #center_wl_list=cwls,
            #use_shutter=p['Use Shutter'] and self.controller.shutter,
            #use_rot_stage=p['Use Rotation Stage'],
            #rot_stage_angles=angles
        )
        return p