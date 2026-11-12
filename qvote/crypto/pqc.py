"""Post-quantum primitives used by the election.

* ML-KEM-768 (NIST FIPS 203) encapsulates a fresh secret for every ballot.
* ML-DSA-65 (NIST FIPS 204) signs the manifest, receipts, the final bulletin head and the results.
* The KEM secret is stretched with HKDF-SHA3-256 into an AES-256-GCM key (KEM-DEM hybrid encryption).
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from dilithium_py.ml_dsa import ML_DSA_65
from kyber_py.ml_kem import ML_KEM_768

KEM_ALG = "ML-KEM-768"
SIG_ALG = "ML-DSA-65"
AEAD_ALG = "AES-256-GCM"
KDF_ALG = "HKDF-SHA3-256"
HASH_ALG = "SHA3-256"
NONCE_BYTES = 12


def sha3(*parts: bytes) -> bytes:
    """SHA3-256 over length-prefixed parts, so different splits never collide."""
    h = hashlib.sha3_256()
    for part in parts:
        h.update(len(part).to_bytes(4, "big"))
        h.update(part)
    return h.digest()


def fingerprint(public_key: bytes) -> str:
    return hashlib.sha3_256(public_key).hexdigest()


@dataclass(frozen=True)
class KemKeyPair:
    public: bytes
    secret: bytes


@dataclass(frozen=True)
class SigKeyPair:
    public: bytes
    secret: bytes


def kem_keygen() -> KemKeyPair:
    ek, dk = ML_KEM_768.keygen()
    return KemKeyPair(ek, dk)


def sig_keygen() -> SigKeyPair:
    pk, sk = ML_DSA_65.keygen()
    return SigKeyPair(pk, sk)


def sign(secret_key: bytes, message: bytes) -> bytes:
    return ML_DSA_65.sign(secret_key, message)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    try:
        return bool(ML_DSA_65.verify(public_key, message, signature))
    except Exception:
        return False


def _derive_key(shared_secret: bytes, context: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA3_256(), length=32, salt=None, info=b"qvote-ballot-v1|" + context).derive(shared_secret)


@dataclass
class TraceStep:
    step: str
    detail: str
    ms: float
    bytes: int | None = None

    def to_dict(self) -> dict:
        d = {"step": self.step, "detail": self.detail, "ms": round(self.ms, 2)}
        if self.bytes is not None:
            d["bytes"] = self.bytes
        return d


@dataclass
class EncryptedBallot:
    kem_ciphertext: bytes
    nonce: bytes
    ciphertext: bytes
    trace: list[TraceStep] = field(default_factory=list)


def encrypt_ballot(kem_public_key: bytes, plaintext: bytes, context: bytes) -> EncryptedBallot:
    """Encrypt to the election authority: only the holder of the ML-KEM secret key can open it."""
    t0 = time.perf_counter()
    shared, kem_ct = ML_KEM_768.encaps(kem_public_key)
    t1 = time.perf_counter()
    key = _derive_key(shared, context)
    t2 = time.perf_counter()
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext, context)
    t3 = time.perf_counter()
    trace = [
        TraceStep(f"{KEM_ALG} encapsulation", "Fresh 32-byte secret sealed to the authority's lattice public key", (t1 - t0) * 1e3, len(kem_ct)),
        TraceStep(f"{KDF_ALG} key derivation", "Shared secret stretched into a one-time 256-bit AES key", (t2 - t1) * 1e3),
        TraceStep(f"{AEAD_ALG} encryption", "Ballot encrypted and authenticated; any tampering breaks the 16-byte tag", (t3 - t2) * 1e3, len(ct)),
    ]
    return EncryptedBallot(kem_ct, nonce, ct, trace)


def decrypt_ballot(kem_secret_key: bytes, kem_ciphertext: bytes, nonce: bytes, ciphertext: bytes, context: bytes) -> bytes:
    """Raises cryptography.exceptions.InvalidTag if anything was modified."""
    shared = ML_KEM_768.decaps(kem_secret_key, kem_ciphertext)
    return AESGCM(_derive_key(shared, context)).decrypt(nonce, ciphertext, context)
