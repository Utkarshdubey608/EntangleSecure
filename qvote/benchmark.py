"""Live performance and size comparison: post-quantum vs classical public-key cryptography."""

from __future__ import annotations

import statistics
import threading
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, x25519
from dilithium_py.ml_dsa import ML_DSA_65
from kyber_py.ml_kem import ML_KEM_768

NOTE = (
    "Timings are measured live on this server. ML-KEM and ML-DSA run as pure-Python reference "
    "implementations, while RSA and elliptic curves use OpenSSL's optimised C code, so this table "
    "overstates the post-quantum cost. Optimised ML-KEM is typically as fast as or faster than RSA."
)
_CACHE_SECONDS = 30
_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def _time(fn, repeats: int) -> float:
    samples = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1e3)
    return round(statistics.median(samples), 3)


def run_benchmark() -> dict:
    global _cache
    with _lock:
        if _cache and time.monotonic() - _cache[0] < _CACHE_SECONDS:
            return _cache[1]
        result = _measure()
        _cache = (time.monotonic(), result)
        return result


def _measure() -> dict:
    msg = b"QuantumVote benchmark ballot"
    rows: list[dict] = []

    def add(scheme: str, family: str, op: str, fn, repeats: int = 5) -> None:
        rows.append({"scheme": scheme, "family": family, "operation": op, "ms": _time(fn, repeats)})

    ek, dk = ML_KEM_768.keygen()
    _, kem_ct = ML_KEM_768.encaps(ek)
    add("ML-KEM-768", "post-quantum", "Key generation", ML_KEM_768.keygen)
    add("ML-KEM-768", "post-quantum", "Encapsulate", lambda: ML_KEM_768.encaps(ek))
    add("ML-KEM-768", "post-quantum", "Decapsulate", lambda: ML_KEM_768.decaps(dk, kem_ct))

    pk, sk = ML_DSA_65.keygen()
    sig = ML_DSA_65.sign(sk, msg)
    add("ML-DSA-65", "post-quantum", "Key generation", ML_DSA_65.keygen, 3)
    add("ML-DSA-65", "post-quantum", "Sign", lambda: ML_DSA_65.sign(sk, msg), 3)
    add("ML-DSA-65", "post-quantum", "Verify", lambda: ML_DSA_65.verify(pk, msg, sig), 3)

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_pub = rsa_key.public_key()
    oaep = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    rsa_ct = rsa_pub.encrypt(msg, oaep)
    rsa_sig = rsa_key.sign(msg, pss, hashes.SHA256())
    add("RSA-2048", "classical", "Key generation", lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048), 3)
    add("RSA-2048", "classical", "Encrypt (OAEP)", lambda: rsa_pub.encrypt(msg, oaep))
    add("RSA-2048", "classical", "Decrypt (OAEP)", lambda: rsa_key.decrypt(rsa_ct, oaep))
    add("RSA-2048", "classical", "Sign (PSS)", lambda: rsa_key.sign(msg, pss, hashes.SHA256()))
    add("RSA-2048", "classical", "Verify (PSS)", lambda: rsa_pub.verify(rsa_sig, msg, pss, hashes.SHA256()))

    ec_key = ec.generate_private_key(ec.SECP256R1())
    ec_sig = ec_key.sign(msg, ec.ECDSA(hashes.SHA256()))
    add("ECDSA P-256", "classical", "Key generation", lambda: ec.generate_private_key(ec.SECP256R1()))
    add("ECDSA P-256", "classical", "Sign", lambda: ec_key.sign(msg, ec.ECDSA(hashes.SHA256())))
    add("ECDSA P-256", "classical", "Verify", lambda: ec_key.public_key().verify(ec_sig, msg, ec.ECDSA(hashes.SHA256())))

    xa, xb = x25519.X25519PrivateKey.generate(), x25519.X25519PrivateKey.generate()
    add("X25519", "classical", "Key generation", x25519.X25519PrivateKey.generate)
    add("X25519", "classical", "Key exchange", lambda: xa.exchange(xb.public_key()))

    raw = serialization.Encoding.Raw, serialization.PublicFormat.Raw
    sizes = [
        {"scheme": "ML-KEM-768", "family": "post-quantum", "purpose": "Key exchange", "public_key": len(ek), "ciphertext_or_signature": len(kem_ct), "quantum_safe": True},
        {"scheme": "ML-DSA-65", "family": "post-quantum", "purpose": "Signature", "public_key": len(pk), "ciphertext_or_signature": len(sig), "quantum_safe": True},
        {"scheme": "RSA-2048", "family": "classical", "purpose": "Encryption / signature", "public_key": rsa_pub.key_size // 8, "ciphertext_or_signature": len(rsa_ct), "quantum_safe": False},
        {"scheme": "ECDSA P-256", "family": "classical", "purpose": "Signature", "public_key": len(ec_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint)), "ciphertext_or_signature": len(ec_sig), "quantum_safe": False},
        {"scheme": "X25519", "family": "classical", "purpose": "Key exchange", "public_key": len(xa.public_key().public_bytes(*raw)), "ciphertext_or_signature": len(xb.public_key().public_bytes(*raw)), "quantum_safe": False},
    ]
    return {"rows": rows, "sizes": sizes, "note": NOTE}
