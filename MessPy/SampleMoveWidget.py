# from Config import config
import attr
from PySide6.QtCore import QObject, Qt, QTimer, Slot
from PySide6.QtGui import QFocusEvent, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from MessPy.Instruments.interfaces import ILissajousScanner
from MessPy.QtHelpers import hlay, vlay


@attr.define(slots=False)
class ScannerMover(QObject):
    @Slot()
    def move_left(self):
        pass

    @Slot()
    def move_right(self):
        pass

    @Slot()
    def move_up(self):
        pass

    @Slot()
    def move_down(self):
        pass


class MoveWidget(QWidget):
    def __init__(self, sh: ILissajousScanner):
        super().__init__()
        self.scanner = sh
        self.setFocusPolicy(Qt.StrongFocus)
        home_button = QPushButton("Set Home")
        home_button.clicked.connect(lambda: self.scanner.set_home())
        goto_home = QPushButton("Go Home")
        goto_home.clicked.connect(lambda: self.scanner.set_pos_mm(0, 0))
        self.move_button = QPushButton("Cont. Move.")
        self.move_button.setCheckable(True)
        self.move_button.setChecked(False)
        self.move_button.toggled.connect(self.mover)
        buttons = hlay([home_button, goto_home, self.move_button])
        pos_str = str(self.scanner.pos_home)
        self.home_label = QLabel()
        self.label_updater(self.scanner.get_pos_mm(), self.scanner.get_zpos_mm())
        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.show_help)
        self.setLayout(vlay([self.home_label, buttons, self.help_button]))
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_pos)
        self.timer.setSingleShot(True)
        self.timer.start(500)

        self.K = 0.1
        self.x_settings = 3
        self.y_settings = [2, 0.2]

    def focusInEvent(self, a0: QFocusEvent) -> None:
        self.home_label.setStyleSheet("background-color: green")
        super().focusInEvent(a0)

    def focusOutEvent(self, a0: QFocusEvent) -> None:
        self.home_label.setStyleSheet("background-color: red")
        super().focusOutEvent(a0)

    def show_help(self):
        self.help_label = QLabel()
        self.help_label.setPixmap(QPixmap("MotorHelp.png"))
        self.help_label.setAutoFillBackground(False)
        self.help_label.show()

    def show_xy(self):
        pass

    def mover(self):
        if self.move_button.isChecked():
            self.setwid = SettingsMoveWidget(mw=self)
            self.setwid.show()

        if not self.move_button.isChecked():
            self.scanner.stop_contimove()
            # self.x_settings = None
            # self.y_settings = None

    def update_pos(self):
        x, y = self.scanner.get_pos_mm()
        z = self.scanner.get_zpos_mm()
        self.label_updater((x, y), z)
        app = QApplication.instance()
        if app:
            self.timer.singleShot(500, self.update_pos)

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        key = a0.key()
        pos = list(self.scanner.get_pos_mm())
        print(pos)
        if self.scanner.has_zaxis:
            z_pos = self.scanner.get_zpos_mm()

        move = True
        K = self.K
        if key == Qt.Key_Left:
            pos[0] += K
        elif key == Qt.Key_Right:
            pos[0] -= K
        elif key == Qt.Key_Up:
            pos[1] += K
        elif key == Qt.Key_Down:
            pos[1] -= K
        elif key == Qt.Key_W:
            self.K *= 1.5
        elif key == Qt.Key_S:
            self.K /= 1.5
        elif key == Qt.Key_Escape:
            move = False
            self.close()

        if self.scanner.has_zaxis:
            z_pos = self.scanner.get_zpos_mm()
            if key == Qt.Key_R:
                z_pos += 0.3
                move = False
            if key == Qt.Key_F:
                z_pos -= 0.3
                move = False
            self.scanner.set_zpos_mm(z_pos)
        else:
            z_pos = 0

        if move:
            self.scanner.set_pos_mm(*pos)
        self.label_updater(pos, z_pos)

    def label_updater(self, new_pos, zpos):
        self.home_label.setText(
            f" x: {new_pos[0]:.3f}, y: {new_pos[1]:.3f}, z: {zpos: .1f}"
        )


class SettingsMoveWidget(QWidget):
    def __init__(self, mw: MoveWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mw = mw
        self.x_button = QPushButton("Set x:")
        self.x_button.clicked.connect(self.x_click)
        self.xlim_label = QLabel("X amp.")
        self.edit_box_x = QLineEdit("3")
        self.edit_box_x.setMaxLength(3)
        self.edit_box_x.setMaximumWidth(100)
        self.x_limbox = vlay([self.xlim_label, self.edit_box_x])
        # self.xsteps_label = QLabel('x steps')
        # self.edit_box_xstep = QLineEdit()
        # self.edit_box_xstep.setMaxLength(3)
        # self.edit_box_xstep.setMaximumWidth(100)
        self.x_setter = hlay([self.x_button, self.x_limbox])

        self.y_button = QPushButton("Set y:")
        self.y_button.clicked.connect(self.y_click)
        self.ylim_label = QLabel("y limit")
        self.edit_box_y = QLineEdit("3")
        self.edit_box_y.setMaxLength(3)
        self.edit_box_y.setMaximumWidth(100)
        self.y_limbox = vlay([self.ylim_label, self.edit_box_y])
        # self.ysteps_label = QLabel('y steps')
        # self.edit_box_ystep = QLineEdit()
        # self.edit_box_ystep.setMaxLength(3)
        # self.edit_box_ystep.setMaximumWidth(100)
        # self.y_stepbox = vlay([self.ysteps_label, self.edit_box_ystep])
        self.y_setter = hlay([self.y_button, self.y_limbox])
        self.start_button = QPushButton("Start Movement:")
        self.start_button.clicked.connect(self.start_move)
        self.setLayout(vlay([self.x_setter, self.y_setter, self.start_button]))

    def x_click(self):
        self.mw.x_settings = float(self.edit_box_x.text())

    def y_click(self):
        self.mw.y_settings = float(self.edit_box_y.text())

    def start_move(self):
        self.mw.x_settings = float(self.edit_box_x.text())
        self.mw.y_settings = float(self.edit_box_y.text())
        self.mw.scanner.start_contimove(self.mw.x_settings, self.mw.y_settings)
        print(self.mw.x_settings, self.mw.y_settings)
        self.close()


if __name__ == "__main__":
    from MessPy.Instruments.stage_smartact import SmarActXYZ

    sh = SmarActXYZ()
    app = QApplication([])
    mwid = MoveWidget(sh)
    mwid.show()
    app.exec_()
