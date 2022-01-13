import asyncio
from asyncio import Task
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Tuple, Optional, Callable, Generator

import attr
import json
import time
from qtpy.QtCore import QObject, Signal, Slot

from Config import config
from Instruments.interfaces import IDevice

sample_parameters = {'name': 'Sample', 'type': 'group', 'children': [
    dict(name='Sample', type='str', value=''),
    dict(name='Solvent', type='list', values=config.list_of_solvents),
    dict(name='Excitation', type='str'),
    dict(name='Thickness', type='str'),
    dict(name='Annotations', type='str'),
    dict(name='Users:', type='str'),
]}


@attr.s(auto_attribs=True)
class TimeTracker(QObject):
    start_time: float = attr.Factory(time.time)
    scan_start_time: float = attr.Factory(time.time)
    scan_end_time: Optional[float] = None
    point_start_time: float = attr.Factory(time.time)
    point_end_time: Optional[float] = None

    sigTimesUpdated: ClassVar[Signal] = Signal(str)

    def __attrs_post_init__(self):
        super(TimeTracker, self).__init__()

    @property
    def total_duration(self):
        return time.time() - self.start_time

    @property
    def scan_duration(self):
        if self.scan_end_time is not None:
            return self.scan_end_time - self.scan_start_time

    @property
    def point_duration(self):
        if self.point_end_time is not None:
            return self.point_end_time - self.point_start_time

    @Slot()
    def scan_starting(self):
        self.scan_start_time = time.time()

    @Slot()
    def scan_ending(self):
        self.scan_end_time = time.time()
        self.sigTimesUpdated.emit(self.as_string())

    @Slot()
    def point_starting(self):
        self.point_start_time = time.time()

    @Slot()
    def point_ending(self):
        self.point_end_time = time.time()
        self.sigTimesUpdated.emit(self.as_string())

    def as_string(self) -> str:
        s = f"""
        <h4>Time-Information</h4>
        Total Time: {timedelta(seconds=self.total_duration)}
        """
        if self.point_end_time:
            s += f"Time per Point: {timedelta(seconds=self.point_duration)}\n"
        if self.scan_end_time:
            s += f"Time per Scan: {timedelta(seconds=self.scan_duration)}\n"
        return s


@attr.s(auto_attribs=True, kw_only=True)
class Plan(QObject):
    plan_shorthand: ClassVar[str]

    name: str = ''
    meta: dict = attr.Factory(dict)
    status: str = ''
    creation_dt: datetime = attr.Factory(datetime.now)
    is_async: bool = False
    time_tracker: TimeTracker = attr.Factory(TimeTracker)

    sigPlanFinished: ClassVar[Signal] = Signal()
    sigPlanStarted: ClassVar[Signal] = Signal()
    sigPlanStopped:  ClassVar[Signal] = Signal()

    def __attrs_post_init__(self):
        super(Plan, self).__init__()

    def get_file_name(self) -> Tuple[Path, Path]:
        """Builds the filename and the metafilename"""
        date_str = self.creation_dt.strftime("%y-%m-%d %H_%M")
        name = f"{date_str} {self.name}.{self.plan_shorthand}"
        meta_name = f"{date_str} {self.name}.{self.plan_shorthand}"
        p = Path(config.data_directory)
        if not p.exists():
            raise IOError("Data path in config not existing")
        if (p / name).with_suffix('.json').exists():
            name = name + "_0"
        return (p / name).with_suffix('.messpy'), (p / meta_name).with_suffix('.json')

    def save_meta(self):
        """Saves the metadata in the metafile"""
        self.get_app_state()
        if self.meta is not None:
            _, meta_file = self.get_file_name()
            with meta_file.open('w') as f:
                json.dump(self.meta, f)

    def get_app_state(self):
        """Collects all devices states."""
        for i in IDevice.registered_devices:
            self.meta[i.name] = i.get_state()

    @Slot()
    def stop_plan(self):
        self.sigPlanStopped.emit()


@attr.s(auto_attribs=True, kw_only=True)
class ScanPlan(Plan):
    sigScanStarted: ClassVar[Signal] = Signal()
    sigScanFinished: ClassVar[Signal] = Signal()

    cur_scan: int = 0
    max_scan: int = 1_000_000
    stop_after_scan: bool = False
    make_step: Callable = attr.ib()

    @make_step.default
    def _prime_gen(self):
        return self.make_step_generator().__next__

    def __attrs_post_init__(self):
        super(ScanPlan, self).__attrs_post_init__()
        self.sigScanStarted.connect(self.time_tracker.scan_starting)
        self.sigScanFinished.connect(self.time_tracker.scan_ending)

    def pre_scan(self) -> Generator:
        yield True

    def setup_plan(self) -> Generator:
        yield True

    def post_plan(self) -> Generator:
        yield True

    def make_step_generator(self):
        self.sigPlanStarted.emit()
        yield from self.setup_plan()
        while self.cur_scan < self.max_scan and not self.stop_after_scan:
            yield from self.pre_scan()
            self.sigScanStarted.emit()
            yield from self.scan()
            self.sigScanFinished.emit()
            yield from self.post_scan()
            self.cur_scan += 1
        yield from self.post_plan()
        self.sigPlanFinished.emit()

    def scan(self) -> Generator:
        raise NotImplementedError

    def post_scan(self) -> Generator:
        yield True

import asyncio


@attr.define
class AsyncPlan(Plan):
    is_async: bool = True
    task: Task = attr.ib()

    sigTaskCreated: ClassVar[Signal] = Signal()

    async def plan(self):
        pass

    @task.default
    def create_task(self):
        loop = asyncio.get_event_loop()
        return loop.create_task(self.plan(), name=self.name)

    def stop_plan(self):
        self.task.cancel()
        return super().stop_plan()
