from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QInputDialog, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from .chat_view import ChatWindow


class WSThread(QThread):
    message = Signal(dict)

    def __init__(self, api):
        super().__init__()
        self.api = api
        self._stop = False

    def run(self):
        try:
            self.api.connect_ws(lambda m: self.message.emit(m))
        except Exception:
            pass

    def stop(self):
        self._stop = True


class MainWindow(QMainWindow):
    def __init__(self, api, username, private_key, public_key):
        super().__init__()
        self.api = api
        self.username = username
        self.private_key = private_key
        self.public_key = public_key
        self.chat_windows = {}

        self.setWindowTitle(f"worm shadow — {username}")
        self.resize(1000, 700)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        self.me_label = QLabel(f"@{username}")
        self.me_label.setObjectName("title")
        left_layout.addWidget(self.me_label)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("поиск по нику")
        search_row.addWidget(self.search_input)
        btn_search = QPushButton("найти")
        btn_search.clicked.connect(self.do_search)
        search_row.addWidget(btn_search)
        left_layout.addLayout(search_row)

        self.search_results = QListWidget()
        self.search_results.itemDoubleClicked.connect(self.open_search_result)
        left_layout.addWidget(self.search_results)

        tabs_label = QLabel("мои чаты")
        tabs_label.setObjectName("subtitle")
        left_layout.addWidget(tabs_label)

        self.chat_list = QListWidget()
        self.chat_list.itemDoubleClicked.connect(self.open_chat)
        left_layout.addWidget(self.chat_list)

        row = QHBoxLayout()
        btn_channel = QPushButton("создать канал")
        btn_channel.setObjectName("secondary")
        btn_channel.clicked.connect(self.create_channel)
        row.addWidget(btn_channel)

        btn_requests = QPushButton("заявки")
        btn_requests.setObjectName("secondary")
        btn_requests.clicked.connect(self.show_requests)
        row.addWidget(btn_requests)
        left_layout.addLayout(row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 20)
        hint = QLabel("выбери чат слева или найди человека по нику")
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(hint)
        splitter.addWidget(right)

        splitter.setSizes([340, 660])
        root.addWidget(splitter)
        self.setCentralWidget(central)

        self.ws_thread = WSThread(self.api)
        self.ws_thread.message.connect(self.on_ws_message)
        self.ws_thread.start()

        self.load_channels()

    def do_search(self):
        q = self.search_input.text().strip()
        if not q:
            return
        try:
            results = self.api.search(q)
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        self.search_results.clear()
        for u in results:
            if u["username"] == self.username:
                continue
            item = QListWidgetItem(f"{u['username']}")
            item.setData(Qt.UserRole, u)
            self.search_results.addItem(item)

    def open_search_result(self, item):
        user = item.data(Qt.UserRole)
        answer = QMessageBox.question(
            self, "начать чат",
            f"отправить заявку на чат пользователю {user['username']}?"
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.api.request_chat(user["username"])
            QMessageBox.information(self, "отправлено", "заявка ушла")
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))

    def load_channels(self):
        try:
            chans = self.api.channels()
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        self.chat_list.clear()
        for c in chans:
            item = QListWidgetItem(f"# {c['name']}")
            item.setData(Qt.UserRole, {"kind": "channel", "id": c["id"], "name": c["name"]})
            self.chat_list.addItem(item)

    def create_channel(self):
        name, ok = QInputDialog.getText(self, "новый канал", "название:")
        if not ok or not name.strip():
            return
        try:
            self.api.create_channel(name.strip())
            self.load_channels()
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))

    def show_requests(self):
        try:
            reqs = self.api.incoming_requests()
        except Exception as e:
            QMessageBox.critical(self, "ошибка", str(e))
            return
        if not reqs:
            QMessageBox.information(self, "заявки", "нет входящих заявок")
            return
        for r in reqs:
            answer = QMessageBox.question(
                self, "заявка на чат",
                f"{r['from_username']} хочет начать с тобой чат. принять?"
            )
            try:
                self.api.respond_request(r["id"], answer == QMessageBox.Yes)
                if answer == QMessageBox.Yes:
                    item = QListWidgetItem(f"@{r['from_username']}")
                    item.setData(Qt.UserRole, {
                        "kind": "dm",
                        "username": r["from_username"],
                        "user_id": r["from_id"],
                    })
                    self.chat_list.addItem(item)
            except Exception as e:
                QMessageBox.critical(self, "ошибка", str(e))

    def open_chat(self, item):
        data = item.data(Qt.UserRole)
        if data["kind"] == "channel":
            QMessageBox.information(self, "канал", "каналы будут в волне 3")
            return
        username = data["username"]
        if username in self.chat_windows:
            self.chat_windows[username].raise_()
            self.chat_windows[username].activateWindow()
            return
        win = ChatWindow(
            self.api, self.username, self.private_key, self.public_key,
            username, data["user_id"]
        )
        win.show()
        self.chat_windows[username] = win

    def on_ws_message(self, msg):
        if msg.get("kind") != "dm":
            return
        from_id = msg.get("from_id")
        payload = msg.get("payload")
        sender_pub = msg.get("sender_pub")
        sender_name = f"id{from_id}"
        for uname, win in self.chat_windows.items():
            if win.peer_user_id == from_id:
                win.receive_message(payload, sender_pub)
                return
        QMessageBox.information(
            self, "новое сообщение",
            f"пришло сообщение от пользователя id {from_id}. открой чат с ним."
        )
