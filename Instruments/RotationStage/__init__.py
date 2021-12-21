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

try:
    rs.s.close()
except NameError:
    pass

import time
import attr
import serial
from qtpy.QtCore import QObject, Signal, QTimer
from Instruments.interfaces import IRotationStage

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


class RotSignals(QObject):
    sigDegreesChanged = Signal(float)
    sigMovementStarted = Signal(float, float)
    sigMovementFinished = Signal()


@attr.s(auto_attribs=True)
class RotationStage(IRotationStage):
    name: str = 'Rotation Stage'
    comport: str = 'COM11'
    rot: serial.Serial = attr.ib()
    offset: float = 180
    last_pos: float = 0
    signals: RotSignals = attr.Factory(RotSignals)

    @rot.default
    def _default_rs(self):
        rot = serial.Serial(self.comport, baudrate=115200 * 8, xonxoff=1)
        rot.timeout = 3
        return rot

    def __attrs_post_init__(self):
        super(RotationStage, self).__attrs_post_init__()
        state = self.controller_state()
        print(state)
        if state.startswith('DISABLE'):
            self.w('1MM1')

            print(self.controller_state())
        elif state.startswith("NOT REFERENCED"):
            self.w(b'1RS')
            self.rot.write(b'1OR\r\n')
            while self.controller_state().startswith('HOMING'):
                time.sleep(0.3)

        if self.last_pos != 0:
            self.set_degrees(self.last_pos)


    def w(self, x):
        writer_str = f'{x}\r\n'
        self.rot.write(writer_str.encode('utf-8'))
        self.rot.timeout = 1

    def set_degrees(self, pos):
        """Set absolute position of the roatation stage"""
        cur_pos = self.get_degrees()
        if isinstance(pos, str):
            pos = float(pos)
        setter_str = f'1PA{pos+self.offset}\r\n'
        self.rot.write(setter_str.encode('utf-8'))
        self.rot.timeout = 3
        self.last_pos = pos
        if self.signals.thread().eventDispatcher() != 0:
            self.signals.sigMovementStarted.emit(pos, cur_pos)
            self._checker = QTimer()
            self._checker.setSingleShot(True)
            self._checker.timeout.connect(self.check_moving)
            self._checker.start(200)

    def check_moving(self):
        if self.is_moving():
            self.signals.sigDegreesChanged.emit(self.get_degrees())
            self._checker.start(200)
        else:
            self.signals.sigDegreesChanged.emit(self.get_degrees())
            self.signals.sigMovementFinished.emit()

    def get_state(self) -> dict:
        return dict(last_pos=self.last_pos)

    def controller_state(self) -> str:
        self.w('1MM?')
        ans = self.rot.read_until(b'\r\n').decode()
        state = ans[ans.find("MM") + 2:-2].upper()
        state = state.replace(' ', '0')
        return controller_states[state]

    def get_degrees(self):
        """Returns the position"""
        self.w('1TP')
        self.rot.timeout = 0.5
        ans = self.rot.read_until(b'\r\n')
        ans = ans.decode()
        return float(ans[ans.find("TP") + 2:-2])-self.offset

    def is_moving(self):
        return self.controller_state().startswith('MOVING')





if __name__ == '__main__':
    import time
    rs = RotationStage(comport='COM6')
    print('change first')
    rs.set_degrees(0)
    time.sleep(8)
    deg = rs.get_degrees()
    print(f'first pol:{deg}')
    rs.set_degrees(80)
    time.sleep(8)
    deg = rs.get_degrees()
    print(f'second pol:{deg}')

# rs.set_pos(1)
