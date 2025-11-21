import pyqtgraph.parametertree.parameterTypes as pTypes
import numpy as np
import pyqtgraph.parametertree as pt
from PySide6.QtWidgets import QWidget

from MessPy.ControlClasses import Controller
from MessPy.QtHelpers import vlay, PlanStartDialog, ObserverPlot, make_entry
from .ScanSpectrum import ScanSpectrum
from .PlanBase import sample_parameters


class ScanSpectrumView(QWidget):
    def __init__(self, scan_plan: ScanSpectrum, *args, **kwargs):
        super(ScanSpectrumView, self).__init__(*args, **kwargs)

        def get_probe():
            return scan_plan.probe[: scan_plan.wl_idx, 64]

        def get_ref():
            return scan_plan.ref[: scan_plan.wl_idx, 64]

        def wn():
            return 1e7 / scan_plan.wls[: scan_plan.wl_idx, 64]

        def nm():
            return scan_plan.wls[: scan_plan.wl_idx, 64]

        self.top_plot = ObserverPlot(
            obs=[get_probe, get_ref],
            signal=scan_plan.sigPointRead,
            x=wn,
        )

        self.bot_plot = ObserverPlot(
            obs=[get_probe, get_ref],
            signal=scan_plan.sigPointRead,
            x=nm,
        )
        self.bot_plot.plotItem.setLabel("bottom", "Wavelength / nm")
        self.top_plot.plotItem.setLabel("bottom", "Wavenumber / cm-1")
        self.setLayout(vlay([self.top_plot, self.bot_plot]))


class WavelengthParameter(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts["type"] = "float"
        opts["value"] = 700
        pTypes.GroupParameter.__init__(self, **opts)

        self.addChild(
            {
                "name": "Wavelength (nm)",
                "type": "float",
                "value": 700,
                "decimals": 5,
            }
        )
        self.addChild(
            {
                "name": "Wavenumber (cm-1)",
                "type": "float",
                "value": 1e7 / 700.0,
                "decimals": 5,
            }
        )
        self.wl = self.param("Wavelength (nm)")
        self.wn = self.param("Wavenumber (cm-1)")
        self.wl.sigValueChanged.connect(self.wl_changed)
        self.wn.sigValueChanged.connect(self.wn_changed)

    def wl_changed(self):
        self.wn.setValue(1e7 / self.wl.value(), blockSignal=self.wn_changed)
        self.setValue(self.wl.value())

    def wn_changed(self):
        self.wl.setValue(1e7 / self.wn.value(), blockSignal=self.wl_changed)
        self.setValue(self.wl.value())


class ScanSpectrumStarter(PlanStartDialog):
    experiment_type = "ScanSpec"
    viewer = ScanSpectrumView
    title = "Scan Spectrum"

    def setup_paras(self):
        tmp = [
            {"name": "Filename", "type": "str", "value": "temp"},
            {
                "name": "Shots",
                "type": "int",
                "max": 4000,
                "decimals": 5,
                "step": 100,
                "value": 100,
            },
            WavelengthParameter(name="Min."),
            WavelengthParameter(name="Max."),
            {"name": "Resolution", "type": "float", "min": 1.0, "value": 100.0},
            {"name": "Linear Axis", "type": "list", "limits": ["cm-1", "nm"], "value": "cm-1"},
            {"name": "timeout", "type": "float", "value": 3},
        ]

        self.candidate_cams = {
            c.cam.name: c for c in self.controller.cam_list if c.changeable_wavelength
        }
        cams = list(self.candidate_cams.keys())
        tmp.append(dict(name="Cam", type="list", limits=cams, value=cams[0]))
        p = pt.Parameter(name="Exp. Settings", type="group", children=tmp)
        sp = pt.Parameter(**sample_parameters)
        params = [sp, p]

        self.paras = pt.Parameter.create(
            name="Scan Spectrum", type="group", children=params
        )
        

        self.save_defaults()

    def create_plan(self, controller: Controller):
        p = self.paras.child("Exp. Settings")
        s = self.paras.child("Sample")
        mapper = {"nm": "Wavelength (nm)", "cm-1": "Wavenumber (cm-1)"}
        unit = mapper[p["Linear Axis"]]
        min_val, max_val = sorted([p.child("Min.")[unit], p.child("Max.")[unit]])
        wl_list = np.arange(min_val, max_val + 0.001, p["Resolution"])
        if p["Linear Axis"] == "cm-1":
            wl_list = 1e7 / wl_list
        scan = ScanSpectrum(
            name=p["Filename"],
            cam=self.candidate_cams[p["Cam"]],
            meta=make_entry(self.paras),
            wl_list=np.sort(wl_list),
            timeout=p["timeout"],
        )
        self.save_defaults()
        return scan
