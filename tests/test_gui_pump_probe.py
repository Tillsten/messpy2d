import pytest

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QPushButton

from MessPy.Plans.PumpProbe import PumpProbePlan
from MessPy.Plans.PumpProbeViewer import PumpProbeStarter


@pytest.mark.parametrize(
    "gui_plan_window",
    [False, True],
    indirect=True,
    ids=["single-delay-line", "second-delay-line"],
)
def test_gui_starts_pump_probe_plan(gui_plan_window, qtbot):
    main_window = gui_plan_window
    main_window.show()
    qtbot.waitExposed(main_window)

    start_button = next(
        button
        for button in main_window.toolbar.findChildren(QPushButton)
        if button.text() == "Pump Probe"
    )
    opened_dialog = []

    def accept_plan_dialog():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, PumpProbeStarter)
        opened_dialog.append(dialog)
        if main_window.controller.delay_line_second is not None:
            dialog.paras.child("Exp. Settings", "Main Delay Line").setValue(
                main_window.controller.delay_line_second._dl.name
            )
        dialog.start_button.click()

    QTimer.singleShot(0, accept_plan_dialog)
    with qtbot.waitSignal(main_window.controller.starting_plan, timeout=5000):
        qtbot.mouseClick(start_button, Qt.MouseButton.LeftButton)

    assert len(opened_dialog) == 1
    assert isinstance(main_window.controller.plan, PumpProbePlan)
    expected_delay_line = (
        main_window.controller.delay_line_second
        if main_window.controller.delay_line_second is not None
        else main_window.controller.delay_line
    )
    assert main_window.controller.plan.main_delay_line is expected_delay_line
