from typing import Protocol
from abc import abstractmethod
import datetime
import math
import typing as T
from itertools import cycle

import pyqtgraph as pg
import pyqtgraph.parametertree as pt
from pyqtgraph import PlotItem
from PySide6.QtCore import Qt, Slot, QTimer, QObject, QSettings
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QDialog,
    QStyleFactory,
    QListWidget,
    QErrorMessage,
    QSizePolicy,
    QCheckBox,
    QLayout,
)


from MessPy.Config import config
from qtawesome import icon

if T.TYPE_CHECKING:
    from MessPy.ControlClasses import Controller

VEGA_COLORS = {
    "blue": "#1f77b4",
    "orange": "#ff7f0e",
    "green": "#2ca02c",
    "red": "#d62728",
    "purple": "#9467bd",
    "brown": "#8c564b",
    "pink": "#e377c2",
    "gray": "#7f7f7f",
    "olive": "#bcbd22",
    "cyan": "#17becf",
}

col = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def make_default_cycle():
    return cycle(col[:])


def make_palette():
    """makes dark palette for use with qt fusion theme"""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(15, 15, 15))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(242, 15, 97).lighter())
    palette.setColor(QPalette.HighlightedText, Qt.white)
    palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    return palette


dark_palette = make_palette()


class LED(QWidget):
    def __init__(self, text, parent=None):
        super(LED, self).__init__(parent=parent)
        self.led = QLabel("")
        self.color = "green"
        self.set_color(self.color)

        self.led.setFixedSize(20, 20)
        self.text_label = QLabel(text)

        self.setLayout(hlay((self.led, self.text_label)))
        self.setText = self.text_label.setText

    def set_color(self, color):
        self.color = color
        self.led.setStyleSheet(
            f"background-color:  qradialgradient(cx: 0.5, cy: 0.5, radius: 2, fx: 0.5, fy: 0.5, stop: 0 {self.color}, stop: 1 white);"
        )


class ControlFactory(QWidget):
    """Simple widget build of Label, button and LineEdit

    Parameters
    ----------
    name: str,
        Shows up in the widget

    apply_fn: function,
        The function which gets called (with the the textlabel value)
        after pressing Set.

    update_signal: signal,
        The signal which is listened to update the label.

    parent: QWidget,
        Qt-parent widget

    format_str: str,
        Formatting of the value

    presets: list
        List of values for which a button is generated. When
        the button is clicked, call preset_func with the value.

    preset_func: function
        Gets called with the preset values, is required when using
        presets

    extra_buttons: list of (str, func)
        Creates button with the label given by the string
        and calling the function func.

    """

    def __init__(
        self,
        name,
        apply_fn,
        update_signal=None,
        parent=None,
        format_str="%.1f",
        presets=None,
        preset_func=None,
        preset_rows=4,
        extra_buttons=None,
    ):
        super(ControlFactory, self).__init__(parent=parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QPushButton("Set")
        self.apply_fn = apply_fn
        self.presets_per_row = preset_rows

        self.cur_value_label = QLabel()
        self.format_str = format_str
        self.update_value(0)
        self.edit_box = QLineEdit()
        self.edit_box.setMaxLength(12)
        self.edit_box.setMaximumWidth(100)
        # self.edit_box.setValidator(QDoubleValidator())
        self.edit_box.returnPressed.connect(lambda: apply_fn(self.edit_box.text()))
        self.apply_button.clicked.connect(lambda: apply_fn(self.edit_box.text()))

        _layout = QFormLayout(self)
        _layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for w in [
            (QLabel("<b>%s</b>" % name), self.cur_value_label),
            (self.apply_button, self.edit_box),
        ]:
            _layout.addRow(*w)

        l = []
        if preset_func is None:
            self.preset_func = self.apply_fn
        else:
            self.preset_func = preset_func

        if presets is not None:
            self.setup_presets(presets)

        if extra_buttons is not None:
            self.setup_extra_buttons(extra_buttons)

        if update_signal is not None:
            update_signal.connect(self.update_value)

    @Slot(int)
    @Slot(float)
    def update_value(self, value):
        """updates value of the control widget"""
        if not isinstance(value, str):
            self.cur_value_label.setText(self.format_str % value)
        else:
            self.cur_value_label.setText(value)

    def setup_presets(self, presets):
        len_row = 0
        hlay = QHBoxLayout()
        for p in presets:
            s = partial_formatter(p)
            but = QPushButton(s)
            # but.setStyleSheet('''
            # QPushButton { color: lightblue;}''')
            but.setFlat(False)
            but.clicked.connect(lambda x, p=p: self.preset_func(p))
            but.setFixedWidth(200 // min(len(presets), 4))
            hlay.addWidget(but)
            hlay.setSpacing(10)
            len_row += 1
            if len_row >= self.presets_per_row:
                self.layout().addRow(hlay)
                hlay = QHBoxLayout()
                len_row = 0
        self.layout().addRow(hlay)

    def setup_extra_buttons(
        self,
        extra_buttons: list[tuple[str, T.Callable] | tuple[str, T.Callable, "QIcon"]],
    ):
        row_cnt = 0
        hlay = QHBoxLayout()
        self.layout().addRow(hlay)
        for button_tuple in extra_buttons:
            if len(button_tuple) == 2:
                (s, fn) = button_tuple
                but = QPushButton(s)
            else:
                (s, fn, ic) = button_tuple
                but = QPushButton(text=s, icon=icon(ic))
            but.clicked.connect(fn)
            hlay.addWidget(but)
            row_cnt += 1
            if row_cnt == 2:
                hlay = QHBoxLayout()
                self.layout().addRow(hlay)
                row_cnt = 0


class PlanStarter(Protocol):
    experiment_type: T.ClassVar[str]
    title: T.ClassVar[str]
    icon: T.ClassVar[str]

    def setup_paras(self):
        pass

    def create_plan(self):
        pass


class QProtocolMetaMeta(type(QObject), type(PlanStarter)):
    pass


class PlanStartDialog(QDialog, metaclass=QProtocolMetaMeta):
    experiment_type: str = ""
    title: str = ""
    icon: str = ""
    paras: pt.Parameter

    def __init__(self, controller: "Controller", *args, **kwargs):
        super(PlanStartDialog, self).__init__(*args, **kwargs)
        self.controller = controller
        self.setMinimumWidth(800)
        self.setMaximumHeight(800)
        self.setWindowTitle(self.title)
        self.treeview = pt.ParameterTree()
        self.recent_settings = []
        self.recent_settings_list = QListWidget()
        self.recent_settings_list.currentRowChanged.connect(self.load_recent)

        start_button = QPushButton("Start Plan")
        start_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.plan_valid_lbl = QLabel()
        self.plan_valid_lbl.setText("Plan valid")

        self.setLayout(
            hlay(
                [
                    vlay(
                        [
                            self.treeview,
                            self.plan_valid_lbl,
                            hlay([start_button, cancel_button]),
                        ]
                    ),
                    vlay([QLabel("Recent Settings"), self.recent_settings_list]),
                ]
            )
        )

        self.setup_paras()
        self.setup_recent_list()
        self.treeview.setParameters(self.paras)
        self.paras.sigTreeStateChanged.connect(self.check_if_valid)
        self.treeview.setPalette(self.style().standardPalette())
        self.treeview.setStyle(QStyleFactory.create("Fusion"))
        self.treeview.setStyleSheet("")
        n = len(self.treeview.listAllItems())

        self.resize(350, n * 40 + 100)
        for i in self.treeview.listAllItems():
            if isinstance(i, pt.types.GroupParameterItem):
                i.updateDepth(0)

    @abstractmethod
    def setup_paras(self):
        raise NotImplementedError

    @abstractmethod
    def create_plan(self, controller: "Controller"):
        raise NotImplementedError

    def load_defaults(self, fname=None):
        pass

    def save_defaults(self, fname=None):
        d = self.paras.saveState(filter="user")
        d["date"] = datetime.datetime.now().isoformat()
        name = self.paras.child("Exp. Settings")["Filename"]
        conf_dict = config.exp_settings.setdefault(self.experiment_type, {})

        conf_dict[name] = d
        config.save()

    def closeEvent(self, *args, **kwargs):
        self.save_defaults()
        super().closeEvent(*args, **kwargs)

    def setup_recent_list(self):
        if self.experiment_type not in config.exp_settings:
            return
        conf_dict = config.exp_settings.setdefault(self.experiment_type, {})
        self.recent_settings = sorted(conf_dict.items(), key=lambda kv: kv[1]["date"])

        for name, r in self.recent_settings:
            self.recent_settings_list.addItem(name)

        self.recent_settings_list.setCurrentRow(len(self.recent_settings) - 1)
        self.load_recent(-1)

    def load_recent(self, new):
        settings = self.recent_settings[new][1].copy()
        settings.pop("date")
        self.paras.restoreState(settings, removeChildren=False, addChildren=False)

    def check_if_valid(self):
        try:
            self.create_plan(self.controller)
            self.plan_valid_lbl.setText("Plan valid")
            return True
        except ValueError as e:
            self.plan_valid_lbl.setText("Plan invalid: " + str(e))
            return False

    @classmethod
    def start_plan(cls, controller, parent=None):
        dialog = cls(parent=parent, controller=controller)
        result = dialog.exec_()
        try:
            plan = dialog.create_plan(controller)
        except ValueError as e:
            emsg = QErrorMessage(parent=parent)
            emsg.setWindowModality(Qt.WindowModal)
            emsg.showMessage("Plan creation failed" + str(e))
            emsg.exec_()
            plan = None

            result = QDialog.Rejected
        return plan, result == QDialog.Accepted


class ObserverPlot(pg.PlotWidget):
    def __init__(
        self, obs, signal, x=None, parent=None, aa=False, linewidth=2, **kwargs
    ):
        """Plot windows which can observe an array

        Parameters
        ----------
        obs : tuple of (object, attribute name) or callable
            Every time the signal is fired, the attribute of the object will be plotted
            against x
        signal : Signal
            Which signal to connect to.
        x : data
            The data the observed data is plotted against.
        parent : QWidget
            The QtParent
        aa: bool
            Antialaising of the curve
        linewidth: float
            Linewidth of the curvess

        All other kwargs are passed to PlotWidget.
        """
        super(ObserverPlot, self).__init__(parent=parent, **kwargs)
        signal.connect(self.request_update)
        self.linewidth = linewidth
        self.signal = signal
        self.antialias = aa
        self.color_cycle = make_default_cycle()
        self.plotItem: PlotItem
        self.plotItem.showGrid(x=True, y=True, alpha=1)
        self.lines = {}
        self.observed = []
        if isinstance(obs, tuple):
            obs = [obs]
        else:
            obs = obs
        for i in obs:
            self.add_observed(i)
        # self.enableMouse()
        self.scene().sigMouseClicked.connect(self.click)
        self.click_func = None
        self.x = x
        self.use_inverse = False
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000 // 60)
        self.do_update = False

    def add_observed(self, single_obs):
        self.observed.append(single_obs)
        pen = pg.mkPen(color=next(self.color_cycle), width=self.linewidth)
        curve = self.plotItem.plot(pen=pen, antialias=self.antialias)
        self.lines[single_obs] = curve

    @Slot()
    def request_update(self):
        self.do_update = True
        if not self.timer.isActive():
            self.timer.start(1000 // 60)

    @Slot()
    def update_data(self):
        if not self.do_update:
            return
        self.use_inverse = False
        if self.x is not None and self.use_inverse:
            x = 1e7 / self.x
        else:
            x = self.x

        if callable(self.x):
            x = self.x()

        for o in self.observed:
            if callable(o):
                y = o()
                self.lines[o].setData(x=x, y=y)
            else:
                y = getattr(*o)
                if y is not None:
                    self.lines[o].setData(x=x, y=y)
        self.do_update = False

    @Slot(object)
    def click(self, ev):
        if self.click_func is not None and ev.button() == Qt.MouseButton.LeftButton:
            coords = self.plotItem.vb.mapSceneToView(ev.pos())
            self.click_func(coords)
            ev.accept()

    def set_x(self, x):
        self.x = x

    def closeEvent(self, event) -> None:
        self.signal.disconnect(self.update_data)


class ObserverPlotWithControls(QWidget):
    def __init__(
        self, names, obs, signal, plot_name: str, x=None, parent=None, **kwargs
    ):
        super(ObserverPlotWithControls, self).__init__()
        self.obs_plot = ObserverPlot(obs, signal, x, parent)
        line_controls = QWidget()
        line_controls.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        form_layout = QFormLayout()
        line_controls.setLayout(form_layout)
        settings = QSettings()

        for i, n in enumerate(names):
            line = self.obs_plot.lines[self.obs_plot.observed[i]]
            col = line.opts["pen"].color()
            lb = QLabel('<font color="%s">%s</font>' % (col.name(), n))
            cb = QCheckBox()
            checked = settings.value(f"{plot_name}/{n}", True, type=bool)
            cb.setChecked(checked)
            form_layout.addRow(lb, cb)
            cb.toggled.connect(line.setVisible)
            cb.toggled.connect(
                lambda _, n=n: QSettings().setValue(f"{plot_name}/{n}", _)
            )

        self.line_controls = line_controls
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.obs_plot)
        self.layout().addWidget(self.line_controls)


class ValueLabels(QWidget):
    def __init__(self, obs, fmt: str = "%.1f", parent=None):
        super(ValueLabels, self).__init__(parent=parent)
        lay = QFormLayout()
        self.setStyleSheet("""
        QLabel { font-size: 14pt;}""")
        self.setLayout(lay)
        self.obs = {}
        self.fmt = fmt
        for name, getter in obs:
            self.obs[name] = QLabel("0"), getter
            lay.addRow(name + ":", self.obs[name][0])

    def update_labels(self):
        for lbl, getter in self.obs.values():
            lbl.setText(self.fmt % getter())


def make_groupbox(widgets, title="") -> QGroupBox:
    """Puts given widgets into a groupbox"""
    gb = QGroupBox()
    gb.setContentsMargins(0, 0, 0, 0)
    gb.setSizeIncrement(0, 0)
    vl = QVBoxLayout()
    gb.setLayout(vl)
    # vl.setContentsMargins(0, 0, 0, 0)
    for i in widgets:
        if isinstance(i, QWidget):
            vl.addWidget(i)
        elif isinstance(i, QLayout):
            vl.addLayout(i)
    if title:
        gb.setTitle(title)
    return gb


def create_layout(
    layout_class, *widgets, pre_stretch=False, post_stretch=False
) -> QLayout:
    """Create a layout with the given class and widgets,
    with optional stretch at the start or end."""
    lay = layout_class()
    if len(widgets) == 1 and isinstance(widgets[0], (list, tuple)):
        widgets = widgets[0]
    if pre_stretch:
        lay.addStretch(1)
    for w in widgets:
        if isinstance(w, QWidget):
            lay.addWidget(w)
        elif isinstance(w, QLayout):
            lay.addLayout(w)
        elif isinstance(w, str):
            lay.addWidget(QLabel(w))
    if post_stretch:
        lay.addStretch(1)
    return lay


def hlay(*widgets, post_stretch=False, pre_stretch=False):
    """Return a QHBoxLayout with widgets, with optional stretch at the start or end."""
    return create_layout(
        QHBoxLayout, *widgets, pre_stretch=pre_stretch, post_stretch=post_stretch
    )


def vlay(*widgets, add_stretch=False):
    """Creates a QVBoxLayout with widgets, with optional stretch at the end."""
    return create_layout(QVBoxLayout, *widgets, post_stretch=add_stretch)


def partial_formatter(val: float) -> str:
    if val == 0:
        return "0"
    else:
        sign = val / abs(val)
        sign = " " if sign > 0 else "-"
    if math.log10(abs(val)) >= 3:
        return sign + "%dk" % (abs(val) / 1000)
    else:
        return sign + str(abs(val))


def remove_nodes(a):
    """This function removes empty children and values entry in the output of the pyqtgraph parametertrees"""
    a = a.copy()
    for s in a.keys():
        if isinstance(a[s], tuple):
            if a[s][0] is None:
                a[s] = remove_nodes(a[s][1])
            elif len(a[s][1]) == 0:
                a[s] = a[s][0]
            else:
                a[s] = (a[s][0], remove_nodes(a[s][1]))
    return a


def make_entry(paras):
    plan_settings = remove_nodes(paras.getValues())
    return {"Plan Settings": plan_settings}


def float_param(
    name: str,
    default: float,
    step: float,
    min_val: float | None = None,
    max_val: float | None = None,
    **kwargs,
):
    "Helper function to create a float parameter using type hints"
    return pt.Parameter.create(
        name=name,
        type="float",
        value=default,
        step=step,
        limits=(min_val, max_val),
        **kwargs,
    )


def int_params(
    name: str,
    default: int,
    step: int,
    min_val: int | None = None,
    max_val: int | None = None,
    **kwargs,
):
    "Helper function to create a float parameter using type hints"
    return pt.Parameter.create(
        name=name,
        type="int",
        value=default,
        step=step,
        limits=(min_val, max_val),
        **kwargs,
    )
