import json
import threading
import time
import typing
from pathlib import Path

import attr
import numpy as np
import pipython
from pipython import fastaligntools, pitools

from MessPy.Instruments.interfaces import ILissajousScanner
from MessPy.Instruments.sample_holder_PI.c843_cppyy import C843
from MessPy.Instruments.sample_holder_PI.newport_smc import NewPortStage

mag = pipython.GCSDevice()

dir = Path(__file__).parent
CONF_FILE = dir / "sample_holder_conf.json"

try:
    with open(CONF_FILE, 'r') as f:
        conf = json.load(f)
        POS_LIST = conf['pos_list']
except FileNotFoundError:
    POS_LIST = (0, 0)


@attr.s(auto_attribs=True)
class SampleHolder(ILissajousScanner):
    name: str = 'Pi Instruments Sampleholder'
    pos_home: tuple = POS_LIST
    has_zaxis: bool = True

    def __attrs_post_init__(self):
        t2 = threading.Thread(target=self.init_mag)
        t2.start()
        self.c843 = C843()
        t2.join()
        # self.set_pos_mm(*self.pos_home)
        self.z_axis = NewPortStage()
        self.z_axis.set_pos_mm(self.z_axis.get_home())

    def init_mag(self):
        mag.ConnectUSB('C-891.130300 SN 119030911')
        self.reset_motor()

    def reset_motor(self):
        mag.WGC(1, 1)
        mag.EAX('1', True)
        #mag.EAX('1', True)
        pitools.startup(mag)

        mag.VEL('1', 700)
        mag.ACC('1', 3000)
        mag.DEC('1', 3000)

    def set_pos_mm(self, x=None, y=None):
        if x is not None:
            mag.MOV('1', x)
        if y is not None:
            self.c843.move_mm(y)

    def get_pos_mm(self) -> tuple[float, float]:
        y = self.c843.get_pos_mm()
        x = mag.qPOS('1')['1']
        return x, y

    def is_moving(self) -> tuple[bool, bool]:
        a = self.c843.is_moving()
        b = mag.qMOV('1')['1']
        return a, b

    def get_zpos_mm(self) -> float:
        return self.z_axis.get_pos_mm()

    def set_zpos_mm(self, mm: float):
        self.z_axis.set_pos_mm(mm)

    def set_home(self):
        self.z_axis.set_home()
        p1, p2 = self.get_pos_mm()
        self.pos_home = (p1, p2)
        print(f'set_home: {self.pos_home[0]},{self.pos_home[1]}')
        with open(CONF_FILE, 'w') as f:
            json.dump(dict(pos_list=(p1, p2)), f)

    def get_home(self):
        return self.pos_home

    def start_contimove(self, x, y):
        self.do_move = True
        self.start_ramp(amp=x)
        self.thread = threading.Thread(target=self.do_contimove, args=(x, y))
        self.thread.start()

    def do_contimove(self, x_settings, y_settings):
        home = self.pos_home[1]
        y = y_settings/2.
        self.c843.move_mm(y + 1 + home)
        while True:
            pos = self.c843.get_pos_mm() - home
            if pos > y:
                self.c843.move_mm(home-y-1)
            elif pos < -y:
                self.c843.move_mm(home+y+1)
            time.sleep(0.02)

            if not self.do_move:
                break

    def stop_contimove(self):
        self.do_move = False
        self.stop_ramp()
        self.set_pos_mm(*self.pos_home)

    def start_ramp(self, amp=20, speed=150, ):
        print('Starting Ramp',  amp, speed)
        time = abs(2*amp/speed)
        time_step = 50e-6
        n_points = int(time / time_step)
        turn_time = int(0.04/time_step)
        print(mag.EAX('1', True))
        print(mag.SVO('1', True))
        print(mag.qEAX('1'))
        print(mag.qSVO('1'))

        offset = -amp/2+self.pos_home[0]
        msg = f'WAV 1 X RAMP {n_points} {amp} {offset} {n_points} 0 {turn_time} {n_points//2}'
        print(msg)
        mag.send(msg)
        mag.MOV('1', [offset])
        pitools.waitontarget(mag)
        mag.WGC(1, 0)
        mag.WGO(1, 1)

    def stop_ramp(self):
        mag.WGC(1, 1)
        pitools.waitonwavegen(mag, 1)
        try:

            mag.WGO(1, 0)

            mag.checkerror()
        except pipython.GCSError:
            pass
        self.reset_motor()


if __name__ == '__main__':
    sh = SampleHolder()
    # SampleHolder.init_mag(None)
    # SampleHolder.start_ramp(None)
#    while True:
#        mag.send('DIO 3 1')
#        mag.send('DIO 2 0')
#        time.sleep(0.3)
#        mag.send('DIO 3 0')
#        mag.send('DIO 2 1')
#        time.sleep(0.3)
#    sh.start_ramp()
    sh.start_contimove(20, 20)

    # print(sh.get_pos_mm())
    # sh.is_moving()
    #sh.set_pos_mm(-0, 80)
    # print(sh.is_moving())
