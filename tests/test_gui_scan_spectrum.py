import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QPushButton

from MessPy.Plans.ScanSpectrum import ScanSpectrum
from MessPy.Plans.ScanSpectrumView import ScanSpectrumStarter


def test_gui_starts_scan_spectrum(gui_plan_window, qtbot):
    main_window = gui_plan_window
    main_window.show()
    qtbot.waitExposed(main_window)

    start_button = next(
        button
        for button in main_window.toolbar.findChildren(QPushButton)
        if button.text() == "Scan Spectrum"
    )
    opened_dialog = []

    def accept_plan_dialog():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ScanSpectrumStarter)
        opened_dialog.append(dialog)
        settings = dialog.paras.child("Exp. Settings")
        settings.child("Filename").setValue("gui spectrum test")
        settings.child("Linear Axis").setValue("nm")
        settings.child("Min.", "Wavelength (nm)").setValue(500)
        settings.child("Max.", "Wavelength (nm)").setValue(700)
        settings.child("Resolution").setValue(100)
        dialog.start_button.click()

    QTimer.singleShot(0, accept_plan_dialog)
    with qtbot.waitSignal(main_window.controller.starting_plan, timeout=5000):
        qtbot.mouseClick(start_button, Qt.MouseButton.LeftButton)

    assert len(opened_dialog) == 1
    plan = main_window.controller.plan
    assert isinstance(plan, ScanSpectrum)
    assert plan.name == "gui spectrum test"
    assert plan.cam is main_window.controller.cam
    np.testing.assert_array_equal(plan.wl_list, [500, 600, 700])
