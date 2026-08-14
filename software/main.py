import sys
import serial
from PyQt6.QtWidgets import QApplication
from app import MainWindow, STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Open-Source Potentiostat")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

