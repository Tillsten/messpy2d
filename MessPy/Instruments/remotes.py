from xmlrpc.client import ServerProxy

import attr
from wrapt import synchronized

from MessPy.Config import config
from MessPy.Instruments.interfaces import ILissajousScanner, IRotationStage, IShutter

config.rot_server = 'http://130.133.30.223:8003'
rot = ServerProxy(config.rot_server)

config.shutter_server = 'http://130.133.30.223:8002'
shutter = ServerProxy(config.shutter_server)


@attr.s
class RotationStage(IRotationStage):
    name = attr.ib('xmlrpc-RotStage')

    @synchronized
    def set_degrees(self, deg: float):
        deg = float(deg)
        rot.set_pos(deg)
        # self.sigDegreesChanged.emit(deg)

    @synchronized
    def get_degrees(self) -> float:
        pos = rot.get_pos()
        return pos

    @synchronized
    def is_moving(self):
        return rot.is_moving()


@attr.s
class Shutter(IShutter):
    name = attr.ib('xmlrpc-Shutter')

    @synchronized
    def is_open(self) -> bool:
        return shutter.is_open()

    @synchronized
    def toggle(self):
        shutter.toggle()
        self.sigShutterToggled.emit(self.is_open())


config.fh_server = 'http://130.133.30.223:8001'
fh = ServerProxy(config.fh_server, allow_none=True)


@attr.s
class Faulhaber(ILissajousScanner):
    name = attr.ib('xmlrpc-SampleHoler')
    pos_home = attr.ib()
    has_zaxis = True

    def __attrs_post_init__(self):
        fh.reset_motor()

    @pos_home.default
    def _pos_home_default(self):
        return fh.get_home()

    @synchronized
    def is_moving(self) -> tuple[bool, bool]:
        return fh.is_xy_moving()

    @synchronized
    def set_pos_mm(self, x=None, y=None):
        if x:
            x = float(x)
        if y:
            y = float(y)
        fh.set_pos_mm(x, y)

    @synchronized
    def get_pos_mm(self) -> tuple[float, float]:
        return fh.get_pos_mm()

    @synchronized
    def start_contimove(self, *args):
        fh.start_contimove(*args)

    @synchronized
    def stop_contimove(self, *args):
        fh.stop_contimove()

    @synchronized
    def set_home(self):
        fh.set_home()
        self.pos_home = fh.get_home()

    @synchronized
    def get_zpos_mm(self) -> float:
        return fh.get_zpos_mm()

    @synchronized
    def set_zpos_mm(self, mm):
        fh.set_zpos_mm(mm)

    @synchronized
    def is_zmoving(self) -> bool:
        return fh.is_zmoving()
#sh = Shutter()


if __name__ == '__main__':
    sh = Faulhaber()
    print(sh.get_pos_mm())
    sh.set_pos_mm(10, 10)
    print(sh.pos_home)
    #sh = Shutter()
    # sh.toggle()
    #rs = RotationStage()
    # print(rs.get_degrees())
    # rs.set_degrees(30)
    # print(rs.is_moving())
