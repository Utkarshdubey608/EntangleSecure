import numpy as np
import pytest

from entanglesecure.protocol.messaging import decrypt, encrypt, required_key_bits


def _key(n: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 2, n, dtype=np.uint8)


def test_round_trip():
    msg = "Quantum keys, classical messages."
    key = _key(required_key_bits(msg))
    assert decrypt(encrypt(msg, key), key) == msg


def test_wrong_key_does_not_recover_plaintext():
    msg = "Attack at dawn"
    cipher = encrypt(msg, _key(required_key_bits(msg), seed=1))
    assert decrypt(cipher, _key(required_key_bits(msg), seed=2)) != msg


def test_ciphertext_differs_from_plaintext():
    msg = "aaaaaaaa"
    cipher = encrypt(msg, _key(required_key_bits(msg)))
    assert cipher != msg.encode()
    assert len(cipher) == len(msg.encode())


def test_too_short_key_raises():
    msg = "hello"
    with pytest.raises(ValueError, match="Key too short"):
        encrypt(msg, _key(required_key_bits(msg) - 1))


def test_extra_key_bits_are_allowed():
    msg = "ok"
    assert decrypt(encrypt(msg, _key(1000)), _key(1000)) == msg


def test_empty_message():
    assert encrypt("", _key(0)) == b""
    assert decrypt(b"", _key(0)) == ""


def test_multibyte_utf8_round_trip():
    msg = "Grüße ⚛"
    key = _key(required_key_bits(msg))
    assert decrypt(encrypt(msg, key), key) == msg
