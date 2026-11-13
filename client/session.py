import os
import json


CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".worm_shadow")
os.makedirs(CONFIG_DIR, exist_ok=True)


def path(name):
    return os.path.join(CONFIG_DIR, name)


def save_identity(username, private_key, public_key):
    data = {"username": username, "private_key": private_key, "public_key": public_key}
    with open(path(f"identity_{username}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_identity(username):
    p = path(f"identity_{username}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_token(username, token):
    with open(path(f"token_{username}.json"), "w", encoding="utf-8") as f:
        json.dump({"token": token}, f)


def load_token(username):
    p = path(f"token_{username}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("token")
