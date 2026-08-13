# -*- coding: utf-8 -*-
"""
Created on Wed Jun 04 19:06:42 2014

@author: tillsten
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Jun 03 15:41:22 2014

@author: tillsten
"""


import time
import attr
import serial
from PySide6.QtCore import QObject, Signal, QTimer, QMutex, QMutexLocker
from MessPy.Instruments.interfaces import IDelayLine


controller_states = {
    "0A": "NOT REFERENCED from reset",
    "0B": "NOT REFERENCED from HOMING",
    "0C": "NOT REFERENCED from CONFIGURATION",
    "0D": "NON REFERENCED from DISABLE",
    "0E": "NOT REFERENCED from READY",
    "0F": "NOT REFERENCED from MOVING",
    "10": "NOT REFERENCED ESP stage error",
    "11": "NOT REFERENCED from JOGGING",
    "14": "CONFIGURATION",
    "1E": "HOMING command from RS-232-C",
    "1F": "HOMING command by SMC-RC",
    "28": "MOVING",
    "32": "READY from HOMING",
    "33": "READY from MOVING",
    "34": "READY from DISABLE",
    "35": "READY from JOGGING",
    "3C": "DISABLE from READY",
    "3D": "DISABLE from MOVING",
    "3E": "DISABLE from JOGGING",
    "46": "JOGGING from READY",
    "47": "JOGGING from DISABLE",
}


states = """
0A NOT INITIALIZED: after reset
0B NOT INITIALIZED: after CONFIG state
0C NOT INITIALIZED: after INITIALAZING state
0D NOT INITIALIZED: after NOT_REFERENCED state
0E NOT INITIALIZED: after HOMING state
0F NOT INITIALIZED: after MOVING state
10 NOT INITIALIZED: after READY state
11 NOT INITIALIZED: after DISABLE state 
12 NOT INITIALIZED: after JOGGING state 
13 NOT INITIALIZED: error, Stage type not valid 
14 CONFIGURATION
1E INITIALAZING: launch by USB
1F INITIALAZING: launch by Remote Control
28 NOT_REFERENCED
32 HOMING: launch by USB
33 HOMING: launch by Remote Control
3C MOVING
46 READY: after MOVING state
47 READY: after MOVING state
48 READY: after DISABLE state
49 READY: after JOGGING state
50 DISABLE: after READY state
51 DISABLE: after MOVING state
52 DISABLE: after JOGGING state
5A JOGGING: after READY state
5B JOGGING: after DISABLE state
"""
controller_states = {}
for s in states.splitlines()[1:]:
    controller_states[s[:2]] = s[3:]


class DSignals(QObject):
    sigDegreesChanged = Signal(float)
    sigMovementStarted = Signal()
    sigMovementFinished = Signal()


@attr.s(auto_attribs=True)
class NewportDelay(IDelayLine):
    name: str = 'Newport AGP stage'
    comport: str = 'COM5'
    rot: serial.Serial = attr.ib()
    last_pos: float = 0
    pos_sign = -1.0
    min_pos_mm: float = 0.0
    max_pos_mm: float = 25.0
    lock: QMutex = attr.Factory(QMutex)

    _busy_cnt = 0
    """
    At least answer n-times with true for is_moving after calling move. Workaround since
    the controller sometimes answers wrongly after calling a move.
    """

    @rot.default
    def _default_rs(self):
        rot = serial.Serial(self.comport, baudrate=115200 * 8, xonxoff=1)
        rot.timeout = 3
        return rot

    def __attrs_post_init__(self):
        super(NewportDelay, self).__attrs_post_init__()
        with QMutexLocker(self.lock):
            state = self.controller_state()
            if state.startswith("DISABLE"):
                self.w("1MM1")
            elif state.startswith("NOT REFERENCED"):
                self.w(b"1RS")
                self.rot.write(b"1OR\r\n")
                while self.controller_state().startswith("HOMING"):
                    time.sleep(0.3)

        if self.last_pos != 0:
            self.move_mm(self.last_pos)

    def w(self, x):
        writer_str = f"{x}\r\n"
        self.rot.write(writer_str.encode("utf-8"))
        self.rot.timeout = 1

    def move_mm(self, pos):
        """Set absolute position of the roatation stage"""
        if isinstance(pos, str):
            pos = float(pos)
        setter_str = f"1PA{pos}\r\n"
        with QMutexLocker(self.lock):
            self.rot.write(setter_str.encode("utf-8"))
            self.rot.timeout = 3
            self._busy_cnt = 2

    def get_state(self) -> dict:
        return dict(last_pos=self.last_pos, home_pos=self.home_pos)

    def controller_state(self) -> str:
        self.w("1MM?")
        ans = self.rot.read_until(b"\r\n").decode()
        state = ans[ans.find("MM") + 2 : -2].upper()
        state = state.replace(" ", "0")
        return controller_states[state]

    def get_pos_mm(self):
        """Returns the position"""
        with QMutexLocker(self.lock):
            self.w("1TP")
            self.rot.timeout = 1
            try:
                ans = self.rot.read_until(b"\r\n")
                ans = ans.decode()
                self.last_pos = float(ans[ans.find("TP") + 2 : -2])
                return self.last_pos
            except ValueError:
                print(ans)
                return 0

    def is_moving(self):
        with QMutexLocker(self.lock):
            if self._busy_cnt > 0:
                self._busy_cnt -= 1
                return True
            return self.controller_state().startswith("MOVING")


if __name__ == "__main__":
    import time
    rs = NewportDelay(comport='COM5')
    print('change first')
    print(rs.get_pos_mm())
    print(rs.controller_state())
    rs.move_mm(100)
    print(rs.is_moving())
    #rs.w("1SR?")
    #print(rs.rot.readall())
    #rs.w("1SL?")
    #print(rs.rot.readall())
    #print(rs.controller_state())
# rs.set_pos(1)
