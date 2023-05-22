from MessPy.Instruments.interfaces import IDelayLine
from MessPy.Instruments.delay_dg535.delay_gen import DG535
import attr


@attr.s(auto_attribs=True, kw_only=True)
class GeneratorDelayline(IDelayLine):
    name: str = 'GeneratorDelayline'
    generator: DG535 = attr.Factory(DG535)
    last_set: float = 0
    home_pos: float = 772_691

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.last_set = 0

    def move_mm(self, x: float):
        self.pos = x

    def is_moving(self):
        return False

    def get_pos_mm(self):
        return 0

    def get_pos_fs(self) -> float:
        return self.last_set

    def def_home(self):
        print('new_home')
        self.home_pos = -self.last_set + self.home_pos
        print(self.home_pos)
        self.last_set = 0

    def move_fs(self, fs, do_wait=False, *args, **kwargs):
        """
        For the delay generator we use ns seconds as base unit for the ScanSetting
        instead of ps. Hence we also have a factor 1000 here since DG gen takes
        ns.


        """
        self.last_set = fs
        self.generator.set_delay('A', -fs + self.home_pos)


if __name__ == '__main__':
    import time
    g = GeneratorDelayline()
    g.home_pos = 722_581
    g.move_fs(0)
