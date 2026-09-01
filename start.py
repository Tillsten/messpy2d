import faulthandler

faulthandler.enable()
from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen
from qtawesome import icon as qta_icon

app = QApplication([])

_STATUS_ALIGN = Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter


def _build_splash_pixmap() -> QPixmap:
    width, height = 480, 260
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#1e1e1e"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    icon_pixmap = qta_icon("fa5s.play", color="#4ea1ff").pixmap(64, 64)
    painter.drawPixmap((width - 64) // 2, 36, icon_pixmap)

    painter.setPen(QColor("white"))
    painter.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    painter.drawText(0, 112, width, 40, Qt.AlignmentFlag.AlignCenter, "MessPy2D")

    painter.setPen(QColor("#9a9a9a"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(
        0,
        150,
        width,
        30,
        Qt.AlignmentFlag.AlignCenter,
        "Ultrafast Spectroscopy Control",
    )
    painter.end()
    return pixmap


class _StatusUpdater(QObject):
    """Relays log messages to the splash screen from whichever thread logs them.

    Signals are safe to emit cross-thread; Qt auto-queues delivery onto this
    object's (the GUI thread's) event loop instead of touching the widget
    directly from a worker thread.
    """

    status_changed = Signal(str)

    def __init__(self, splash: QSplashScreen):
        super().__init__()
        self._splash = splash
        self.status_changed.connect(self._show)

    def _show(self, text: str):
        self._splash.showMessage(text, _STATUS_ALIGN, Qt.GlobalColor.lightGray)


splash = QSplashScreen(_build_splash_pixmap())
status_updater = _StatusUpdater(splash)
_log_handler_id = logger.add(
    lambda message: status_updater.status_changed.emit(message.record["message"]),
    level="INFO",
)
status_updater.status_changed.emit("Starting up...")
splash.show()
app.processEvents()

from MessPy.MessPy2D import start_app  # slow: imports and initializes real hardware

logger.info("Starting MessPy2D")
logger.remove(_log_handler_id)

start_app(splash)
