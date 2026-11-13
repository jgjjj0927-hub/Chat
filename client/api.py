import json
import requests
import websockets.sync.client as ws_client

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"


class Api:
    def __init__(self):
        self.token = None
        self.user_id = None
        self.public_key = None

    def _headers(self):
        return {"authorization": self.token or ""}

    def register(self, username, password, public_key):
        r = requests.post(
            f"{BASE}/register",
            json={"username": username, "password": password, "public_key": public_key},
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError(r.json().get("detail", "register failed"))
        return r.json()

    def login(self, username, password):
        r = requests.post(
            f"{BASE}/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError(r.json().get("detail", "login failed"))
        data = r.json()
        self.token = data["token"]
        self.user_id = data["user_id"]
        self.public_key = data["public_key"]
        return data

    def search(self, q):
        r = requests.get(
            f"{BASE}/search", params={"q": q}, headers=self._headers(), timeout=10
        )
        if r.status_code != 200:
            raise RuntimeError("search failed")
        return r.json()

    def channels(self):
        r = requests.get(f"{BASE}/channels", headers=self._headers(), timeout=10)
        if r.status_code != 200:
            raise RuntimeError("channels failed")
        return r.json()

    def create_channel(self, name, description=""):
        r = requests.post(
            f"{BASE}/channels",
            json={"name": name, "description": description},
            headers=self._headers(),
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError(r.json().get("detail", "channel failed"))
        return r.json()

    def request_chat(self, to_username):
        r = requests.post(
            f"{BASE}/chat/request",
            json={"to_username": to_username},
            headers=self._headers(),
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError(r.json().get("detail", "request failed"))
        return r.json()

    def incoming_requests(self):
        r = requests.get(
            f"{BASE}/chat/requests", headers=self._headers(), timeout=10
        )
        if r.status_code != 200:
            raise RuntimeError("requests failed")
        return r.json()

    def respond_request(self, request_id, accept):
        r = requests.post(
            f"{BASE}/chat/respond",
            json={"request_id": request_id, "accept": accept},
            headers=self._headers(),
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError("respond failed")
        return r.json()

    def connect_ws(self, on_message):
        """Блокирующий цикл, запускать в отдельном потоке."""
        url = f"{WS}?token={self.token}"
        with ws_client.connect(url) as ws:
            while True:
                try:
                    raw = ws.recv(timeout=1)
                except TimeoutError:
                    continue
                except Exception:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                on_message(msg)

    def send_dm(self, ws, to_id, payload, sender_pub):
        ws.send(json.dumps({
            "kind": "dm",
            "to_id": to_id,
            "payload": payload,
            "sender_pub": sender_pub,
        }))
