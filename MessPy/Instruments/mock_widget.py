from typing import TYPE_CHECKING

from pyqtgraph.parametertree import Parameter, ParameterTree
from PySide6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    from .mocks import MockCam

params = [
    dict(name="Noise Level", type="float", value=0.01, step=0.1, min=0),
    dict(name="Peak Width", type="float", value=50, step=10, min=10),
]


class MockWidget(QWidget):
    def __init__(self, cam: "MockCam"):
        super().__init__()
        self.mock_cam = cam
        self.setWindowTitle("MockCam Widget")

        self.setLayout(QVBoxLayout())
        self.tree = ParameterTree()
        self.layout().addWidget(self.tree)
        self.params = Parameter.create(name="params", type="group", children=params)
        self.tree.setParameters(self.params, showTop=False)
        self.params["Noise Level"] = cam.noise_scale
        self.params["Peak Width"] = cam.peak_width
        self.params.sigTreeStateChanged.connect(self.update_cam)

    def update_cam(self):
        self.mock_cam.noise_scale = self.params["Noise Level"]
        self.mock_cam.peak_width = self.params["Peak Width"]
