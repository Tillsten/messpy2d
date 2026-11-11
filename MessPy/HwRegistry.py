import platform
import typing as T

import attr
from loguru import logger
from PySide6.QtWidgets import QApplication

from MessPy.Config import config
from MessPy.Instruments.interfaces import (
    ICam,
    IDelayLine,
    ILissajousScanner,
    IPowerMeter,
    IRotationStage,
    IShutter,
)
from MessPy.Instruments.mocks import CamMock, DelayLineMock, PowerMeterMock, StageMock


def _move_to_main_thread(obj):
    """Move a freshly constructed QObject to the GUI thread and return it, for inline use.

    Otherwise, since it was constructed in a worker thread, later cross-thread
    signal delivery can silently fail.
    """
    app = QApplication.instance()
    if app is not None:
        obj.moveToThread(app.thread())
    return obj


def _guarded_init(description: str, fn):
    """Run fn(), logging progress and adding context to any failure."""
    logger.info(f"Importing and initializing {description}")
    try:
        fn()
    except Exception:
        logger.warning(f"{description} initialization failed")
        raise


def _run_init_steps(steps: dict[str, T.Callable[[], None]]):
    """Run each step in its own thread and wait for all to finish.

    Re-raises the first failure only after every step has completed. Polls
    with a timeout (instead of blocking on as_completed) so the GUI thread
    can keep pumping events -- e.g. to repaint a splash screen -- even
    though the real Qt event loop hasn't started yet at this point.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    app = QApplication.instance()
    with ThreadPoolExecutor(max_workers=len(steps)) as ex:
        futures = {
            ex.submit(_guarded_init, name, fn): name for name, fn in steps.items()
        }
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
            if app is not None:
                app.processEvents()
            for fut in done:
                name = futures[fut]
                try:
                    fut.result()
                    logger.info(f"Initialization function {name} finished successfully")
                except Exception as e:
                    logger.exception(
                        f"Initialization function {name} raised an exception: {e}"
                    )
                    # re-raise so import errors aren't silently swallowed
                    raise


@attr.s(auto_attribs=True)
class Hardware:
    """Initializes and holds every instrument for the machine we're running on."""

    cam: ICam | None = None
    cam2: ICam | None = None
    dl: IDelayLine | None = None
    rot_stage: IRotationStage | None = None
    shutter: list[IShutter] = attr.Factory(list)
    sh: ILissajousScanner | None = None
    shaper: object | None = None
    power_meter: IPowerMeter | None = None

    def __attrs_post_init__(self):
        pc_name = platform.node()
        logger.info(f"Running on {pc_name}")

        if pc_name == "DESKTOP-RMRQA8D":
            self._init_avaspec_rig()
        elif pc_name == "DESKTOP-BBLLUO7":
            self._init_phasetec_rig()
        else:
            logger.info("Unknown PC, using mocks")
            self.cam = CamMock()
            self.dl = DelayLineMock()
            self.sh = StageMock()
            self.power_meter = PowerMeterMock()

        logger.info("HwRegistry initialized")

    def _init_avaspec_rig(self):
        def _init_cam():
            from MessPy.Instruments.cam_avaspec import AvaCam

            self.cam = _move_to_main_thread(AvaCam())

        def _init_delay_and_shutter():
            from MessPy.Instruments.delay_dg535 import DGGShutter, GeneratorDelayline

            # from MessPy.Instruments.delay_line_apt import DelayLine
            # self.dl = DelayLine(name="VisDelay")
            # from MessPy.Instruments.delay_line_newport import NewportDelay
            self.dl = _move_to_main_thread(GeneratorDelayline())
            # self.dl = NewportDelay('COM5', beam_passes=4, pos_sign=-1)
            self.shutter.append(
                _move_to_main_thread(
                    DGGShutter(generator=self.dl.generator, name="Gen Shutter")
                )
            )

        def _init_rot_stage():
            from MessPy.Instruments.rot_stage_thorlabs import TLRotStage

            self.rot_stage = _move_to_main_thread(TLRotStage("Polarizer"))

        _run_init_steps(
            {
                "AvaCam": _init_cam,
                "GeneratorDelayline": _init_delay_and_shutter,
                "Polarizer RotStage": _init_rot_stage,
            }
        )

    def _init_phasetec_rig(self):
        def _init_pt():
            from MessPy.Instruments.cam_phasetec import PhaseTecCam

            self.cam = _move_to_main_thread(PhaseTecCam())
            tmp_shots = self.cam.shots
            self.cam.set_shots(10)
            self.cam.read_cam()
            self.cam.set_shots(tmp_shots)
            # self.cam = CamMock()

        # from MessPy.Instruments.delay_line_apt import DelayLine
        # self.dl = DelayLine(name="VisDelay")
        # from MessPy.Instruments.delay_dg535 import GeneratorDelayline

        # self.dl = GeneratorDelayline(port='COM10')

        def _init_dl():
            from MessPy.Instruments.delay_line_newport import NewportDelay

            self.dl = _move_to_main_thread(NewportDelay(name="IR Delay", pos_sign=-1))

        def _init_aom():
            from MessPy.Instruments.dac_px import AOM, AOMShutter
            from MessPy.Instruments.RotationStage import RotationStage

            try:
                self.shaper = _move_to_main_thread(AOM(name="AOM"))
                self.shutter.append(_move_to_main_thread(AOMShutter(aom=self.shaper)))
                self.shaper.rot1 = _move_to_main_thread(
                    RotationStage(name="Grating1", comport="COM5")
                )
                self.shaper.rot2 = _move_to_main_thread(
                    RotationStage(name="Grating2", comport="COM6")
                )
                self.shaper.fm1 = _move_to_main_thread(
                    RotationStage(name="Folding2", comport="COM9", offset=0)
                )
                self.shaper.fm2 = _move_to_main_thread(
                    RotationStage(name="Folding1", comport="COM4", offset=0)
                )
            except Exception:
                self.shaper = None  # partial init isn't usable, drop it
                raise

        def _init_topas_shutter():
            from MessPy.Instruments.shutter_topas import TopasShutter

            self.shutter.append(_move_to_main_thread(TopasShutter()))

        _run_init_steps(
            {
                "AOM": _init_aom,
                "PhaseTecCam": _init_pt,
                "NewportDelay": _init_dl,
                "TopasShutter": _init_topas_shutter,
            }
        )
        # logger.info("Importing and initializing PhidgetShutter")
        # try:
        #    from MessPy.Instruments.shutter_phidget import PhidgetShutter

        #    self.shutter.append(PhidgetShutter())
        # except ImportError:
        #    logger.warning("PhidgetShutter import failed")

        # from MessPy.Instruments.stage_smartact import SmarActXYZ

        # self.sh = SmarActXYZ()
        self.power_meter = None
        # try:
        #    from MessPy.Instruments.cam_power import PowerCam
        #    self.power_meter = PowerCam()
        # except:
        #    self.power_meter = None
        # try:
        #    from MessPy.Instruments.ophire import Starbright
        #    self.power_meter = Starbright()
        # except:
        # self.power_meter = None


hw = Hardware()

TESTING = config.testing
