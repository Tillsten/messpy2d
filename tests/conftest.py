from unittest.mock import MagicMock

import pytest
from loguru import logger


@pytest.fixture
def gui_plan_window(request, qtbot, tmp_path, monkeypatch):
    from MessPy.Config import config
    from MessPy.ControlClasses import Controller, DelayLine
    from MessPy.MessPy2D import MainWindow

    monkeypatch.setattr(config, "testing", True)
    monkeypatch.setattr(config, "data_directory", tmp_path)
    monkeypatch.setattr(config, "exp_settings", {})
    monkeypatch.setattr(config, "save", lambda *args, **kwargs: None)

    controller = Controller()
    controller.cam.set_shots(2)
    monkeypatch.setattr(controller, "loop", lambda: None)
    if getattr(request, "param", False):
        device = MagicMock()
        device.name = "Second delay line"
        device.get_pos_fs.return_value = 0.0
        controller.delay_line_second = DelayLine(device)

    window = MainWindow(controller)
    qtbot.addWidget(window)
    yield window

    window.cleanup()
    window.controller_thread.wait(2000)


def pytest_sessionfinish(session, exitstatus):
    """Detach loguru sinks before interpreter shutdown.

    Instrument mocks register atexit save_state() calls that log through
    loguru. By the time atexit runs, pytest has already closed the captured
    stdout/stderr streams, so those log writes raise "I/O operation on
    closed file" and pytest-qt reports it as a non-zero exit. Removing the
    sinks here (while streams are still open) turns later log calls into
    no-ops instead of failures.
    """
    logger.remove()
