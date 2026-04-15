from typing import Literal
from serial import Serial
from loguru import logger
from threading import Lock

import time
# Open serial port


def double(x):
    for i in x:
        yield i
        yield i


class DG535:
    channels = {
        0: 'Trigger Input',
        1: 'T0 Output',
        2: 'A Output',
        3: 'B Output',
        4: 'AB and -AB Outputs',
        5: 'C Output',
        6: 'D Output',
        7: 'CD and -CD Outputs',
    }

    channel_to_int = {
        'A': 2,
        'B': 3,
        'C': 5,
        'D': 6,
    }

    def __init__(self, port='COM4'):
        self.lock = Lock()
        s = Serial(port, 9600*12, timeout=1)
        s.write(b'++mode 1\n')
        s.write(b'++addr 15\n')
        s.write(b'++eot_enable 0\n')
        s.write(b'++eoi 1\n')
        s.write(b'++auto 1\n')
        self.port = s
        self.cmd("ES\n")

    def cmd(self, cmd):
        cmd = 'ES\n' + cmd
        with self.lock:
            logger.info("CMD %s sent"%cmd)
            double_cmd = "".join(list(double(cmd)))
            self.port.write(double_cmd.encode('ascii')[:-1])
            time.sleep(0.1)

    def set_delay(self, channel: Literal['A', 'B', 'C', 'D'], delay_ns: float):
        """Set delay for channel in seconds"""
        delay = delay_ns
        channel_int = self.channel_to_int[channel]
        self.cmd(f'DT {channel_int}, 1, {delay: .2f}E-9\n')
        disp = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'T0': 4}
        
        self.cmd(f'DL 1, 0, {disp[channel]}\n')


if __name__ == '__main__':
    dg = DG535(port='COM4')
    dg.cmd('DS\n')
    for i in range(100):
        for j in range(20):
            dg.set_delay('A', j*10)

            time.sleep(0.5)

