from typing import ClassVar, Optional, Literal

from attr import define, Factory
from qtpy.QtCore import Signal, Slot, QObject, QThread, QTimer
from Plans.PlanBase import Plan


@define
class PlanRunner(QObject):
    plan: Optional[Plan] = None
    state: Literal['running', 'paused', 'no_plan'] = 'no_plan'

    sigPlanStopped: ClassVar[Signal] = Signal(bool)
    sigPlanStarted: ClassVar[Signal] = Signal(bool)
    sigPlanPaused: ClassVar[Signal] = Signal(bool)

    def __attr_post_init__(self):
        super().__attr_post_init__()

    @Slot(Plan)
    def start_plan(self, plan: Plan):
        self.plan = plan
        self.state = 'running'
        self.sigPlanStarted.emit(True)
        if not plan.is_async:
            pass

    @Slot()
    def pause_plan(self):
        if self.plan:
            self.state = 'paused'
            self.sigPlanPaused.emit(True)

    @Slot()
    def resume_plan(self):
        if self.plan:
            self.state = 'running'
            self.sigPlanPaused.emit(False)

    @Slot
    def stop_plan(self):
        if self.plan:
            self.plan.stop_plan()
            self.sigPlanStopped.emit(True)
            self.state = 'no_plan'
