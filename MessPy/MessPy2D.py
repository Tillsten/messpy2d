from functools import partial


from PySide6.QtCore import QTimer, Qt, Slot, QThread, QSettings
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QDockWidget,
    QPushButton,
    QLabel,
    QSizePolicy,
    QMessageBox,
    QGroupBox,
    QCheckBox,
)
import qtawesome as qta
from pyqtgraph import setConfigOptions
from qtpy.QtWidgets import QVBoxLayout
from loguru import logger

from MessPy.Config import config
from MessPy.ControlClasses import Controller
from MessPy.Instruments.interfaces import ICam
from MessPy.Plans import *

from MessPy.QtHelpers import (
    ControlFactory,
    make_groupbox,
    ValueLabels,
    ObserverPlotWithControls,
    hlay,
    vlay,
)
from MessPy.SampleMoveWidget import MoveWidget

qta.set_defaults(color="white")
setConfigOptions(
    enableExperimental=True,
    useNumba=True,
    antialias=False,
    useOpenGL=False,
)


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Messpy-2D Edition")
        self.setWindowIcon(qta.icon("fa.play"))
        self.controller = controller  # controller
        logger.info("Creating loop thread")
        self.controller_thread = QThread()
        self.controller_thread.setObjectName("Controller Thread")
        logger.info(f"Main threadis {QThread.currentThread()}")
        logger.info(f"Controller thread id is {self.controller_thread.currentThread()}")
        controller.moveToThread(self.controller_thread)
        self.controller_thread.start()
        app = QApplication.instance()
        assert app is not None
        app.aboutToQuit.connect(self.cleanup)
        self.setup_toolbar()
        self.cm = CommandMenu(controller, self)
        self.setCentralWidget(self.cm)
        self.timer = QTimer()
        self.update_time = 10
        self.timer.timeout.connect(controller.loop, Qt.ConnectionType.QueuedConnection)
        self.toggle_run(True)
        self.xaxis = {}

        dock_wigdets = []
        for c in controller.cam_list:
            lf = controller.loop_finished
            c.last_read
            self.xaxis[c] = c.wavelengths.copy()

            obs = [lambda i=i, c=c: c.last_read.lines[i, :] for i in range(c.cam.lines)]
            op = ObserverPlotWithControls(
                c.cam.line_names, obs, lf, x=c.disp_axis, plot_name="Readings"
            )
            dw = QDockWidget("Readings")
            dw.setWidget(op)
            dock_wigdets.append(dw)

            obs = [
                lambda i=i, c=c: c.last_read.stds[i, :] for i in range(c.cam.std_lines)
            ]
            op2 = ObserverPlotWithControls(
                c.cam.std_names, obs, lf, x=c.disp_axis, plot_name="Readings - stddev"
            )
            op2.obs_plot.setYRange(0, 8)
            dw = QDockWidget("Readings - stddev")
            dw.setWidget(op2)
            dock_wigdets.append(dw)

            obs = [
                lambda i=i, c=c: c.last_read.signals[i, :]
                for i in range(c.cam.sig_lines)
            ]
            op3 = ObserverPlotWithControls(
                c.cam.sig_names, obs, lf, x=c.disp_axis, plot_name="Signals"
            )
            dw = QDockWidget("Pump-probe signal")
            dw.setWidget(op3)
            dock_wigdets.append(dw)

        for dw in dock_wigdets:
            self.addDockWidget(Qt.LeftDockWidgetArea, dw)

        if len(dock_wigdets) > 3:
            self.splitDockWidget(dock_wigdets[0], dock_wigdets[3], Qt.Horizontal)
            self.splitDockWidget(dock_wigdets[1], dock_wigdets[4], Qt.Horizontal)
            self.splitDockWidget(dock_wigdets[2], dock_wigdets[5], Qt.Horizontal)
        self.setCentralWidget(self.cm)

        # self.controller.cam.sigRefCalibrationFinished.connect(self.plot_calib)
        self.readSettings()

    def setup_toolbar(self):
        self.toolbar = self.addToolBar("Begin Plan")
        tb = self.toolbar

        def plan_starter(PlanClass):
            def f():
                plan, ok = PlanClass.start_plan(self.controller)
                self.controller.stop_plan()
                if ok:
                    self.toggle_run(False)
                    self.plan_class = PlanClass
                    self.viewer = PlanClass.viewer(plan)
                    self.viewer.show()
                    self.controller.start_plan(plan)
                    plan.sigPlanFinished.connect(self.controller.stop_plan)
                    self.toggle_run(True)

            return f

        plans = [
            ("Pump Probe", "ei.graph", PumpProbeStarter),
            ("Scan Spectrum", "ei.barcode", ScanSpectrumStarter),
            ("Adaptive TZ", "ei.car", AdaptiveTZStarter),
        ]

        if self.controller.sample_holder is not None:
            plans.append(("Focus Scan", "fa5s.ruler-combined", FocusScanStarter))
            plans.append(("Signal Image", "fa5s.image", SignalImageStarter))

        if self.controller.shaper is not None:
            plans += [("Fast GVD Scan", "ei.car", FastGVDScanStarter)]
            plans += [("GVD Scan", "fa5s.stopwatch", GVDScanStarter)]
            plans += [("2D Measurement", "ei.graph", AOMTwoDStarter)]

            if self.controller.shaper.fm1 is not None:
                plans += [("Folding Mirror Scan", "fa5s.stopwatch", ScanFoldingMirrorsStarter)]
       

        for text, icon, starter in plans:
            asl_icon = qta.icon(icon, color="white")
            pp = QPushButton(text, icon=asl_icon)
            pp.clicked.connect(plan_starter(starter))
            tb.addWidget(pp)

        if self.controller.shaper is not None:

            def start_calib():
                c = self.controller
                self.cal_viewer = CalibScanView(c.cam_list[0], c.shaper)
                self.cal_viewer.sigPlanCreated.connect(c.start_plan)
                self.cal_viewer.show()

            asl_icon = qta.icon("fa5s.ruler", color="white")
            pp = QPushButton(text="Shaper Calibration", icon=asl_icon)
            pp.clicked.connect(start_calib)
            tb.addWidget(pp)

        alg_icon = qta.icon("fa5s.crosshairs")
        pp = QPushButton("Show alignment helper", icon=alg_icon)
        pp.clicked.connect(self.show_alignment_helper)
        tb.addWidget(pp)

    @Slot(int)
    def set_update_time(self, ms: int):
        self.update_time = ms

    @Slot()
    @Slot(bool)
    def toggle_run(self, bool=True):
        if bool:
            self.timer.setSingleShot(True)
            self.timer.setInterval(self.update_time)
            self.controller.loop_finished.connect(self.timer.start)
            self.timer.start()
        else:
            self.timer.stop()

    def toggle_wl(self, c):
        self.xaxis[c][:] = 1e7 / self.xaxis[c][:]

    @Slot()
    def show_planview(self):
        if self.viewer is not None:
            self.viewer.show()
        else:
            self.viewer = self.plan_class.viewer(self.controller.plan)

    @Slot()
    def show_alignment_helper(self):
        self._ah = AlignmentHelper(self.controller)
        self._ah.show()
        # dw = QDockWidget(self._ah)
        # self.addDockWidget(Qt.LeftDockWidgetArea, dw)

    # def closeEvent(self, *args, **kwargs):
    #     self.toggle_run(False)

    #     config.save()
    #     # settings = QSettings()
    #     # settings.setValue("geometry", self.saveGeometry())
    #     # settings.setValue("windowState", self.saveState())
    #     logger.info("Closing")

    #     super().closeEvent(*args, **kwargs)

    def readSettings(self):
        pass
        # settings = QSettings()
        # if settings.contains("geometry"):
        #    self.restoreGeometry(settings.value("geometry"))
        #    self.restoreState(settings.value("windowState"))

    def cleanup(self):
        self.controller.stop_plan()
        self.timer.stop()
        self.controller_thread.quit()
        config.save()


class CommandMenu(QWidget):
    def __init__(self, controller, main_window):
        super(CommandMenu, self).__init__()
        self.main_window = main_window
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._layout = QVBoxLayout(self)
        c = controller  # type: Controller
        self.controller = c
        self.add_plan_controls()

        gb1 = CamControls(c)
        self._layout.addWidget(gb1)
        gb2 = DelayLineControl(c)
        self._layout.addWidget(gb2)

        for control in [gb1, gb2]:
            c.starting_plan.connect(control.setDisabled)
            c.stopping_plan.connect(control.setEnabled)

        for cam in c.cam_list:
            if cam.changeable_wavelength:
                gb = SpectrometerControls(cam)
                self._layout.addWidget(gb)
                c.starting_plan.connect(gb.setDisabled)
                c.stopping_plan.connect(gb.setEnabled)
        if len(c.shutter) > 0:
            self._layout.addWidget(ShutterControls(c))
        if c.rot_stage:
            self.add_rot_stage(c.rot_stage)
        if c.sample_holder:
            self.add_sample_holder(c.sample_holder)
        if c.shaper is not None:
            self.add_shaper(c.shaper)

    def add_plan_controls(self):
        c = self.controller  # type: Controller

        def ask_stop():
            result = QMessageBox.question(self, "MessPy", "Stop Plan?")
            if result == QMessageBox.Yes:
                c.stop_plan()

        stop_plan_but = QPushButton(qta.icon("fa.stop"), "Stop")
        stop_plan_but.clicked.connect(ask_stop)

        pause_plan_but = QPushButton(text="Pause plan", icon=qta.icon("fa.pause"))
        pause_plan_but.clicked.connect(lambda: setattr(c, "pause_plan", True))

        reopen_planview_but = QPushButton(
            qta.icon("fa5s.window-restore"), "Reopen Planview"
        )
        reopen_planview_but.clicked.connect(self.main_window.show_planview)

        for but in stop_plan_but, pause_plan_but, reopen_planview_but:
            c.starting_plan.connect(but.setEnabled)
            c.stopping_plan.connect(but.setDisabled)
            but.setDisabled(True)

        cb_running = QPushButton(
            text="Running", icon=qta.icon("fa.play", color="white")
        )
        cb_running.setCheckable(True)
        cb_running.setChecked(True)
        cb_running.toggled.connect(self.main_window.toggle_run)
        for w in (reopen_planview_but, stop_plan_but, pause_plan_but, cb_running):
            self._layout.addWidget(w)

    def add_ext_view(self):
        def get_ext(i):
            lr = self.main_window.controller.last_read
            return lr.ext[:,]

        vl = ValueLabels([("Ext 1", partial(get_ext, 1))])
        self._layout.addWidget(make_groupbox([vl], "Ext."))

    def add_rot_stage(self, rs):
        rsi = ControlFactory(
            "Angle", rs.set_degrees, format_str="%.1f deg", presets=[0, 45]
        )
        rsi.update_value(rs.get_degrees())
        rs.sigDegreesChanged.connect(rsi.update_value)
        gb = make_groupbox([rsi], "Rotation Stage")
        self._layout.addWidget(gb)

    def add_sample_holder(self, saho):
        move_wid = MoveWidget(saho)
        gb = make_groupbox([move_wid], "Sample Holder")
        self._layout.addWidget(gb)

    def add_shaper(self, sh):
        from .ShaperRotStages import ShaperControl

        self.shaper_controls = ShaperControl(
            sh.rot1, sh.rot2, sh, 
            folding_mirror_1=getattr(sh, "fm1", None), 
            folding_mirror_2=getattr(sh, "fm2", None)
        )
        but = QPushButton("Shaper Contorls")
        but.clicked.connect(self.shaper_controls.show)
        self._layout.addWidget(but)
        return


class ShutterControls(QGroupBox):
    def __init__(self, c: Controller):
        super(ShutterControls, self).__init__()
        self.setTitle("Shutters")
        assert len(c.shutter) > 0
        w = []
        for shutter in c.shutter:
            cb = QCheckBox(shutter.name)
            cb.setChecked(shutter.is_open())
            cb.toggled.connect(shutter.toggle)
            w.append(cb)
        self.setLayout(vlay(*w))


class CamControls(QGroupBox):
    def __init__(self, c: Controller):
        super(CamControls, self).__init__()
        # type: list[tuple[str, Callable, str]]
        bg_buttons = [("BG", c.cam.get_bg, "fa5.circle")]
        if hasattr(c.cam, "calibrate_ref"):
            bg_buttons.append(("Refcalib.", c.cam.calibrate_ref, "fa5.clone"))
        if c.cam2:
            bg_buttons.append(("BG2", c.cam2.get_bg, "fa5s.circle"))
        if c.cam.cam.can_validate_pixel:
            bg_buttons.append(
                ("Mark valid pix", c.cam.cam.mark_valid_pixel, "fa5s.check")
            )
            bg_buttons.append(
                ("Delete valid pix", c.cam.cam.delete_valid_pixel, "fa5s.times")
            )
        if w := c.cam.cam.get_extra_widgets():
            self._extra_widget = w
            bg_buttons.append(("Extra", w.show, "fa5s.plus"))
        sc = ControlFactory(
            "Shots",
            c.cam.set_shots,
            format_str="%d",
            presets=[20, 100, 500, 1000],
            extra_buttons=bg_buttons,
        )
        sc.edit_box.setValidator(QIntValidator(10, 50000))
        c.cam.sigShotsChanged.connect(sc.update_value)
        self.setTitle("ADC")
        self.setLayout(vlay(sc))


class SpectrometerControls(QGroupBox):
    def __init__(self, cam: ICam, *args):
        """
        Controls for the spectrometer. This includes wavelength, slit, grating and wavenumber controls.
        Latter is only available if the spectrometer supports it.

        Parameters
        ----------
        cam : ICam
            The camera object to control, here we assume it has a spectrometer object.
        """
        super(SpectrometerControls, self).__init__()
        spec = cam.cam.spectrograph

        def calc_and_set_wl(s):
            if len(s) == 0:
                return
            s = s.strip()
            try:
                if s[-1] == "c":
                    wl = 1e7 / float(s[:-1])
                else:
                    wl = float(s)
                spec.set_wavelength(wl)
            except ValueError:
                pass

        spec_control = ControlFactory(
            "Wavelength",
            calc_and_set_wl,
            format_str="%.1f nm",
            presets=[-100, -50, 50, 100],
            preset_func=lambda x: spec.set_wavelength(spec.get_wavelength() + x),
        )
        spec.sigWavelengthChanged.connect(spec_control.update_value)
        spec.sigWavelengthChanged.emit(spec.get_wavelength())
        l = [spec_control]
        if spec.changeable_slit:

            def pre_fcn(x):
                return spec.spectrograph.set_slit(spec.get_slit() + x)

            slit_control = ControlFactory(
                "Slit (μm)", spec.set_slit, presets=[-10, 10], preset_func=pre_fcn
            )
            slit_control.update_value(spec.get_slit())
            spec.sigSlitChanged.connect(slit_control.update_value)
            l.append(slit_control)

        cb = QCheckBox("Use Wavenumbers")
        checked = QSettings().value("use_wavenumbers", False, type=bool)
        cb.setChecked(checked)
        cb.clicked.connect(cam.set_disp_wavelengths)
        cb.clicked.connect(lambda x: QSettings().setValue("use_wavenumbers", x))
        l[-1].layout().addRow(cb)
        if len(spec.gratings) > 1:
            gratings = spec.gratings
            cur_grating = spec.get_grating()
            lbl = QLabel("G: %s" % gratings[cur_grating])
            self.btns_ = [lbl]
            for idx, name in gratings.items():
                btn = QPushButton(name)

                btn.clicked.connect(lambda x, idx=idx: spec.set_grating(idx))
                btn.setFixedWidth(70)
                self.btns_.append(btn)
            l.append(hlay(self.btns_, post_stretch=1))
        spec.sigGratingChanged.connect(lambda g: lbl.setText("G: %s" % gratings[g]))
        self.setTitle(f"Spec: {cam.cam.name}")
        self.setLayout(vlay(*l))


class DelayLineControl(QGroupBox):
    """
    Controls for the delay lines. This includes the delay line and the optional second delay line.
    """

    def __init__(self, c: Controller):
        super(DelayLineControl, self).__init__()
        dl = c.delay_line
        dl1c = ControlFactory(
            "Delay 1",
            lambda x: c.delay_line.set_pos(x, do_wait=False),
            format_str="%.1f fs",
            extra_buttons=[("Set Home", dl.set_home)],
            presets=[-50000, -10000, -1000.0001, -50, 50000, 10000, 1000.0001, 50],
            preset_func=lambda x: dl.set_pos(dl.get_pos() + x, do_wait=False),
        )
        c.delay_line.sigPosChanged.connect(dl1c.update_value)
        dl1c.update_value(c.delay_line.get_pos())
        dls = [dl1c]

        if c.delay_line_second:
            dl2 = c.delay_line_second
            dl2c = ControlFactory(
                "Delay 2",
                dl2.set_pos,
                format_str="%.1f fs",
                extra_buttons=[("Set Home", dl2.set_pos)],
            )
            dls.append(dl2c)
            dl2.sigPosChanged.connect(dl2c.update_value)
        self.setTitle("Delay Lines")
        self.setLayout(vlay(dls))


def start_app():
    import sys
    import qasync

    import asyncio as aio
    import traceback

    from pyqtgraph.parametertree.parameterTypes.basetypes import GroupParameter
    GroupParameter.value = lambda self: None
    from pyqtgraph import mkQApp, setConfigOption

    setConfigOption("antialias", True)
    app = mkQApp()


    app.setOrganizationName("USD")
    app.setApplicationName("MessPy3")
    sys._excepthook = sys.excepthook

    def exception_hook(exctype, value, tb):
        emsg = QMessageBox()
        emsg.setWindowModality(Qt.WindowModal)
        traceback.print_tb(tb)
        s = []
        while tb and (tb := tb.tb_next):
            s += traceback.format_tb(tb, limit=4)
        emsg.setText("Exception raised")
        emsg.setInformativeText("".join(s[-5:]))
        emsg.setMaximumHeight(1000)
        emsg.setStandardButtons(QMessageBox.Abort | QMessageBox.Ignore)  # type: ignore
        result = emsg.exec_()
        if not result == QMessageBox.Ignore:
            sys._excepthook(exctype, value, tb)
            exit()
        else:
            pass

    sys.excepthook = exception_hook

    mw = MainWindow(Controller())
    mw.showMaximized()
    loop = qasync.QEventLoop(app)
    aio.set_event_loop(loop)
    app_close_event = aio.Event()
    app.aboutToQuit.connect(app_close_event.set)
    with loop:
        loop.run_until_complete(app_close_event.wait())
    # app.exec()
