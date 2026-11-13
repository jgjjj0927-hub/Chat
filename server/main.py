import json
import time
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from pydantic import BaseModel

from server import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="worm-shadow messenger", lifespan=lifespan)

SESSIONS: dict[str, int] = {}
CONNECTIONS: dict[int, set[WebSocket]] = {}


# ---------- модели ----------

class RegisterReq(BaseModel):
    username: str
    password: str
    public_key: str


class LoginReq(BaseModel):
    username: str
    password: str


class ChannelReq(BaseModel):
    name: str
    description: str = ""


class ChatRequestReq(BaseModel):
    to_username: str


class ChatRespondReq(BaseModel):
    request_id: int
    accept: bool


# ---------- авторизация ----------

def auth(authorization: Optional[str]) -> int:
    if not authorization:
        raise HTTPException(401, "missing token")
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    user_id = SESSIONS.get(token)
    if user_id is None:
        raise HTTPException(401, "unauthorized")
    return user_id


# ---------- HTTP ----------

@app.post("/register")
def register(req: RegisterReq):
    if not req.username or len(req.username) < 2:
        raise HTTPException(400, "username too short")
    if len(req.password) < 4:
        raise HTTPException(400, "password too short")
    try:
        uid = db.create_user(req.username, req.password, req.public_key)
    except ValueError:
        raise HTTPException(400, "username taken")
    return {"user_id": uid}


@app.post("/login")
def login(req: LoginReq):
    u = db.get_user(req.username)
    if not u or not db.verify_password(req.password, u["password_hash"], u["salt"]):
        raise HTTPException(401, "bad credentials")
    token = secrets.token_hex(24)
    SESSIONS[token] = u["id"]
    return {"token": token, "user_id": u["id"], "public_key": u["public_key"]}


@app.get("/search")
def search(q: str, authorization: str = Header(None)):
    auth(authorization)
    return db.search_users(q)


@app.get("/channels")
def channels(authorization: str = Header(None)):
    uid = auth(authorization)
    return db.list_channels(uid)


@app.post("/channels")
def create_channel(req: ChannelReq, authorization: str = Header(None)):
    uid = auth(authorization)
    if not req.name.strip():
        raise HTTPException(400, "channel name empty")
    cid = db.create_channel(req.name.strip(), uid, req.description)
    return {"channel_id": cid}


@app.post("/chat/request")
def chat_request(req: ChatRequestReq, authorization: str = Header(None)):
    uid = auth(authorization)
    target = db.get_user(req.to_username)
    if not target:
        raise HTTPException(404, "no such user")
    if target["id"] == uid:
        raise HTTPException(400, "cannot request yourself")
    rid = db.create_chat_request(uid, target["id"])
    return {"request_id": rid}


@app.get("/chat/requests")
def chat_requests(authorization: str = Header(None)):
    uid = auth(authorization)
    return db.list_incoming_requests(uid)


@app.post("/chat/respond")
def chat_respond(req: ChatRespondReq, authorization: str = Header(None)):
    uid = auth(authorization)
    ok = db.respond_chat_request(req.request_id, uid, req.accept)
    if not ok:
        raise HTTPException(404, "request not found")
    return {"status": "accepted" if req.accept else "declined"}


# ---------- WebSocket ----------

async def _send_safe(ws: WebSocket, payload: dict) -> bool:
    try:
        await ws.send_text(json.dumps(payload))
        return True
    except Exception:
        return False


async def broadcast_to_user(user_id: int, payload: dict):
    sockets = CONNECTIONS.get(user_id)
    if not sockets:
        return
    dead = []
    for ws in list(sockets):
        ok = await _send_safe(ws, payload)
        if not ok:
            dead.append(ws)
    for ws in dead:
        sockets.discard(ws)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    token = ws.query_params.get("token")
    uid = SESSIONS.get(token) if token else None
    if uid is None:
        await ws.close(code=4401)
        return

    CONNECTIONS.setdefault(uid, set()).add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            kind = msg.get("kind")

            if kind == "dm":
                to_id = msg.get("to_id")
                payload = msg.get("payload")
                sender_pub = msg.get("sender_pub")
                if not isinstance(to_id, int) or not payload or not sender_pub:
                    continue
                if to_id == uid:
                    continue
                if db.get_user_by_id(to_id) is None:
                    continue
                await broadcast_to_user(
                    to_id,
                    {
                        "kind": "dm",
                        "from_id": uid,
                        "payload": payload,
                        "sender_pub": sender_pub,
                        "ts": int(time.time()),
                    },
                )

            elif kind == "channel_msg":
                await _send_safe(ws, {"kind": "stub", "for": "channel_msg"})

    except WebSocketDisconnect:
        pass
    finally:
        sockets = CONNECTIONS.get(uid)
        if sockets:
            sockets.discard(ws)
            if not sockets:
                CONNECTIONS.pop(uid, None)
