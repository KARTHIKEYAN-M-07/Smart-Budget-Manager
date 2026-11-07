"""Cryptographic, Session, and Hashing Security Services"""

import base64
import hashlib
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

# Argon2id hasher configured per SECURITY.md (memory 64MB, time cost 3, 4 lanes)
pwd_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id with per-user salt."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    return pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    try:
        return pwd_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def generate_session_token() -> str:
    """Generates a cryptographically secure 256-bit random session token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hashes a session token using SHA-256 for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """Generates a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


# ------------------------------------------------------------------------------
# Field-Level Encryption (AES-256-GCM)
# ------------------------------------------------------------------------------
def _get_aes_key(key: str | bytes | None = None) -> bytes:
    """Derives a 32-byte key for AES-256-GCM from settings or provided argument."""
    raw_key = key or settings.FIELD_ENCRYPTION_KEY
    if isinstance(raw_key, str):
        # Derive fixed 32-byte key via SHA-256
        return hashlib.sha256(raw_key.encode("utf-8")).digest()
    if len(raw_key) != 32:
        return hashlib.sha256(raw_key).digest()
    return raw_key


def encrypt_field(plaintext: str, key: str | bytes | None = None) -> str:
    """
    Encrypts sensitive text (e.g. account numbers) using AES-256-GCM.
    Returns base64 encoded string containing nonce + ciphertext + tag.
    """
    if not plaintext:
        return ""
    aes_key = _get_aes_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_field(ciphertext_b64: str, key: str | bytes | None = None) -> str:
    """Decrypts base64 encoded AES-256-GCM ciphertext."""
    if not ciphertext_b64:
        return ""
    aes_key = _get_aes_key(key)
    data = base64.b64decode(ciphertext_b64.encode("utf-8"))
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(aes_key)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")
