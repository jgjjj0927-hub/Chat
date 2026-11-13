import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.api import Api
from client.ui.login import LoginWindow
from client.ui.main_window import MainWindow


def load_theme(app):
    qss_path = os.path.join(os.path.dirname(__file__), "ui", "theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("worm shadow")
    load_theme(app)

    api = Api()
    state = {}

    def on_login(username, priv, pub):
        win = MainWindow(api, username, priv, pub)
        win.show()
        state["main"] = win
        state["login"].close()

    login = LoginWindow(api, on_login)
    login.show()
    state["login"] = login

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
