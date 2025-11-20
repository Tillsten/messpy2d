import datetime
from abc import abstractmethod

from PySide6.QtWidgets import (
    QDialog,
    QPushButton,
    QLabel,
    QListWidget,
    QStyleFactory,
    QErrorMessage,
)

from PySide6.QtCore import Qt, QObject

from pyqtgraph import parametertree as pt

from MessPy.Widgets.common_helpers import hlay, vlay
from typing import Protocol, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from MessPy.Controller.Controller import Controller

import MessPy.Config as config

class PlanStarter(Protocol):
    experiment_type: ClassVar[str]
    title: ClassVar[str]
    icon: ClassVar[str]

    def setup_paras(self):
        pass

    def create_plan(self):
        pass


class QProtocolMetaMeta(type(QObject), type(PlanStarter)):
    pass



class PlanStartDialog(QDialog, metaclass=QProtocolMetaMeta):
    experiment_type: str = ""
    title: str = ""
    icon: str = ""
    paras: pt.Parameter

    def __init__(self, controller: "Controller", *args, **kwargs):
        super(PlanStartDialog, self).__init__(*args, **kwargs)
        self.controller = controller
        self.setMinimumWidth(800)
        self.setMaximumHeight(800)
        self.setWindowTitle(self.title)
        self.treeview = pt.ParameterTree()
        self.recent_settings = []
        self.recent_settings_list = QListWidget()
        self.recent_settings_list.currentRowChanged.connect(self.load_recent)

        self.start_button = QPushButton("Start Plan")
        self.start_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.plan_valid_lbl = QLabel()
        self.plan_valid_lbl.setText("Plan valid")

        self.setLayout(
            hlay(
                [
                    vlay(
                        [
                            self.treeview,
                            self.plan_valid_lbl,
                            hlay([self.start_button, cancel_button]),
                        ]
                    ),
                    vlay([QLabel("Recent Settings"), self.recent_settings_list]),
                ]
            )
        )

        self.setup_paras()
        self.setup_recent_list()
        self.treeview.setParameters(self.paras)
        self.paras.sigTreeStateChanged.connect(self.check_if_valid)
        self.treeview.setPalette(self.style().standardPalette())
        self.treeview.setStyle(QStyleFactory.create("Fusion"))
        self.treeview.setStyleSheet("")
        n = len(self.treeview.listAllItems())

        self.resize(350, n * 40 + 100)
        for i in self.treeview.listAllItems():
            if isinstance(i, pt.types.GroupParameterItem):
                i.updateDepth(0)

    @abstractmethod
    def setup_paras(self):
        raise NotImplementedError

    @abstractmethod
    def create_plan(self, controller: "Controller"):
        raise NotImplementedError

    def load_defaults(self, fname=None):
        pass

    def save_defaults(self, fname=None):
        d = self.paras.saveState(filter="user")
        d["date"] = datetime.datetime.now().isoformat()
        name = self.paras.child("Exp. Settings")["Filename"]
        conf_dict = config.exp_settings.setdefault(self.experiment_type, {})

        conf_dict[name] = d
        config.save()

    def closeEvent(self, *args, **kwargs):
        self.save_defaults()
        super().closeEvent(*args, **kwargs)

    def setup_recent_list(self):
        if self.experiment_type not in config.exp_settings:
            return
        conf_dict = config.exp_settings.setdefault(self.experiment_type, {})
        self.recent_settings = sorted(conf_dict.items(), key=lambda kv: kv[1]["date"])

        for name, r in self.recent_settings:
            self.recent_settings_list.addItem(name)

        self.recent_settings_list.setCurrentRow(len(self.recent_settings) - 1)
        self.load_recent(-1)

    def load_recent(self, new):
        settings = self.recent_settings[new][1].copy()
        settings.pop("date")
        self.paras.restoreState(settings, removeChildren=False, addChildren=False)
        self.check_if_valid()

    def check_if_valid(self):
        try:
            self.create_plan(self.controller)
            self.plan_valid_lbl.setText("<h2>Plan valid</h2>")
            self.start_button.setEnabled(True)
            return True
        except Exception as e:
            self.plan_valid_lbl.setText("<h2 color=r>Plan invalid: " + str(e) + "</h2>")
            self.start_button.setEnabled(False)
            return False

    @classmethod
    def start_plan(cls, controller, parent=None):
        dialog = cls(parent=parent, controller=controller)
        result = dialog.exec_()
        try:
            plan = dialog.create_plan(controller)
        except ValueError as e:
            emsg = QErrorMessage(parent=parent)
            emsg.setWindowModality(Qt.WindowModality.WindowModal)
            emsg.showMessage("Plan creation failed" + str(e))
            emsg.exec_()
            plan = None

            result = QDialog.DialogCode.Rejected
        return plan, result == QDialog.DialogCode.Accepted