
import attr
import numpy as np

from MessPy.Instruments.interfaces import ICam


@attr.s(auto_attribs=True)
class Parameter:
    name: str
    upper_lim: float = np.inf
    lower_lim: float = -np.inf
    start_val: float | None = None


class Manipulator:
    params = list[Parameter]

    def apply(self):
        raise NotImplementedError


class ObjectivDetector:
    """
    pass
    """

    @staticmethod
    def from_cam(cam: ICam, kind: str) -> 'ObjectivDetector':
        pass

    def eval(self):
        pass


@attr.s
class OptimizePlan:
    mani: Manipulator
