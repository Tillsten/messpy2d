import sys
import threading
import time
import typing

import attr
import numpy as np
from smaract import ctl

from MessPy.Instruments.interfaces import ILissajousScanner


@attr.define
class SmarActXYZ(ILissajousScanner):
    name: str = 'SmarAct XYZ'
    handle: int = attr.ib(init=False)
    channels: dict[str, int] = {"x": 0, "y": 2, "z": 1}
    has_zaxis: bool = True

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        buffer = ctl.FindDevices()
        if len(buffer) == 0:
            raise OSError("MCS2 no devices found.")
        locators = buffer.split("\n")
        self.handle = ctl.Open(locators[0])

        for c, idx in self.channels.items():
            ctl.SetProperty_i32(
                self.handle, idx, ctl.Property.MAX_CL_FREQUENCY, 10000)
            ctl.SetProperty_i32(self.handle, idx, ctl.Property.HOLD_TIME, 50)
            move_mode = ctl.MoveMode.CL_ABSOLUTE
            ctl.SetProperty_i32(
                self.handle, idx, ctl.Property.MOVE_MODE, move_mode)
            ctl.SetProperty_i64(
                self.handle, idx, ctl.Property.MOVE_VELOCITY, 20_000_000_000)
            # Set move acceleration to 20 mm/s2.
            ctl.SetProperty_i64(
                self.handle, idx, ctl.Property.MOVE_ACCELERATION, 10_000_000_000_000)
            ctl.SetProperty_i32(
                self.handle, idx, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)

    def get_state(self):
        return dict(pos_home=self.pos_home)

    def get_pos_mm_abs(self) -> tuple[float, float]:
        pos = []
        for c in ['x', 'y']:
            position = ctl.GetProperty_i64(
                self.handle, self.channels[c], ctl.Property.POSITION)
            pos.append(position * 1e-9)
        return tuple(pos)

    def get_pos_mm(self) -> tuple[float, float]:
        x, y = self.get_pos_mm_abs()
        return x-self.pos_home[0], y-self.pos_home[1]

    def set_pos_mm_abs(self, x=None, y=None):
        if x is not None:
            ctl.Move(self.handle, self.channels['x'], round(x/1e-9), 0)
        if y is not None:
            ctl.Move(self.handle, self.channels['y'], round(y/1e-9), 0)

    def set_pos_mm(self, x: float | None=None, y:float | None=None):
        if x is not None:
            x = x + self.pos_home[0]
        if y is not None:
            y += self.pos_home[1]
        self.set_pos_mm_abs(x, y)

    def is_moving(self) -> tuple[bool, bool]:
        state = ctl.GetProperty_i32(
            self.handle, self.channels['x'], ctl.Property.CHANNEL_STATE)
        x_moving = state & ctl.ChannelState.ACTIVELY_MOVING
        state = ctl.GetProperty_i32(
            self.handle, self.channels['y'], ctl.Property.CHANNEL_STATE)
        y_moving = state & ctl.ChannelState.ACTIVELY_MOVING
        return bool(x_moving), bool(y_moving)

    def set_home(self):
        x, y = self.get_pos_mm_abs()
        self.pos_home = (x, y)
        self.save_state()

    def set_zpos_mm(self, mm: float):
        ctl.Move(self.handle, self.channels['z'], round(mm/1e-9), 0)

    def get_zpos_mm(self) -> float:
        position = ctl.GetProperty_i64(
            self.handle, self.channels['z'], ctl.Property.POSITION)
        return position*1e-9

    def is_zmoving(self) -> bool:
        state = ctl.GetProperty_i32(
            self.handle, self.channels['z'], ctl.Property.CHANNEL_STATE)
        return state & ctl.ChannelState.ACTIVELY_MOVING

    def parse_error(self, e: ctl.Error):
        return "MCS2 {}: {}, error: {} (0x{:04X}) in line: {}.".format(e.func, ctl.GetResultInfo(e.code),
                                                                       ctl.ErrorCode(
                                                                           e.code).name, e.code,
                                                                       sys.exc_info(
        )[-1].tb_lineno
        )

    def start_contimove(self, x_mm, y_mm):
        self.t0 = time.time()
        self.contimove = True
        self.set_pos_mm(0, y_mm)
        while any(self.is_moving()):
            pass
        self.conti_thread = threading.Thread(target=self._do_contimove, args=(x_mm, y_mm))
        self.conti_thread.start()
        #self._do_contimove(1, 1)

    def stop_contimove(self):
        self.contimove = False

    def _do_contimove(self, x_mm, y_mm):
        x = 0
        while self.contimove:
            print(self.get_pos_mm())
            t = time.time() - self.t0
            #if x == 0:
            #    x = 1
            #    y = 3
            x = y_mm*np.sin(2*np.pi*t/2)
            y = x_mm*np.cos(2 * np.pi * t / 2)
            #else:
            #    x = 0
            #    y = 0
            print('jo', x, y)
            self.set_pos_mm(x, y)
            time.sleep(0.01)


if __name__ == '__main__':
    stage = SmarActXYZ(name='SmartAct')
    print(stage.get_pos_mm())
    print(stage.is_moving())
    # stage.set_zpos_mm(0)
    for i in range(50):
        stage.set_pos_mm(None, i * 0.1)
        for j in range(2):
            stage.set_pos_mm(80*j+10, i * 0.1)
            while any(stage.is_moving()):
                print(stage.get_pos_mm())
                time.sleep(0.1)
    print(stage.get_pos_mm())

    print(stage.is_zmoving())
    print(stage.get_zpos_mm())
