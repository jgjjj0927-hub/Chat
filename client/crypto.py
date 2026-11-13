import os
import base64

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)


def generate_keypair():
    priv = X25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    pub_bytes = priv.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    return (
        base64.b64encode(priv_bytes).decode(),
        base64.b64encode(pub_bytes).decode(),
    )


def derive_shared_secret(priv_b64: str, peer_pub_b64: str, context: bytes = b"dm") -> bytes:
    priv = X25519PrivateKey.from_private_bytes(base64.b64decode(priv_b64))
    peer_pub = X25519PublicKey.from_public_bytes(base64.b64decode(peer_pub_b64))
    shared = priv.exchange(peer_pub)
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"worm-shadow-messenger:" + context,
    ).derive(shared)


def encrypt_message(shared_secret: bytes, plaintext: str) -> str:
    aesgcm = AESGCM(shared_secret)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_message(shared_secret: bytes, payload_b64: str) -> str:
    raw = base64.b64decode(payload_b64)
    if len(raw) < 13:
        raise ValueError("payload too short")
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(shared_secret)
    return aesgcm.decrypt(nonce, ct, None).decode()
