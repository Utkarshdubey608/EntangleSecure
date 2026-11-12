"""Cascade, Toeplitz hashing, key-rate bounds, abort logic."""

import math

import numpy as np
import pytest

from entanglesecure.protocol import ExperimentConfig, run_experiment
from entanglesecure.protocol.postprocessing import bits_to_hex, cascade, toeplitz_hash, toeplitz_matrix
from entanglesecure.protocol.theory import TSIRELSON_BOUND, bbm92_key_rate, binary_entropy, di_key_rate, eve_holevo_bound


@pytest.mark.parametrize("q", [0.01, 0.03, 0.06, 0.1])
def test_cascade_corrects_errors(q):
    rng = np.random.default_rng(42)
    n = 8000
    alice = rng.integers(0, 2, n, dtype=np.uint8)
    noise = (rng.random(n) < q).astype(np.uint8)
    bob = alice ^ noise
    corrected, rep = cascade(alice, bob, q, passes=4, rng=rng)
    assert rep.initial_errors == int(noise.sum())
    assert rep.residual_errors == 0 and rep.success
    np.testing.assert_array_equal(corrected, alice)
    assert rep.verification_passed
    # Leakage must exceed the Shannon limit n·h(Q) (no free lunch) but stay reasonable.
    assert n * binary_entropy(q) < rep.leaked_bits < 2.0 * n * binary_entropy(q) + 300


def test_cascade_on_identical_keys_leaks_only_parities():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 2, 1000, dtype=np.uint8)
    corrected, rep = cascade(a, a.copy(), 0.0, 4, rng)
    assert rep.initial_errors == 0 and rep.residual_errors == 0
    assert sum(rep.corrections_per_pass) == 0


def test_toeplitz_hash_matches_explicit_matrix():
    rng = np.random.default_rng(3)
    for n, m in [(10, 4), (257, 100), (3000, 1500)]:
        x = rng.integers(0, 2, n, dtype=np.uint8)
        s = rng.integers(0, 2, n + m - 1, dtype=np.uint8)
        explicit = (toeplitz_matrix(n, m, s).astype(np.int64) @ x) & 1
        np.testing.assert_array_equal(toeplitz_hash(x, m, s), explicit)


def test_toeplitz_fft_path_matches_direct_path():
    rng = np.random.default_rng(4)
    n, m = 6000, 3000  # n·m > 4e6 → FFT path
    x = rng.integers(0, 2, n, dtype=np.uint8)
    s = rng.integers(0, 2, n + m - 1, dtype=np.uint8)
    direct = (np.rint(np.convolve(s.astype(float), x.astype(float))[n - 1 : n - 1 + m]).astype(np.int64)) & 1
    np.testing.assert_array_equal(toeplitz_hash(x, m, s), direct)


def test_toeplitz_is_linear():
    rng = np.random.default_rng(5)
    n, m = 500, 200
    s = rng.integers(0, 2, n + m - 1, dtype=np.uint8)
    x, y = rng.integers(0, 2, (2, n), dtype=np.uint8)
    np.testing.assert_array_equal(toeplitz_hash(x ^ y, m, s), toeplitz_hash(x, m, s) ^ toeplitz_hash(y, m, s))


def test_key_rate_bounds():
    assert eve_holevo_bound(TSIRELSON_BOUND) == pytest.approx(0.0, abs=1e-12)
    assert eve_holevo_bound(2.0) == 1.0 and eve_holevo_bound(1.5) == 1.0
    assert eve_holevo_bound(float("nan")) == 1.0
    assert di_key_rate(TSIRELSON_BOUND, 0.0) == pytest.approx(1.0)
    assert di_key_rate(2.0, 0.0) == 0.0
    assert bbm92_key_rate(0.11) == pytest.approx(0.0, abs=0.003)  # ~11 % threshold
    assert binary_entropy(0.5) == 1.0 and binary_entropy(0.0) == 0.0


def test_bits_to_hex():
    assert bits_to_hex(np.array([1, 1, 1, 1, 0, 0, 0, 0], dtype=np.uint8)) == "f0"
    assert bits_to_hex(np.array([1], dtype=np.uint8)) == "80"
    assert bits_to_hex(np.zeros(0, dtype=np.uint8)) == ""


def test_noisy_channel_still_yields_identical_final_keys():
    r = run_experiment(ExperimentConfig(n_pairs=150_000, depolarizing_noise=0.02, seed=9))
    k = r.keys
    assert k.sifted_qber > 0
    assert k.cascade is not None and k.cascade.residual_errors == 0
    assert not k.aborted and k.keys_match
    expected_len = math.floor(k.remaining_length * (1 - k.eve_info_bound) - k.cascade.leaked_bits)
    assert k.final_length == expected_len


def test_abort_when_bell_test_fails():
    r = run_experiment(ExperimentConfig(n_pairs=20_000, depolarizing_noise=0.25))
    assert not r.bell.violation_confirmed
    assert r.keys.aborted and "Bell test failed" in r.keys.abort_reason
    assert r.keys.final_length == 0


def test_too_few_pairs_aborts_gracefully():
    r = run_experiment(ExperimentConfig(n_pairs=100, seed=1, detection_efficiency=0.1))
    assert r.keys.aborted
    assert r.keys.abort_reason
