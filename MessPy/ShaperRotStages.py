from MessPy.Instruments.signal_processing import cm2THz, THz2cm
from MessPy.Instruments.RotationStage import RotationStage
from MessPy.Instruments.dac_px import AOM

import attr
from PySide6.QtCore import Qt, Slot
from PySide6 import QtWidgets
from MessPy.QtHelpers import ControlFactory, vlay, hlay

from pyqtgraph.parametertree import Parameter, ParameterTree

dispersion_params = [
    dict(name="gvd", type="float", value=0),
    dict(name="tod", type="float", value=0),
    dict(name="fod", type="float", value=0),
    dict(name="center", type="float", value=2000, decimals=5),
    dict(name="Phase Sign", type="float", value=1.0),
]


@attr.s
class ShaperControl(QtWidgets.QWidget):
    rs1: RotationStage = attr.ib()
    rs2: RotationStage = attr.ib()
    aom: AOM = attr.ib()
    folding_mirror_1: RotationStage | None = attr.ib()
    folding_mirror_2: RotationStage | None = attr.ib()

    def __attrs_post_init__(self):
        super(ShaperControl, self).__init__()
        self.setWindowTitle("Shaper Controls")
        preset = [-1, -0.1, -0.01] + [0.01, 0.1, 1][::-1]
        rot_stages: list[RotationStage] = [self.rs1, self.rs2]
        names = ["Grating 1", "Grating 2"]
        if self.folding_mirror_1:
            assert self.folding_mirror_2 is not None
            rot_stages += [self.folding_mirror_1, self.folding_mirror_2]
            names += ["FM 1", "FM2 2"]
        rot_controls = []
        for name, rs in zip(names, rot_stages):
            f = rs.move_relative
            c1 = ControlFactory(
                name,
                apply_fn=rs.set_degrees,
                update_signal=rs.signals.sigDegreesChanged,
                format_str="%.2f",
                presets=preset,
                preset_func=f,
                preset_rows=3,
            )
            c1.update_value(rs.get_degrees())
            rot_controls.append(c1)
        slider_lbl = QtWidgets.QLabel("bla")

        self.slider = QtWidgets.QSlider()
        self.slider.setOrientation(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(
            lambda x: slider_lbl.setText("%0.2f" % (x / 1000))
        )
        self.slider.setValue(int(self.aom.amp_fac * 1000))
        self.slider.valueChanged.connect(lambda x: self.aom.set_wave_amp(x / 1000))

        calib_label = QtWidgets.QLabel()

        def f(x):
            return calib_label.setText("%.2e %.2e %.2e" % tuple(x))

        self.aom.sigCalibChanged.connect(f)
        if self.aom.calib is not None:
            self.aom.sigCalibChanged.emit(self.aom.calib)

        self.chopped = QtWidgets.QCheckBox("Chopped")
        self.chopped.setChecked(self.aom.chopped)
        self.chopped.toggled.connect(lambda x: setattr(self.aom, "chopped", x))
        self.chopped.toggled.connect(lambda x: self.aom.generate_waveform())
        self.pc = QtWidgets.QCheckBox("Phase Cycle")
        self.pc.setChecked(self.aom.phase_cycle)
        self.pc.toggled.connect(lambda x: setattr(self.aom, "phase_cycle", x))
        self.pc.toggled.connect(lambda x: self.aom.generate_waveform())
        self.chopped.toggled.connect(lambda x: self.aom.generate_waveform())

        self.apply = QtWidgets.QPushButton("Apply Waveform")
        self.apply.clicked.connect(lambda x: self.aom.generate_waveform())
        self.cali = QtWidgets.QPushButton("Full Mask")
        self.cali.clicked.connect(self.aom.load_full_mask)
        self.sc = QtWidgets.QPushButton("Set spec amp")
        self.sc.clicked.connect(self.aom.set_compensation_amp)
        self.sc2 = QtWidgets.QPushButton("Del spec amp")
        self.sc2.clicked.connect(lambda p: setattr(self.aom, "compensation_amp", None))

        self.disp_param = Parameter.create(
            name="Dispersion", type="group", children=dispersion_params
        )
        self.disp_param["gvd"] = self.aom.gvd / 1000
        self.disp_param["tod"] = self.aom.tod / 1000
        self.disp_param["fod"] = self.aom.fod / 1000
        self.disp_param["center"] = THz2cm(self.aom.nu0_THz)

        for c in self.disp_param.children():
            c.sigValueChanged.connect(self.update_disp)

        self.chop_params = Parameter.create(
            name="Chopping",
            type="group",
            children=[
                dict(name="Window Mode", type="bool", value=False),
                dict(name="lower wn", type="float", value=self.aom.chop_window[0]),
                dict(name="upper wn", type="float", value=self.aom.chop_window[1]),
            ],
        )

        for c in self.chop_params.children():
            c.sigValueChanged.connect(self.update_chop)

        self.pt = ParameterTree()
        self.pt.setParameters(self.disp_param)
        self.pt.addParameters(self.chop_params)

        self.setLayout(
            hlay(
                vlay("<h2>Motors</h2>", *rot_controls),
                vlay(
                    "<h2>AOM</h2>",
                    "<h3>Power</h3>",
                    hlay(slider_lbl, self.slider),
                    "<h3>Calib Values</h3>",
                    calib_label,
                    self.chopped,
                    self.pc,
                    self.pt,
                    hlay(self.sc, self.sc2),
                    hlay((self.apply, self.cali)),
                )
            )
        )

    @Slot()
    def update_disp(self):
        for i in ["gvd", "tod", "fod"]:
            setattr(self.aom, i, self.disp_param[i] * 1000)
        self.aom.nu0_THz = cm2THz(self.disp_param["center"])
        self.aom.phase_sign = self.disp_param["Phase Sign"]
        self.aom.update_dispersion_compensation()

    @Slot()
    def update_chop(self):
        self.aom.chop_window = (
            self.chop_params["lower wn"],
            self.chop_params["upper wn"],
        )
        mode = "window" if self.chop_params["Window Mode"] else "standard"
        self.aom.chop_mode = mode
        self.aom.generate_waveform()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    # from qt_material import apply_stylesheet
    # apply_stylesheet(app, 'light_blue.xml')
    aom = AOM()
    # from MessPy.Instruments.RotationStage import RotationStage

    aom.set_wave_amp(0.4)
    aom.gvd = -50
    aom.nu0_THz = cm2THz(2100)
    aom.update_dispe
