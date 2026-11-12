"""Voter password hashing with scrypt (memory-hard, standard library)."""

from __future__ import annotations

import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    salt = salt or os.urandom(16)
    return hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32), salt


def check_password(password: str, digest: bytes, salt: bytes) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, digest)
