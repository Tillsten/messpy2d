import platform
import sys
from MessPy.Config import config
from MessPy.Instruments.mocks import CamMock, DelayLineMock, StageMock, PowerMeterMock
from loguru import logger

logger.info("Init HwRegistry")
TESTING = config.testing
_cam = None  # CamMock()
_cam2 = None  # CamMock(name="Mock2")
_dl = None
_dl2 = None
_rot_stage = None
_shutter = []
_sh = None
_shaper = None

pc_name = platform.node()

if len(sys.argv) > 1:
    arg = sys.argv[1]
else:
    arg = "vis"


logger.info(f"Running on {pc_name}")

if pc_name == "DESKTOP-RMRQA8D":
    logger.info("Importing and initializing AvaSpec")
    from MessPy.Instruments.cam_avaspec import AvaCam

    _cam = AvaCam()

    logger.info("Importing and initializing GeneratorDelayline")
    from MessPy.Instruments.delay_dg535 import GeneratorDelayline

    _dl = GeneratorDelayline()

    _cam2 = None

    # from MessPy.Instruments.delay_line_apt import DelayLine
    # _dl = DelayLine(name="VisDelay")

elif pc_name == "DESKTOP-BBLLUO7":

    def init_pt():
        logger.info("Importing and initializing PhaseTecCam")
        try:
            from MessPy.Instruments.cam_phasetec import PhaseTecCam

            global _cam
            _cam = PhaseTecCam()
            tmp_shots = _cam.shots
            _cam.set_shots(10)
            _cam.read_cam()
            _cam.set_shots(tmp_shots)

        except Exception as e:
            logger.warning("PhaseTecCam import or testread failed")
            raise e
        # _cam = CamMock()

    # from MessPy.Instruments.delay_line_apt import DelayLine
    # _dl = DelayLine(name="VisDelay")
    # from MessPy.Instruments.delay_dg535 import GeneratorDelayline

    # _dl = GeneratorDelayline(port='COM10')

    def init_dl():
        logger.info("Importing and initializing NewportDelay")
        from MessPy.Instruments.delay_line_newport import NewportDelay

        global _dl
        _dl = NewportDelay(name="IR Delay", pos_sign=-1)

    def init_aom():
        logger.info("Importing and initializing AOM")
        from MessPy.Instruments.dac_px import AOM, AOMShutter

        try:
            global _shaper
            _shaper = AOM(name="AOM")
            aom_shutter = AOMShutter(aom=_shaper)
            _shutter.append(aom_shutter)
            logger.info("Importing and initializing RotationStage")
            from MessPy.Instruments.RotationStage import RotationStage

            r1 = RotationStage(name="Grating1", comport="COM5")
            r2 = RotationStage(name="Grating2", comport="COM6")
            _shaper.rot1 = r1
            _shaper.rot2 = r2
            f1 = RotationStage(name="Folding2", comport="COM9", offset=0)
            f2 = RotationStage(name="Folding1", comport="COM4", offset=0)
            _shaper.fm1 = f1
            _shaper.fm2 = f2
        except Exception as e:
            logger.warning("Either AOM or Rotation Stage initalization failed")
            _shaper = None
            raise e

    def init_topas_shutter():
        logger.info("Importing and initializing TopasShutter")
        try:
            from MessPy.Instruments.shutter_topas import TopasShutter

            topas_shutter = TopasShutter()
            _shutter.append(topas_shutter)
        except ImportError as e:
            logger.warning("TopasShutter import failed")
            raise e

    # Use concurrent.futures to initialize hardware in parallel and
    # propagate exceptions from worker functions.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    init_aom()
    init_funcs = [init_pt, init_dl,  init_topas_shutter]
    with ThreadPoolExecutor(max_workers=len(init_funcs)) as ex:
        futures = {ex.submit(f): f.__name__ for f in init_funcs}
        for fut in as_completed(futures):
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
    # logger.info("Importing and initializing PhidgetShutter")
    # try:
    #    from MessPy.Instruments.shutter_phidget import PhidgetShutter

    #    _shutter.append(PhidgetShutter())
    # except ImportError:
    #    logger.warning("PhidgetShutter import failed")

    # from MessPy.Instruments.stage_smartact import SmarActXYZ

    # _sh = SmarActXYZ()
    _power_meter = None
    # try:
    #    from MessPy.Instruments.cam_power import PowerCam
    #    _power_meter = PowerCam()
    # except:
    #    _power_meter = None
    # try:
    #    from MessPy.Instruments.ophire import Starbright
    #    _power_meter = Starbright()
    # except:
    # _power_meter = None
else:
    logger.info("Unknown PC, using mocks")
    _cam = CamMock()
    _dl = DelayLineMock()
    _sh = StageMock()
    _power_meter = PowerMeterMock()

logger.info("HwRegistry initialized")
