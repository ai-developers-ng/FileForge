"""At-rest file encryption using AES-256-GCM.

Encrypted file format on disk:
    [12-byte nonce][ciphertext + 16-byte GCM tag]

The key is a 32-byte (256-bit) AES key provided by the client,
transmitted base64url-encoded in the X-Encryption-Key HTTP header,
and held in server memory only during the request/job lifecycle.
"""

import base64
import logging
import os
import tempfile
import threading

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

NONCE_SIZE = 12  # 96 bits, standard for GCM


def key_to_b64(key: bytes) -> str:
    """Encode a raw key to base64url string (no padding)."""
    return base64.urlsafe_b64encode(key).rstrip(b"=").decode("ascii")


def key_from_b64(b64: str) -> bytes:
    """Decode a base64url string to raw 32-byte key."""
    padding = 4 - len(b64) % 4
    if padding != 4:
        b64 += "=" * padding
    key = base64.urlsafe_b64decode(b64)
    if len(key) != 32:
        raise ValueError(f"Invalid key length: expected 32 bytes, got {len(key)}")
    return key


def encrypt_file(file_path: str, key: bytes) -> None:
    """Encrypt a file in-place using AES-256-GCM."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)

    with open(file_path, "rb") as f:
        plaintext = f.read()

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    with open(file_path, "wb") as f:
        f.write(nonce)
        f.write(ciphertext)

    logger.debug("Encrypted %s (%d -> %d bytes)", file_path, len(plaintext), NONCE_SIZE + len(ciphertext))


def decrypt_file(file_path: str, key: bytes) -> bytes:
    """Decrypt a file and return plaintext bytes. File on disk is unchanged."""
    aesgcm = AESGCM(key)

    with open(file_path, "rb") as f:
        data = f.read()

    nonce = data[:NONCE_SIZE]
    ciphertext = data[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, None)


def decrypt_to_tempfile(file_path: str, key: bytes, suffix: str = "") -> str:
    """Decrypt a file to a temporary file. Caller must delete the temp file."""
    plaintext = decrypt_file(file_path, key)

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, plaintext)
    finally:
        os.close(fd)

    return tmp_path


class KeyStore:
    """Thread-safe in-memory store for per-job encryption keys.

    Keys live only in RAM and are lost on server restart — by design.
    """

    def __init__(self):
        self._keys: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def store(self, job_id: str, key: bytes) -> None:
        with self._lock:
            self._keys[job_id] = key

    def get(self, job_id: str) -> bytes | None:
        with self._lock:
            return self._keys.get(job_id)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._keys.pop(job_id, None)

    def delete_many(self, job_ids: list[str]) -> None:
        with self._lock:
            for jid in job_ids:
                self._keys.pop(jid, None)
