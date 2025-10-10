"""
This file scans the folding mirrors to find the best alignment to
maximize the AOM efficiency.
"""

from typing import ClassVar, Generator

from PySide6.QtCore import Signal
import numpy as np
from MessPy.Instruments.interfaces import IRotationStage, ICam
from MessPy.Instruments.dac_px import AOM
from .PlanBase import Plan
from attr import Factory, dataclass

from loguru import logger


@dataclass
class ScanFoldingMirrors(Plan):
    aom: AOM
    cam: ICam
    estimated_best_angle: float = 1.0
    angle_range: float = 0.3
    steps: int = 10
    second_mirror_range: float = 0.3
    second_mirror_steps: int = 10
    shots: int = 20
    name: str = "Scan Folding Mirrors"
    data: dict[tuple[float, float], float] = Factory(dict)
    state: dict = Factory(dict)
    plan_shorthand: ClassVar[str] = "Scan FoldingMirrors"

    sigPointRead: ClassVar[Signal] = Signal()
    sigAngle1Changed: ClassVar[Signal] = Signal(float)

    def __attrs_post_init__(self):
        assert hasattr(self.aom, "fm1"), "AOM has no folding mirrors"
        assert hasattr(self.aom, "fm2"), "AOM has no folding mirrors"
        self.state['FM1'] = self.aom.fm1.get_degrees()
        self.state['FM2'] = self.aom.fm2.get_degrees()
        gen = self.make_step_generator()
        self.make_step = lambda: next(gen)
        return super().__attrs_post_init__()
    
    def restore_state(self):
        self.aom.fm1.set_degrees(self.state['FM1'])
        self.aom.fm2.set_degrees(self.state['FM2'])
        return super().restore_state()
    
    def make_step_generator(self):
        fm1: IRotationStage = self.aom.fm1  # type: ignore[attr-defined]
        zero_order_angle1 = fm1.get_degrees()
        fm2: IRotationStage = self.aom.fm2  # type: ignore[attr-defined]
        zero_order_angle2 = fm2.get_degrees()

        logger.info(
            f"Zero order angle of first folding mirror: {zero_order_angle1:.2f}°"
        )
        logger.info(
            f"Zero order angle of second folding mirror: {zero_order_angle2:.2f}°"
        )

        angle1 = (
            np.linspace(-self.angle_range / 2, self.angle_range / 2, self.steps)
            + self.estimated_best_angle
        )
        angle2 = (
            np.linspace(
                -self.second_mirror_range / 2,
                self.second_mirror_range / 2,
                self.second_mirror_steps,
            )
            + self.estimated_best_angle
        )
        for ang1 in angle1:
            for ang2 in angle2:
                yield (
                    fm1.set_degrees(zero_order_angle1 + ang1),
                    fm2.set_degrees(zero_order_angle2 + ang2),
                )
                logger.info(f"Moving to {zero_order_angle1 + ang1} and {zero_order_angle2 + ang2}")
                while fm1.is_moving() or fm2.is_moving():
                    yield
                sig = self.measure_point()
                self.data[(ang1, ang2)] = sig
                self.sigPointRead.emit()
                logger.info(
                    f"Angle1: {ang1:.3f}°, Angle2: {ang2:.3f}°, Signal: {sig:.1f}"
                )
                yield

    def measure_point(self):
        reading = self.cam.get_spectra(frames=2)[0]
        sum_sig = reading["Probe2"].mean.sum()
        return sum_sig
