import attr
import instrumental.drivers.cameras.uc480
from instrumental import instrument
from qtpy import QtCore, QtWidgets

from MessPy.Instruments.interfaces import IPowerMeter


@attr.dataclass(kw_only=True)
class PowerCam(IPowerMeter):
    name: str = 'UC 480'
    _cam = instrumental.drivers.cameras.uc480.UC480_Camera = instrument('UC480_Camera')
    exposure_ms: float = 1.99

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._cam.set_auto_exposure(False)
        self._cam.start_live_video(exposure_time='%.2fms'%self.exposure_ms, vsub=2, hsub=2)

    def get_state(self) -> dict:
        return dict()

    def read_power(self):
        self._cam.wait_for_frame()
        img = self._cam.latest_frame()
        return img.mean()

if __name__ == '__main__':
    import pyqtgraph as pg
    #app = QtWidgets.QApplication([])
    #win = pg.PlotWidget()
    #image = pg.ImageItem()
    #win.addItem(image)
    cam = PowerCam()
    #image.setImage(cam._cam.grab_image())
    for i in range(30):
        print(cam.read_power())
    #win.show()
    #app.exec_()




