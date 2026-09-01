from pytest import fixture

from MessPy.Config import config
from MessPy.ControlClasses import Controller
from MessPy.Plans import AlignmentHelper, SignalAlignmentHelper

config.testing = True


@fixture
def controller(qtbot):
    controller = Controller()
    controller.cam.set_shots(2)
    return controller


def test_alignment_helper_updates(controller, qtbot):
    widget = AlignmentHelper(controller)
    qtbot.addWidget(widget)

    for _ in range(3):
        controller.loop()

    for (cam, line), (_plot, data) in widget.amp_lines.items():
        assert len(data) > 0
    for (cam, line), (_plot, data) in widget.std_lines.items():
        assert len(data) > 0


def test_signal_alignment_helper_updates(controller, qtbot):
    widget = SignalAlignmentHelper(controller)
    qtbot.addWidget(widget)

    for _ in range(3):
        controller.loop()

    for (cam, line), (_plot, data) in widget.evo_lines.items():
        assert len(data) > 0
    for (cam, line), (_plot, data) in widget.max_lines.items():
        assert len(data) > 0


def test_signal_alignment_helper_baseline_subtracted(controller, qtbot):
    widget = SignalAlignmentHelper(controller)
    qtbot.addWidget(widget)

    controller.loop()

    cam = controller.cam_list[0]
    ref1, ref2 = widget.ref_lines[cam]
    ref1.setPos(0)
    ref2.setPos(0)

    subtracted = widget.baseline_subtracted(cam, 0)
    assert subtracted[0] == 0
