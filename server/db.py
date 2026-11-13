import os
import time
import hmac
import base64
import sqlite3
import secrets
import threading

DB_PATH = os.path.join(os.path.dirname(__file__), "messenger.db")

# один общий коннект, потокобезопасный через блокировку
_conn = None
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db():
    conn = get_conn()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


# ---------- пароли ----------

def hash_password(password: str):
    salt = secrets.token_bytes(16)
    digest = _pbkdf2(password, salt)
    return base64.b64encode(digest).decode(), base64.b64encode(salt).decode()


def _pbkdf2(password: str, salt: bytes) -> bytes:
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    salt = base64.b64decode(stored_salt)
    digest = base64.b64encode(_pbkdf2(password, salt)).decode()
    return hmac.compare_digest(digest, stored_hash)


# ---------- пользователи ----------

def create_user(username: str, password: str, public_key: str) -> int:
    pw_hash, salt = hash_password(password)
    with _lock:
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, public_key, created_at) "
                "VALUES (?,?,?,?,?)",
                (username, pw_hash, salt, public_key, int(time.time())),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError("username taken")
    return cur.lastrowid


def get_user(username: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def search_users(query: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, public_key FROM users "
        "WHERE username LIKE ? COLLATE NOCASE LIMIT 20",
        (f"%{query}%",),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- каналы ----------

def create_channel(name: str, owner_id: int, description: str = "") -> int:
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO channels (name, owner_id, description, created_at) "
            "VALUES (?,?,?,?)",
            (name, owner_id, description, int(time.time())),
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO channel_members (channel_id, user_id, joined_at) "
            "VALUES (?,?,?)",
            (cid, owner_id, int(time.time())),
        )
        conn.commit()
    return cid


def list_channels(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.id, c.name, c.owner_id, c.description, c.created_at
           FROM channels c
           JOIN channel_members m ON m.channel_id = c.id
           WHERE m.user_id = ?""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- заявки на чат ----------

def create_chat_request(from_id: int, to_id: int) -> int:
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO chat_requests (from_id, to_id, created_at) "
            "VALUES (?,?,?)",
            (from_id, to_id, int(time.time())),
        )
        conn.commit()
    return cur.lastrowid


def list_incoming_requests(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.id, r.from_id, u.username AS from_username, r.status, r.created_at
           FROM chat_requests r
           JOIN users u ON u.id = r.from_id
           WHERE r.to_id = ? AND r.status = 'pending'""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def respond_chat_request(request_id: int, user_id: int, accept: bool) -> bool:
    with _lock:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM chat_requests WHERE id = ? AND to_id = ?",
            (request_id, user_id),
        ).fetchone()
        if not row:
            return False
        status = "accepted" if accept else "declined"
        conn.execute(
            "UPDATE chat_requests SET status = ? WHERE id = ?", (status, request_id)
        )
        conn.commit()
    return True
