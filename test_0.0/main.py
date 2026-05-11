import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import SafeCityMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SafeCity AI Monitor")
    app.setOrganizationName("SafeCity Prototype")

    window = SafeCityMainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
