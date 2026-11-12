"""One-time-pad messaging using bits distilled by E91.

Each message byte is XORed with a fresh 8 bits of the shared secret key, so the key
must never be reused and must be at least as long as the message in bits.
"""

from __future__ import annotations

import numpy as np


def required_key_bits(text: str) -> int:
    return 8 * len(text.encode("utf-8"))


def _key_bytes(key_bits: np.ndarray, n_bytes: int) -> np.ndarray:
    bits = np.asarray(key_bits, dtype=np.uint8).reshape(-1)
    needed = 8 * n_bytes
    if bits.size < needed:
        raise ValueError(
            f"Key too short: the message needs {needed:,} bits but only {bits.size:,} key bits are available."
        )
    return np.packbits(bits[:needed])


def encrypt(text: str, key_bits: np.ndarray) -> bytes:
    data = np.frombuffer(text.encode("utf-8"), dtype=np.uint8)
    return (data ^ _key_bytes(key_bits, data.size)).tobytes()


def decrypt(ciphertext: bytes, key_bits: np.ndarray) -> str:
    data = np.frombuffer(ciphertext, dtype=np.uint8)
    plain = data ^ _key_bytes(key_bits, data.size)
    return plain.tobytes().decode("utf-8", errors="replace")
