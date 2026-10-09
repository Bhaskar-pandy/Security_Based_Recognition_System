"""Encrypts and decrypts face data so it is never stored in plain form."""
import os

import numpy as np
from cryptography.fernet import Fernet

import config


def _load_key():
    """Read the secret key from disk. Create it the first time."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.KEY_PATH):
        with open(config.KEY_PATH, "wb") as f:
            f.write(Fernet.generate_key())
        os.chmod(config.KEY_PATH, 0o600)   # only the owner can read it
    with open(config.KEY_PATH, "rb") as f:
        return f.read()


def encrypt_encoding(encoding):
    """numpy array (128 numbers) -> encrypted bytes."""
    data = np.asarray(encoding, dtype=np.float64).tobytes()
    return Fernet(_load_key()).encrypt(data)


def decrypt_encoding(token):
    """Encrypted bytes -> numpy array (128 numbers)."""
    data = Fernet(_load_key()).decrypt(token)
    return np.frombuffer(data, dtype=np.float64)
