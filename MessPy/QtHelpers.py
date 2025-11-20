from typing import Protocol
from abc import abstractmethod
import datetime
import math
import typing as T
from itertools import cycle

import pyqtgraph as pg
import pyqtgraph.parametertree as pt
from pyqtgraph.parametertree import Parameter

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
from MessPy.Widgets.PlanStarter import PlanStarter, PlanStartDialog
from MessPy.Widgets.common_helpers import partial_formatter, hlay, vlay
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
            line.setVisible(checked)
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




def getValuesGroupFriendly(para: Parameter):
    vals = {}
    for ch in para:        
        if ch.hasValue():
            vals[ch.name()] = (ch.value(), getValuesGroupFriendly(ch))
        else:
            vals[ch.name()] = (None, getValuesGroupFriendly(ch))
    return vals

def make_entry(paras: Parameter):
    plan_settings = remove_nodes(getValuesGroupFriendly(paras))
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
