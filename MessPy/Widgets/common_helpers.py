import math

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLayout, QWidget, QLabel


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
