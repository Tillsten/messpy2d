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


from functools import cached_property
from MessPy.Instruments.interfaces import IRotationStage
from PySide6.QtCore import QObject, Signal, QTimer

import serial
import attr
import time
from threading import Lock

from loguru import logger

try:
    rs.s.close()
except NameError:
    pass


controller_states = {
    "0A": "NOT REFERENCED from reset",
    "0B": "NOT REFERENCED from HOMING",
    "0C": "NOT REFERENCED from CONFIGURATION",
    "0D": "NON REFERENCED from DISABLE",
    "0E": "NOT REFERENCED from READY",
    "0F": "NOT REFERENCED from MOVING",
    "10": "NOT REFERENCED no parameters.",
    "14": "CONFIGURATION",
    "1E": "HOMING",
    "28": "MOVING",
    "32": "READY from HOMING",
    "33": "READY from MOVING",
    "34": "READY from DISABLE",
    "3C": "DISABLE from READY",
    "3D": "DISABLE from MOVING",
}


class RotSignals(QObject):
    sigDegreesChanged = Signal(float)
    sigMovementStarted = Signal(float, float)
    sigMovementFinished = Signal()


@attr.s(auto_attribs=True)
class RotationStage(IRotationStage):
    name: str = "Rotation Stage"
    comport: str = "COM11"
    offset: float = 180
    last_pos: float = 0
    lock: Lock = attr.Factory(Lock)
    signals: RotSignals = attr.Factory(RotSignals)

    @cached_property
    def rot(self):
        return serial.Serial(self.comport, baudrate=115200 * 8, xonxoff=True, timeout=2)

    def __attrs_post_init__(self):
        super(RotationStage, self).__attrs_post_init__()
        logger.info("Connecting %s"%(self.name))
        state = self.controller_state()        
        logger.info(f"Starting state: {state}")
        if state.startswith("DISABLE"):
            logger.info(f"Enable")
            self.w("1MM1")
            
        elif state.startswith("NOT REFERENCED"):
            #self.w(b"1RS")
            self.w("1OR")
            time.sleep(0.3)
            logger.info("Start Homing")
            
            while True:
                state = self.controller_state()
                print(state)                
                time.sleep(0.3)
                if state.startswith('READY'):
                    break
            logger.info("Homing finnished")
        logger.info(f"State after init: {self.controller_state()}, Postion: {self.get_degrees()}")
        #if self.last_pos != 0:
        #    self.set_degrees(self.last_pos)

    def w(self, x):
        assert x is not bytes

        writer_str = f"{x}\r\n"
        self.rot.write(writer_str.encode("utf-8"))
        #self.rot.timeout = 1

    def set_degrees(self, pos):
        """Set absolute position of the roatation stage"""
        cur_pos = self.get_degrees()
        if isinstance(pos, str):
            pos = float(pos)
        with self.lock:
            self.w(f"1PA{pos+self.offset}")
        logger.info(f"Starting Move to {pos}")
        self.last_pos = pos


        self.signals.sigMovementStarted.emit(pos, cur_pos)
        self._checker = QTimer.singleShot(100, self.check_moving)
        
    def check_moving(self):
        if (moving :=  self.is_moving()):
            self.signals.sigDegreesChanged.emit(self.get_degrees())
            QTimer.singleShot(200, self.check_moving)

        else:
            self.signals.sigDegreesChanged.emit(self.get_degrees())
            self.signals.sigMovementFinished.emit()


    def get_state(self) -> dict:
        return dict(last_pos=self.last_pos)

    def controller_state(self) -> str:
        with self.lock:
            self.w("1MM?")        
            ans = self.rot.read_until(b"\r\n").decode()
        logger.debug("Asked for stateL Got ans %s"%ans)
        state = ans[ans.find("MM") + 2 : -2].upper()
        state = state.replace(" ", "0")
        return controller_states[state]

    def get_degrees(self):
        """Returns the position"""
        with self.lock:
            self.w("1TP")        
            ans = self.rot.read_until(b"\r\n")
        logger.debug("Asked for pos. Got ans %s"%ans)
        ans = ans.decode()
        return float(ans[ans.find("TP") + 2 : -2]) - self.offset

    def is_moving(self):
        return self.controller_state().startswith("MOVING")


if __name__ == "__main__":
    import time

    rs = RotationStage(comport="COM4")
    print("change first")
    rs.set_degrees(-64)
    time.sleep(8)
    deg = rs.get_degrees()
    print(f"first pol:{deg}")
    rs.set_degrees(80)
    time.sleep(8)
    deg = rs.get_degrees()
    print(f"second pol:{deg}")

# rs.set_pos(1)
