from xmlrpc.client import ServerProxy
import sys
sys.path.append(r"C:\Users\MUELLER-WERKMEISTER\Downloads\download\messpy2d")

from Instruments.interfaces import IDelayLine
import wrapt
import logging
import attr
import clr

from System import Decimal, Action, UInt64

sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
clr.AddReference("Thorlabs.MotionControl.Benchtop.BrushlessMotorCLI")
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")

from Thorlabs.MotionControl.Benchtop.BrushlessMotorCLI import  BenchtopBrushlessMotor
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI




#config.dl_server = 'http://130.133.30.223:8000'

#dlproxy = ServerProxy(config.dl_server)

class APTDelay:
    def __init__(self):        
        DeviceManagerCLI.BuildDeviceList()
        dev_list = DeviceManagerCLI.GetDeviceList(BenchtopBrushlessMotor.DevicePrefix73)
       
        dev = BenchtopBrushlessMotor.CreateBenchtopBrushlessMotor(dev_list[0])        
        dev.Connect(dev_list[0])
        
        channel = dev.GetChannel(1)
        channel.WaitForSettingsInitialized(5000)
        channel.EnableDevice()
        channel.LoadMotorConfiguration(channel.DeviceID)
        channel.StartPolling(150)
        self.channel = channel
        self.moving = False

    def move_mm(self, x: float):
        if self.moving:
            self.channel.Stop(10000)
        def f(n):
            self.moving = False
        act = Action[UInt64](f)        
        self.moving = True
        self.channel.MoveTo(Decimal(x), act)

    def is_moving(self):
        return self.moving

    def get_pos_mm(self):
        return self.channel.Position

@attr.s(auto_attribs=True)
class DelayLine(IDelayLine):
    apt_delay : APTDelay = attr.Factory(APTDelay)

    def get_pos_mm(self) -> float:
        return 2*float(str(self.apt_delay.get_pos_mm()))

    def move_mm(self, mm, *args, **kwargs):
        self.apt_delay.move_mm(mm/2)
        return True

    def is_moving(self) -> bool:
        return self.apt_delay.is_moving()

if __name__ == "__main__":
    dl = DelayLine("ExtDelay")
    dl.load_home()
    print(dl.get_pos_mm())
    print(dl.move_mm(30))
    while dl.is_moving():
        pass #print(dl.is_moving())
    print(dl.get_pos_mm())
    #dl.def_home()


