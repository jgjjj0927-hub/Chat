from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
import crypto
import session


class LoginWindow(QWidget):
    def __init__(self, api, on_success):
        super().__init__()
        self.api = api
        self.on_success = on_success

        self.setWindowTitle("worm shadow — вход")
        self.setFixedSize(420, 380)

        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("worm shadow")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("сквозное шифрование, твой ключ — только у тебя")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        self.nick_input = QLineEdit()
        self.nick_input.setPlaceholderText("ник (например, Ivan)")
        layout.addWidget(self.nick_input)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("пароль")
        self.pass_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pass_input)

        layout.addSpacing(6)

        btn_login = QPushButton("Войти")
        btn_login.clicked.connect(self.handle_login)
        layout.addWidget(btn_login)

        btn_register = QPushButton("Зарегистрироваться")
        btn_register.setObjectName("secondary")
        btn_register.clicked.connect(self.handle_register)
        layout.addWidget(btn_register)

        layout.addStretch()
        self.setLayout(layout)

    def handle_login(self):
        nick = self.nick_input.text().strip()
        pw = self.pass_input.text()
        if not nick or not pw:
            QMessageBox.warning(self, "пусто", "введи ник и пароль")
            return
        try:
            self.api.login(nick, pw)
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        ident = session.load_identity(nick)
        if not ident:
            QMessageBox.critical(
                self, "ключ потерян",
                "на этом компьютере нет приватного ключа для этого ника.\n"
                "без него ты не сможешь расшифровывать сообщения."
            )
            return
        session.save_token(nick, self.api.token)
        self.on_success(nick, ident["private_key"], ident["public_key"])

    def handle_register(self):
        nick = self.nick_input.text().strip()
        pw = self.pass_input.text()
        if not nick or not pw:
            QMessageBox.warning(self, "пусто", "введи ник и пароль")
            return
        if len(pw) < 4:
            QMessageBox.warning(self, "слабый пароль", "минимум 4 символа")
            return
        priv, pub = crypto.generate_keypair()
        try:
            self.api.register(nick, pw, pub)
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        session.save_identity(nick, priv, pub)
        try:
            self.api.login(nick, pw)
        except Exception as e:
            QMessageBox.critical(self, "ошибка входа после регистрации", str(e))
            return
        session.save_token(nick, self.api.token)
        QMessageBox.information(
            self, "готово",
            "аккаунт создан. приватный ключ сохранён на этом компьютере."
        )
        self.on_success(nick, priv, pub)
