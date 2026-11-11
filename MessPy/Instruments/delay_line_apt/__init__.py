import sys
sys.path.append(r"C:\Users\MUELLER-WERKMEISTER\Downloads\download\messpy2d - Copy")
sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")


import clr
clr.AddReference("Thorlabs.MotionControl.Benchtop.BrushlessMotorCLI")
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.Benchtop.BrushlessMotorCLI import BenchtopBrushlessMotor
from System import Decimal, Action, UInt64

import attr
import logging
import wrapt
from MessPy.Instruments.interfaces import IDelayLine
from xmlrpc.client import ServerProxy



#config.dl_server = 'http://130.133.30.223:8000'

#dlproxy = ServerProxy(config.dl_server)

class APTDelay:
    def __init__(self):
        DeviceManagerCLI.BuildDeviceList()
        dev_list = DeviceManagerCLI.GetDeviceList(
            BenchtopBrushlessMotor.DevicePrefix73)

        dev = BenchtopBrushlessMotor.CreateBenchtopBrushlessMotor(dev_list[0])
        dev.Connect(dev_list[0])

        channel = dev.GetChannel(1)
        channel.WaitForSettingsInitialized(5000)
        channel.EnableDevice()
        channel.LoadMotorConfiguration(channel.DeviceID)
        channel.StartPolling(100)

        motorConfiguration = channel.LoadMotorConfiguration(channel.DeviceID)
        currentDeviceSettings = channel.MotorDeviceSettings

        pid = channel.GetPosLoopParams()
        pid.set_DerivativeGain(3000)
        self.channel = channel
        self.moving = False
        print(type(channel))
        print([x for x in dir(channel) if "Pos" in x])
        print([x for x in dir(channel) if "Move" in x])
        print([x for x in dir(channel) if "Busy" in x])
        print([x for x in dir(channel) if "Status" in x])

    def move_mm(self, x: float):
        if self.moving:
            self.channel.Stop(10000)

        def f(n):
            self.moving = False
        act = Action[UInt64](f)
        self.moving = True
        self.channel.MoveTo(Decimal(x), act)
        
    def is_moving(self):

        print(self.get_status())
        return self.channel.IsDeviceBusy

    def get_pos_mm(self):
        self.channel.RequestPosition()
        import time
        while str(self.channel.Position) == '0':
            time.sleep(0.05)
            #print(self.channel.Position)
        return self.channel.Position

    def get_status(self):
        self.channel.RequestStatusBits()
        status = int(self.channel.GetStatusBits())

        return {
            "raw": hex(status),
            "cw_limit": bool(status & 0x01),
            "ccw_limit": bool(status & 0x02),
            "moving_cw": bool(status & 0x10),
            "moving_ccw": bool(status & 0x20),
            "jogging_cw": bool(status & 0x40),
            "jogging_ccw": bool(status & 0x80),
            "homing": bool(status & 0x200),
            "homed": bool(status & 0x400),
            "active": bool(status & 0x20000000),
            "enabled": bool(status & 0x80000000),
        }


@attr.s(auto_attribs=True)
class DelayLine(IDelayLine):
    apt_delay: APTDelay = attr.Factory(APTDelay)

    def get_pos_mm(self) -> float:
        return 2*float(str(self.apt_delay.get_pos_mm()))

    def move_mm(self, mm, *args, **kwargs):
        self.apt_delay.move_mm(mm/2)
        return True

    def is_moving(self) -> bool:
        return self.apt_delay.is_moving()


if __name__ == "__main__":
    dl = DelayLine("ExtDelay")
    print(dl.get_status())
    print(dl.get_pos_mm())
    #print(dl.move_mm(30))
    #while dl.is_moving():
    #    pass  # print(dl.is_moving())
    print(dl.get_pos_mm())
    # dl.def_home()
