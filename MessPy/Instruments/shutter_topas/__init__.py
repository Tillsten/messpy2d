import time
from typing import List

import requests
from attr import dataclass

from MessPy.Instruments.interfaces import IShutter

ip_address = '127.0.0.1'
port = '8000'
serial_number = '14187'
version = 'v0'

url = f'http://{ip_address}:{port}/{serial_number}/{version}/PublicAPI'


@dataclass(kw_only=True)
class TopasShutter(IShutter):
    name: str = 'TopasShutter'
    baseAddress: str = url

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.is_open()

    def _get_motor_state(self) -> dict:
        ans = self.get('/Motors/PropertiesThatChangeOften')
        return ans.json()

    def get_state(self) -> dict:
        return self._get_motor_state()

    def load_state(self, exclude: list[str] | None = None):
        """Do nothing"""

    def put(self, url, data):
        return requests.put(self.baseAddress + url, json=data)

    def post(self, url, data):
        return requests.post(self.baseAddress + url, json=data)

    def get(self, url):
        return requests.get(self.baseAddress + url)

    def is_open(self) -> bool:
        return self.get('/ShutterInterlock/IsShutterOpen').json()

    def toggle(self):
        start_state = self.is_open()
        self.put('/ShutterInterlock/OpenCloseShutter', not start_state)
        self.sigShutterToggled.emit(not start_state)
        time.sleep(0.1)


if __name__ == '__main__':
    import time

    sh = TopasShutter()
    print(sh.is_open())
    sh.toggle()
    for i in range(10):
        print(sh.is_open())
        time.sleep(0.05)
