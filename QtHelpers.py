from functools import partial
from itertools import cycle
from qtpy.QtGui import QPalette, QColor
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QWidget, QLineEdit, QLabel, QPushButton, QHBoxLayout,
                            QFormLayout, QGroupBox, QVBoxLayout,)
import pyqtgraph as pg
import math
import numpy as np
import attr


VEGA_COLORS = {
    'blue': '#1f77b4',
    'orange': '#ff7f0e',
    'green': '#2ca02c',
    'red': '#d62728',
    'purple': '#9467bd',
    'brown': '#8c564b',
    'pink': '#e377c2',
    'gray': '#7f7f7f',
    'olive': '#bcbd22',
    'cyan': '#17becf'}

col = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
       '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
       '#bcbd22', '#17becf']


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
    palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
    palette.setColor(QPalette.HighlightedText, Qt.white)
    palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
    return palette


class ControlFactory(QWidget):
    """Simple widget build of Label, button and LineEdit"""
    def __init__(self, name, apply_fn, update_signal=None, parent=None,
                 format_str='%.1f', presets=None, preset_func=None,extra_buttons=None):
        super(ControlFactory, self).__init__(parent=parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.apply_button = QPushButton('Set')
        self.apply_fn = apply_fn
        self.cur_value_label = QLabel()
        self.format_str = format_str
        self.update_value(0)
        self.edit_box = QLineEdit()
        self.edit_box.setMaxLength(7)
        self.edit_box.setMaximumWidth(100)
        self.apply_button.clicked.connect(lambda: apply_fn(self.edit_box.text()))

        self._layout = QFormLayout(self)
        self._layout.setLabelAlignment(Qt.AlignRight)

        for w in [(QLabel('<b>%s</b>'%name), self.cur_value_label),
                  (self.apply_button, self.edit_box)]:
            self._layout.addRow(*w)
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
            update_signal.connect(self.update)

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
            but.setStyleSheet('''
            QPushButton { color: lightblue;}''')
            but.setFlat(False)
            but.clicked.connect(partial(self.preset_func, p))
            but.setFixedWidth(200/min(len(presets), 4))
            hlay.addWidget(but)
            hlay.setSpacing(10)
            len_row += 1
            if len_row > 3:
                self._layout.addRow(hlay)
                hlay = QHBoxLayout()
                len_row = 0
            self._layout.addRow(hlay)

    def setup_extra_buttons(self, extra_buttons):
        hlay = QHBoxLayout()
        for (s, fn) in extra_buttons:
            but = QPushButton(s)
            but.clicked.connect(fn)
            hlay.addWidget(but)
        self._layout.addRow(hlay)




#class ObservedLine:
#    obs_attr = attrib()
#    line_color = attrib()


class ObserverPlot(pg.PlotWidget):
    def __init__(self, obs, signal, x=None, parent=None):
        super(ObserverPlot, self).__init__(parent=parent)
        signal.connect(self.update_data)
        self.color_cycle = make_default_cycle()
        self.plotItem.showGrid(x=True, y=True, alpha=1)
        self.lines = {}
        self.observed = []
        if isinstance(obs, tuple):
            obs = [obs]
        else:
            obs = obs
        for i in obs:
            self.add_observed(i)
        #self.enableMouse()
        self.sceneObj.sigMouseClicked.connect(self.click)
        self.click_func = None

    def add_observed(self, single_obs):
        self.observed.append(single_obs)
        pen = pg.mkPen(color=next(self.color_cycle), width=4)
        self.lines[single_obs[1]] = self.plotItem.plot([0], pen=pen)

    def update_data(self):
        for o in self.observed:
            self.lines[o[1]].setData(getattr(*o))

    def click(self, ev):
        print(ev.button())

        if self.click_func is not None and ev.button() == 1:
            coords = self.plotItem.vb.mapSceneToView(ev.pos())
            self.click_func(coords)
            ev.accept()




class ValueLabels(QWidget):
    def __init__(self, obs, parent=None):
        super(ValueLabels, self).__init__(parent=parent)
        lay = QFormLayout()
        self.setStyleSheet('''
        QLabel { font-size: 14pt;}''')
        self.setLayout(lay)
        self.obs = {}
        for name, getter in obs:
            self.obs[name] = QLabel('0'), getter
            lay.addRow(name + ':', self.obs[name][0])


def make_groupbox(widgets, title=''):
    """Puts given widgets into a groupbox"""
    gb = QGroupBox()
    gb.setContentsMargins(0, 0, 0, 0)
    gb.setSizeIncrement(0, 0)
    vl = QVBoxLayout(gb)
    vl.setContentsMargins(0, 0, 0, 0)
    for i in widgets:
        vl.addWidget(i)
    if title:
        gb.setTitle(title)

    return gb

dark_palette = make_palette()


def hlay(widgets, add_stretch=False):
    lay = QHBoxLayout()
    for w in widgets:
        try:
            lay.addWidget(w)
        except TypeError:
            lay.addLayout(w)

    if add_stretch:
        lay.addStretch(1)
    return lay


def vlay(widgets, add_stretch=False):
    lay = QVBoxLayout()
    for w in widgets:
        try:
            lay.addWidget(w)
        except TypeError:
            lay.addLayout(w)

    if add_stretch:
        lay.addStretch(1)
    return lay


def partial_formatter(val):
    sign = val/abs(val)
    if math.log10(abs(val)) > 3:
        return '%dk'%(sign*(abs(val)//1000))
    else:
        return str(val)

