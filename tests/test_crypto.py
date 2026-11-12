import os
import random

import pytest
from cryptography.exceptions import InvalidTag

from qvote.crypto import pqc, shor
from qvote.crypto.passwords import check_password, hash_password


def test_kem_and_signature_sizes_match_fips():
    kem, sig = pqc.kem_keygen(), pqc.sig_keygen()
    assert len(kem.public) == 1184 and len(sig.public) == 1952
    assert len(pqc.sign(sig.secret, b"m")) == 3309


def test_ballot_round_trip():
    kem = pqc.kem_keygen()
    enc = pqc.encrypt_ballot(kem.public, b'{"c":"c1"}', b"el_1")
    assert len(enc.kem_ciphertext) == 1088 and len(enc.nonce) == 12
    assert pqc.decrypt_ballot(kem.secret, enc.kem_ciphertext, enc.nonce, enc.ciphertext, b"el_1") == b'{"c":"c1"}'
    assert [s.step for s in enc.trace][0].startswith("ML-KEM-768")


def test_ballot_encryption_is_randomised():
    kem = pqc.kem_keygen()
    a = pqc.encrypt_ballot(kem.public, b"same", b"ctx")
    b = pqc.encrypt_ballot(kem.public, b"same", b"ctx")
    assert a.kem_ciphertext != b.kem_ciphertext and a.ciphertext != b.ciphertext


@pytest.mark.parametrize("field", ["ciphertext", "nonce", "context", "key"])
def test_tampering_or_wrong_key_is_rejected(field):
    kem, other = pqc.kem_keygen(), pqc.kem_keygen()
    enc = pqc.encrypt_ballot(kem.public, b"vote", b"ctx")
    ct, nonce, ctx, sk = bytearray(enc.ciphertext), enc.nonce, b"ctx", kem.secret
    if field == "ciphertext":
        ct[0] ^= 1
    elif field == "nonce":
        nonce = os.urandom(12)
    elif field == "context":
        ctx = b"other-election"
    else:
        sk = other.secret
    with pytest.raises(InvalidTag):
        pqc.decrypt_ballot(sk, enc.kem_ciphertext, nonce, bytes(ct), ctx)


def test_signature_verification():
    sig = pqc.sig_keygen()
    s = pqc.sign(sig.secret, b"receipt")
    assert pqc.verify(sig.public, b"receipt", s)
    assert not pqc.verify(sig.public, b"receipt!", s)
    assert not pqc.verify(pqc.sig_keygen().public, b"receipt", s)
    assert not pqc.verify(sig.public, b"receipt", b"garbage")


def test_hash_is_length_prefixed():
    assert pqc.sha3(b"ab", b"c") != pqc.sha3(b"a", b"bc")


def test_passwords():
    digest, salt = hash_password("qv-001")
    assert check_password("qv-001", digest, salt)
    assert not check_password("qv-002", digest, salt)


def test_order_finding_and_factoring():
    assert shor.multiplicative_order(7, 15) == 4
    for seed in range(5):
        rng = random.Random(seed)
        key = shor.make_toy_rsa(rng)
        p, q, _, steps = shor.factor_with_period(key.n, rng)
        assert {p, q} == {key.p, key.q} and steps
        assert pow(key.encrypt(5), pow(key.e, -1, (p - 1) * (q - 1)), key.n) == 5
