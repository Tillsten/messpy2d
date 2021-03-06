import platform
import sys
import Instruments.dac_px
from Config import config
from Instruments.mocks import CamMock, DelayLineMock, StageMock
import logging

TESTING = config.testing
_cam = None #CamMock()
_cam2 = None#CamMock(name="Mock2")
_dl = None
_dl2 = None
_rot_stage = None
_shutter = None
_sh = None
_shaper = None

pc_name = platform.node()
if len(sys.argv) > 1:
    arg = sys.argv[1]
else:
    arg = ''


if pc_name == '2dir-PC':
    from Instruments.delay_line_mercury import dl
    _dl = dl
    hp = config.__dict__.get('Delay 1 Home Pos.', 8.80)
    _dl.home_pos = hp

    from Instruments.delay_line_gmc2 import dl
    _dl2 = dl
    #hp = config.__dict__.get('Delay 2 Home Pos.', 8.80)
    #_dl2.home_pos = hp
    #_dl2 = None
    from Instruments.sample_holder_PI import SampleHolder
    _sh = SampleHolder()
    #from Instruments.FringeCounter import fc
    #_fc = fc
elif pc_name == 'ir-2d':
    from Instruments.cam_phasetec import _ircam as _cam
    _cam2 = None
    #from Instruments.delay_line_gmc2 import DelayL
    #from Instruments.delay_line_mercury import dl
    from Instruments.delay_line_xmlrpc import _dl
    #hp = config.__dict__.get('Delay 1 Home Pos.', 8.80)
    #_dl.home_pos = hp
    logging.info("Init RotationStage and Shutter (rpc)")
    from Instruments.shutter import sh
    _shutter = sh
    from Instruments.RotationStage import rs
    _rot_stage = rs
    from Instruments.remotes import Faulhaber
    _sh = Faulhaber()
    _sh.set_pos_mm(*_sh.pos_home)



elif pc_name == 'helmholm' and not TESTING:
    from Instruments.stresing_cam.ESLS import Cam
    #from Instruments.delay_line_serial import dl as _dl
    from Instruments.delay_line_xmlrpc import dl as _dl
    #from Instruments.delay_line_mercury import dl as _dl
    logging.info("Init ESLS Cam")
    _cam = Cam()
    #from Instruments.ircam_64_remote import cam
    _cam2 = None
    logging.info("Init RotationStage and Shutter (rpc)")
    from Instruments.remotes import RotationStage, Shutter
    #_rot_stage = RotationStage()
    _shutter = Shutter()


elif pc_name == 'DESKTOP-BBLLUO7' and arg == 'Vis':
    from Instruments.cam_avaspec import AvaCam
    _cam = AvaCam()
    _cam2 = None
    from Instruments.delay_line_apt import DelayLine
    _dl = DelayLine(name="VisDelay")

elif pc_name == 'DESKTOP-BBLLUO7':
    from Instruments.cam_phasetec import PhaseTecCam
    _cam = PhaseTecCam()
    _cam2 = None
    #from Instruments.delay_line_apt import DelayLine
    #_dl = DelayLine(name="VisDelay")
    from Instruments.delay_line_newport import NewportDelay
    _dl = NewportDelay(name='IR Delay', pos_sign=-1)
    from Instruments.dac_px import AOM
    _shaper = AOM(name='AOM')
    from Instruments.RotationStage import RotationStage
    r1 = RotationStage(name="Grating1", comport="COM5")
    r2 = RotationStage(name="Grating2", comport="COM6")

    _shaper.rot1 = r1
    _shaper.rot2 = r2

else:
    _cam = CamMock()
    _dl = DelayLineMock()
    _sh = StageMock()
