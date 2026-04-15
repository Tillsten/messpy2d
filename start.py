import faulthandler
faulthandler.enable()
from loguru import logger
from PySide6.QtWidgets import QApplication

app = QApplication([])
from MessPy.MessPy2D import start_app

logger.info("Starting MessPy2D")

start_app()
