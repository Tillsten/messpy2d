"""Using the IR-ADC over network. Uses direct zmq messages."""
import xmlrpc.client
from typing import List

import attr
import numpy as np
import wrapt
import zmq

from MessPy.Config import config
from MessPy.Instruments.interfaces import ICam, Reading

config.ir_server_addr = 'tcp://130.133.30.146:5555'
if config.ir_server_addr is None:
    config.ir_server_addr = 'tcp://130.133.30.146:5555'

#config.ir_server_addr = 'tcp://localhost:8001'
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(config.ir_server_addr)
triax = xmlrpc.client.ServerProxy(
    'http://130.133.30.146:8001', allow_none=True)


@attr.s(auto_attribs=True)
class Cam(ICam):
    name: str = 'Remote IR 32x2'
    shots: int = config.shots
    line_names: list = ['Probe', 'Ref']
    std_names: list = ['Probe', 'Ref', 'Probe/Ref']
    sig_names: list = ['Probe/Ref']
    channels: int = 32
    ext_channels: int = 3
    changeable_wavelength: bool = True
    changeable_slit: bool = True

    @wrapt.synchronized
    def read_cam(self):
        socket.send_json(('read', ''))
        #data = socket.recv()
        #data = np.frombuffer(b, dtype=args['dtype'], shape=args['shape'])
        shape, dtype = socket.recv_json()
        arr = socket.recv()
        arr = np.frombuffer(arr, dtype=dtype).reshape(shape)/3276.7
        ans = arr[:, :32], arr[:, 32:64], arr[:, -1] > 2, arr[:, [77]]
        return ans

    @wrapt.synchronized
    def make_reading(self) -> Reading:
        a, b, chopper, ext = self.read_cam()
        tmp = np.stack((a, b))
        if self.background is not None:
            tmp -= self.background[:, None, :]
        tm = tmp.mean(1)
        with np.errstate(invalid='ignore', divide='ignore'):
            ref = b/a
            ref_std = ref.std(0)/ref.mean(0)
            signal = -1000 * \
                np.log10(b[chopper, :].mean(0)/b[~chopper, :].mean(0))
            signal2 = -1000 * \
                np.log10(ref[chopper, :].mean(0) / ref[~chopper, :].mean(0))
        return Reading(
            lines=tm,
            stds=100*np.concatenate((tmp.std(1)/tm, ref_std[None, :])),
            signals=signal2[None, :],  # np.stack((signal2)),
            valid=True,
        )

    @wrapt.synchronized
    def new_make_reading(self):
        socket.send_json(('reading', ''))
        shape, dtype = socket.recv_json()
        arr = socket.recv()
        arr = np.frombuffer(arr, dtype=dtype).reshape(shape)
        print('reading')
        return Reading(
            lines=arr[:2, :],
            stds=arr[2:5, :],
            signals=arr[5:6, :],  # np.stack((signal2)),
            valid=True,
        )

    @wrapt.synchronized
    def set_shots(self, shots: int):
        shots = int(shots)
        socket.send_json(('set_shots', shots))
        self.shots = shots
        b = socket.recv_json()

    def get_wavelength_array(self, center_wl):
        li = triax.get_arr(center_wl)
        return np.array(li)

    def set_wavelength(self, wl: float):
        try:
            wl = float(wl)
            triax.set_wl(wl)
        except ValueError:
            pass

    def get_wavelength(self):
        return triax.get_wl()

    def get_slit(self):
        return triax.get_slit()

    def set_slit(self, slit):
        try:
            slit = float(slit)
            triax.set_slit(slit)
        except ValueError:
            pass

    @wrapt.synchronized
    def set_background(self, back):
        socket.send_json(('set_back', ''))
        ans = socket.recv_json()

    @wrapt.synchronized
    def get_background(self):
        socket.send_json(('get_back', ''))
        return socket.recv_json()


cam = Cam()

if __name__ == '__main__':
    print(cam.get_wavelength())
    # cam.set_wavelength(1e7/1700)
    print(cam.set_shots(100))
    print(cam.read_cam())
    print(cam.get_wavelength_array(5000), cam.get_wavelength_array(5500))
