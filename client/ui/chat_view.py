from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
import crypto


class ChatWindow(QWidget):
    def __init__(self, api, me, my_priv, my_pub, peer_name, peer_user_id):
        super().__init__()
        self.api = api
        self.me = me
        self.my_priv = my_priv
        self.my_pub = my_pub
        self.peer_name = peer_name
        self.peer_user_id = peer_user_id
        self.peer_pub = None
        self.shared_secret = None

        self.setWindowTitle(f"чат с @{peer_name}")
        self.resize(520, 600)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QLabel(f"@{peer_name}")
        header.setObjectName("title")
        layout.addWidget(header)

        self.messages_view = QTextEdit()
        self.messages_view.setReadOnly(True)
        layout.addWidget(self.messages_view, 1)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("написать сообщение…")
        self.input.returnPressed.connect(self.send_message)
        row.addWidget(self.input, 1)

        btn = QPushButton("отправить")
        btn.clicked.connect(self.send_message)
        row.addWidget(btn)
        layout.addLayout(row)

        self.setLayout(layout)

        self.try_load_peer_key()

    def try_load_peer_key(self):
        try:
            results = self.api.search(self.peer_name)
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        for u in results:
            if u["username"] == self.peer_name:
                self.peer_pub = u["public_key"]
                self.shared_secret = crypto.derive_shared_secret(
                    self.my_priv, self.peer_pub, context=b"dm"
                )
                return
        QMessageBox.warning(self, "ключ не найден", "не удалось получить публичный ключ собеседника")

    def send_message(self):
        text = self.input.text().strip()
        if not text:
            return
        if self.shared_secret is None:
            QMessageBox.warning(self, "нет ключа", "сначала получи публичный ключ собеседника")
            return
        payload = crypto.encrypt_message(self.shared_secret, text)
        try:
            ws = self.api  # отправка через websocket требует живого соединения
            # отправляем через отдельное короткое ws-подключение
            import websockets.sync.client as ws_client
            import json
            with ws_client.connect(f"ws://127.0.0.1:8000/ws?token={self.api.token}") as ws:
                ws.send(json.dumps({
                    "kind": "dm",
                    "to_id": self.peer_user_id,
                    "payload": payload,
                    "sender_pub": self.my_pub,
                }))
        except Exception as e:
            QMessageBox.critical(self, "ошибка отправки", str(e))
            return
        self.messages_view.append(f"<b>ты:</b> {text}")
        self.input.clear()

    def receive_message(self, payload, sender_pub):
        if self.shared_secret is None:
            try:
                self.shared_secret = crypto.derive_shared_secret(
                    self.my_priv, sender_pub, context=b"dm"
                )
            except Exception as e:
                self.messages_view.append(f"[не удалось расшифровать: {e}]")
                return
        try:
            text = crypto.decrypt_message(self.shared_secret, payload)
            self.messages_view.append(f"<b>@{self.peer_name}:</b> {text}")
        except Exception as e:
            self.messages_view.append(f"[ошибка расшифровки: {e}]")
