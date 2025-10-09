import asyncio
from functools import cached_property
import json
import time
import threading
from asyncio import Task
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Tuple, Optional, Callable, Generator, Any

from loguru import logger
import h5py
import attr
from PySide6.QtCore import QObject, Signal, Slot, QThread
from numpy import ndarray

from MessPy.Config import config
from MessPy.Instruments.interfaces import IDevice

sample_parameters = {
    "name": "Sample",
    "type": "group",
    "children": [
        dict(name="Sample", type="str", value=""),
        dict(name="Solvent", type="str", value=""),
        dict(name="Excitation", type="str"),
        dict(name="Thickness", type="str"),
        dict(name="Annotations", type="str"),
        dict(name="Users:", type="str"),
    ],
}


@attr.s(auto_attribs=True)
class TimeTracker(QObject):
    """Class to track times for scans and points."""

    start_time: float = attr.Factory(time.time)
    scan_start_time: float = 0
    scan_end_time: Optional[float] = None
    scan_duration: Optional[float] = None
    point_start_time: float = 0
    point_end_time: Optional[float] = None
    point_duration: Optional[float] = None

    sigTimesUpdated: ClassVar[Signal] = Signal(str)

    def __attrs_post_init__(self):
        super(TimeTracker, self).__init__()

    @property
    def total_duration(self):
        """Time elapsed since start of scan."""
        return time.time() - self.start_time

    @Slot()
    def scan_starting(self):
        """Record start time of scan."""
        self.scan_start_time = time.time()
        self.scan_end_time = None

    @Slot()
    def scan_ending(self):
        """Record end time of scan."""
        self.scan_end_time = time.time()
        self.scan_duration = self.scan_end_time - self.scan_start_time

    @Slot()
    def point_starting(self):
        """Record start time of point."""
        self.point_start_time = time.time()

    @Slot()
    def point_ending(self):
        """Record end time of point."""
        self.point_end_time = time.time()
        self.point_duration = self.point_end_time - self.point_start_time
        self.as_string()

    def as_string(self) -> str:
        """Format time information as a string."""
        s = f"""
        <h4>Time-Information</h4>
        Total Time: {timedelta(seconds=self.total_duration)}<br>
        """
        if self.point_duration:
            s += f"Time per Point: {timedelta(seconds=self.point_duration)}<br>"
        if self.scan_duration:
            s += f"Time per Scan: {timedelta(seconds=self.scan_duration)}<br>"
        self.sigTimesUpdated.emit(s)
        return s


@attr.s(auto_attribs=True, kw_only=True)
class Plan(QObject):
    plan_shorthand: ClassVar[str]

    name: str = ""
    meta: dict = attr.Factory(dict)
    status: str = ""
    creation_dt: datetime = attr.Factory(datetime.now)
    is_async: bool = False
    time_tracker: TimeTracker = attr.Factory(TimeTracker)
    file_name: Tuple[Path, Path] | None = None

    sigPlanFinished: ClassVar[Signal] = Signal()
    sigPlanStarted: ClassVar[Signal] = Signal()
    sigPlanStopped: ClassVar[Signal] = Signal()

    def __attrs_post_init__(self):
        super(Plan, self).__init__()
        self.get_file_name()  # check if name is valid

    def get_file_name(self) -> Tuple[Path, Path]:
        """Builds the filename and the metafilename"""
        if self.file_name is not None:
            return self.file_name
        if any(c in self.name for c in r':;<>"|?*\/'):
            raise ValueError("Plan name contains invalid characters")
        date_str = self.creation_dt.strftime("%y-%m-%d %H_%M")
        name = f"{date_str} {self.plan_shorthand} {self.name}"
        p = Path(config.data_directory)
        if not p.exists():
            raise IOError("Data path in config not existing")
        if (p / name).with_suffix(".json").exists():
            name = name + "_0"
        logger.info(f"Generated the filepath {str(p / name)}")
        return (p / name).with_suffix(".h5"), (p / name).with_suffix(".json")

    @property
    def data_file(self) -> h5py.File:
        return h5py.File(self.get_file_name()[0], "a", track_order=True)

    @property
    def meta_file(self) -> Path:
        return self.get_file_name()[1]

    def make_step_generator(self) -> Generator:
        """Generator that yields steps of the plan.

        Should be overridden by subclasses."""
        raise NotImplementedError

    def save_meta(self):
        """Saves the metadata in the metafile"""
        self.get_app_state()
        if self.meta is not None:
            _, meta_file = self.get_file_name()
            with meta_file.open("w") as f:
                json.dump(self.meta, f, indent=4)

    def get_app_state(self):
        """Collects all devices states."""
        self.meta["Saved at"] = datetime.now().isoformat()
        self.meta["Started at"] = self.creation_dt.isoformat()
        devices_state = {}
        for i in IDevice.registered_devices:
            devices_state[i.name] = i.get_state()
        self.meta["Devices"] = devices_state

    def restore_state(self):
        pass

    @Slot()
    def stop_plan(self):
        self.restore_state()
        self.sigPlanStopped.emit()


@attr.s(auto_attribs=True, kw_only=True)
class H5PySaver:
    fname: Path = attr.ib()
    plan: Plan = attr.ib()

    def __attrs_post_init__(self):
        self.fname.parent.mkdir(parents=True, exist_ok=True)

    def save(self, data: dict):
        with h5py.File(self.fname, "w") as f:
            for k, v in data.items():
                f.create_dataset(k, data=v)


@attr.s(auto_attribs=True, kw_only=True)
class ScanPlan(Plan):
    sigScanStarted: ClassVar[Signal] = Signal()
    sigScanFinished: ClassVar[Signal] = Signal()

    cur_scan: int = 0
    max_scan: int = 1_000_000
    stop_after_scan: bool = False

    @cached_property
    def make_step(self) -> Callable:
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
            yield from self.post_scan()
            self.sigScanFinished.emit()
            self.cur_scan += 1
        yield from self.post_plan()
        self.sigPlanFinished.emit()

    def scan(self) -> Generator:
        raise NotImplementedError

    def post_scan(self) -> Generator:
        yield True


from concurrent.futures import ThreadPoolExecutor, Future


@attr.s(auto_attribs=True, kw_only=True)
class PointList:
    axis: str
    points: ndarray
    func: Callable | None = None


@attr.s(auto_attribs=True, kw_only=True)
class PointScan(ScanPlan):
    points: dict[str, PointList]

    def move_pos(self, pos) -> Generator:
        raise NotImplementedError

    def setup_plan(self) -> Generator:
        return super().setup_plan()

    def scan(self):
        for i, pos in enumerate(self.points):
            yield from self.move_pos(pos)

            with ThreadPoolExecutor() as executor:
                future = executor.submit(self.measure_point)
                while not future.done():
                    yield True
                data = future.result()
                with h5py.File(self.file_name, "w") as f:
                    for k, v in data.items():
                        f.create_dataset(f"{self.cur_scan}/{k}", data=v)

    def measure_point(self) -> dict[str, ndarray]:
        raise NotImplementedError


@attr.s(auto_attribs=True, kw_only=True)
class AsyncPlan(Plan):
    is_async: bool = True
    task: Task = attr.ib(init=False)

    sigTaskCreated: ClassVar[Signal] = Signal()

    async def plan(self):
        raise NotImplementedError

    def __attrs_post_init__(self):
        super(AsyncPlan, self).__attrs_post_init__()
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self.plan(), name=self.name)

    def stop_plan(self):
        if self.task:
            self.task.cancel()
        return super().stop_plan()
