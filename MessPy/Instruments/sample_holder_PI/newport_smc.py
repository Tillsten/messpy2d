import json
import time
from pathlib import Path

import serial

DIR = Path(__file__).parent

ERRORS = {"@": "",
          "A": "Unknown message code or floating point controller address.",
          "B": "Controller address not correct.",
          "C": "Parameter missing or out of range.",
          "D": "Execution not allowed.",
          "E": "home sequence already started.",
          "I": "Execution not allowed in CONFIGURATION state.",
          "J": "Execution not allowed in DISABLE state.",
          "H": "Execution not allowed in NOT REFERENCED state.",
          "K": "Execution not allowed in READY state.",
          "L": "Execution not allowed in HOMING state.",
          "M": "Execution not allowed in MOVING state.",
          }

positioner_errors = {
    0b1000000000: '80 W output power exceeded',
    0b0100000000: 'DC voltage too low',
    0b0010000000: 'Wrong ESP stage',
    0b0001000000: 'Homing time out',
    0b0000100000: 'Following error',
    0b0000010000: 'Short circuit detection',
    0b0000001000: 'RMS current limit',
    0b0000000100: 'Peak current limit',
    0b0000000010: 'Positive end of run',
    0b0000000001: 'Negative end of run',
}

controller_states = {
    '0A': 'NOT REFERENCED from reset.',
    '0B': 'NOT REFERENCED from HOMING.',
    '0C': 'NOT REFERENCED from CONFIGURATION.',
    '0D': 'NOT REFERENCED from DISABLE.',
    '0E': 'NOT REFERENCED from READY.',
    '0F': 'NOT REFERENCED from MOVING.',
    '10': 'NOT REFERENCED ESP stage error.',
    '11': 'NOT REFERENCED from JOGGING.',
    '14': 'CONFIGURATION.',
    '1E': 'HOMING commanded from RS-232-C.',
    '1F': 'HOMING commanded by SMC-RC.',
    '28': 'MOVING.',
    '32': 'READY from HOMING.',
    '33': 'READY from MOVING.',
    '34': 'READY from DISABLE.',
    '35': 'READY from JOGGING.',
    '3C': 'DISABLE from READY.',
    '3D': 'DISABLE from MOVING.',
    '3E': 'DISABLE from JOGGING.',
    '46': 'JOGGING from READY.',
    '47': 'JOGGING from DISABLE.',
}

TERM = b'\r\n'


class NewPortStage:
    def __init__(self):
        self.port = serial.Serial('COM12', baudrate=9600 * 6, timeout=2,
                                  xonxoff=True,
                                  )
        self.port.flush()
        self.w(b'1MM1')
        if (DIR / 'SMC_home.json').exists():
            d = json.load((DIR / 'SMC_home.json').open())
            self.home_pos = d['home']
        else:
            self.home_pos = 15

        if self.get_status().startswith('NOT REFERENCED'):
            self.ref()
            while self.get_status().startswith('HOMING'):
                time.sleep(0.5)

    def w(self, s: bytes):
        self.port.write(s + TERM)

    def rl(self):
        return self.port.read_until(TERM)[:-2]

    def get_status(self) -> str:
        self.w(b'1TS')
        rl = self.rl()
        return controller_states[rl.decode('ASCII')[-2:]]

    def set_pos_mm(self, mm : float):
        self.w(b'1PA%.3f' % mm)

    def get_pos_mm(self) -> float:
        self.w(b'1TP')
        rl = self.rl()
        return float(rl[3:])

    def is_moving(self) -> bool:
        return self.get_status() == 'MOVING.'

    def ref(self):
        self.w(b'1OR')

    def set_home(self):
        pos = self.get_pos_mm()
        self.home_pos = pos
        with (DIR / 'SMC_home.json').open('w') as f:
            json.dump({'home': pos}, f)

    def get_home(self) -> float:
        return self.home_pos

if __name__ == '__main__':
    np = NewPortStage()
    print(np.get_status())
    print(np.get_pos_mm())
    np.set_home()
