import logging
from xmlrpc.client import ServerProxy

import attr
import wrapt

from MessPy.Config import config
from MessPy.Instruments.interfaces import IDelayLine

config.dl_server = 'http://130.133.30.223:8000'

dlproxy = ServerProxy(config.dl_server)


@attr.s(auto_attribs=True)
class DelayLine(IDelayLine):
    name: str = f"Remote DelayLine xmlrpc {config.dl_server}"
    pos_sign: float = -1
    home_pos: float = dlproxy.get_home()

    def __init__(self):
        super().__init__(name=self.name, pos_sign=-1)

    @wrapt.synchronized
    def move_mm(self, mm, *args, **kwargs):
        return dlproxy.move_mm(mm)

    @wrapt.synchronized
    def get_pos_mm(self):
        return dlproxy.get_mm()

    @wrapt.synchronized
    def is_moving(self):
        return dlproxy.is_moving()

    @wrapt.synchronized
    def def_home(self):
        self.home_pos = self.get_pos_mm()
        return dlproxy.def_home()


logging.info("Init xmlrpc delayline")
_dl = DelayLine()
if __name__ == '__main__':

    dl.is_moving()
    print(dlproxy.get_home(), dl.home_pos)
    dl.move_mm(5)
# print(dl.def_home())
