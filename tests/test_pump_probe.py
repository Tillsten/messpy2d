import pytest
import os
import pathlib
import os.path as osp
from unittest.mock import MagicMock

from MessPy.Plans import PumpProbePlan
from MessPy.ControlClasses import Controller, DelayLine
from MessPy.Config import config

config.testing = True
config.data_directory


def test_init():
    controller = Controller()
    controller.cam.set_shots(2)
    for i in range(2):
        controller.loop()


def test_functions():
    c = Controller()
    c.cam.get_bg()
    if c.shutter:
        c.shutter[0].open()
        assert c.shutter[0].is_open()
        c.shutter[0].close()
        assert not c.shutter[0].is_open()


def test_pump_probe():
    c = Controller()
    t_list = range(0, 10)
    cwls = [
        [
            0,
            300,
        ]
    ]
    c.cam.set_shots(2)
    pp = PumpProbePlan(
        controller=c,
        main_delay_line=c.delay_line,
        t_list=t_list,
        name="test",
        shots=2,
        center_wl_list=cwls,
    )
    c.plan = pp

    while pp.num_scans < 2:
        c.loop()
    assert pp.cam_data[0].completed_scans.shape[0] == pp.cam_data[0].scan


def test_pump_probe_uses_supplied_delay_line(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_directory", tmp_path)
    controller = Controller()
    primary_move = MagicMock()
    monkeypatch.setattr(controller.delay_line, "set_pos", primary_move)
    selected = MagicMock(spec=DelayLine)
    selected.get_pos.return_value = 123.0
    selected.moving = False

    plan = PumpProbePlan(
        controller=controller, main_delay_line=selected, t_list=[0.0], name="test"
    )
    assert plan.pre_state["delay"] == 123.0
    list(plan.move_delay_line(42.0))
    selected.set_pos.assert_called_once_with(42.0, do_wait=False)

    plan.restore_state()
    selected.set_pos.assert_called_with(123.0, do_wait=False)
    primary_move.assert_not_called()
