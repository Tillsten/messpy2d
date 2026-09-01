import pytest

from MessPy.Config import config
from MessPy.ControlClasses import Controller
from MessPy.MessPy2D import MainWindow

config.testing = True


@pytest.fixture
def main_window(qtbot, tmp_path):
    config.data_directory = tmp_path
    controller = Controller()
    controller.cam.set_shots(2)
    mw = MainWindow(controller)
    qtbot.addWidget(mw)
    yield mw
    mw.cleanup()
    mw.controller_thread.wait(2000)


def test_main_window_starts(main_window, qtbot):
    main_window.show()
    qtbot.waitExposed(main_window)
    assert main_window.windowTitle() == "Messpy-2D Edition"


def test_main_window_runs_loop(main_window, qtbot):
    main_window.show()
    qtbot.waitUntil(
        lambda: main_window.controller.cam.last_read is not None, timeout=3000
    )


def test_show_alignment_helpers(main_window, qtbot):
    main_window.show()

    main_window.show_alignment_helper()
    qtbot.addWidget(main_window._ah)
    assert main_window._ah.isVisible()

    main_window.show_signal_alignment_helper()
    qtbot.addWidget(main_window._sah)
    assert main_window._sah.isVisible()
