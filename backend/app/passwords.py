from __future__ import annotations

import hashlib
import hmac
import secrets

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 310_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        prefix, iterations_text, salt, digest = encoded_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if prefix != PBKDF2_PREFIX:
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(derived, digest)
