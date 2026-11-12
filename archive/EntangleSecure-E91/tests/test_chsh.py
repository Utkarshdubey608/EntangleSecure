"""CHSH Bell-inequality analysis."""

import itertools
import math

import numpy as np
import pytest

from entanglesecure.protocol import ExperimentConfig, choose_labelling, run_measurement_only
from entanglesecure.protocol.chsh import correlator_from_counts
from entanglesecure.protocol.theory import CLASSICAL_BOUND, TSIRELSON_BOUND, chsh_value, correlation_matrix

EKERT_A = np.radians([0, 45, 90])
EKERT_B = np.radians([45, 90, 135])


def test_default_labelling_matches_ekert():
    lab = choose_labelling(EKERT_A, EKERT_B)
    # a = A2 (90°), a′ = A0 (0°), b = B0 (45°), b′ = B2 (135°)
    assert (lab.a, lab.a_prime, lab.b, lab.b_prime) == (2, 0, 0, 2)


def test_ideal_chsh_is_tsirelson_bound():
    cfg = ExperimentConfig().validate()
    lab = choose_labelling(EKERT_A, EKERT_B)
    assert math.isclose(chsh_value(cfg, lab), TSIRELSON_BOUND, rel_tol=1e-12)


def test_correlator_estimator():
    counts = np.array([[10, 30], [30, 10]])
    e, se = correlator_from_counts(counts)
    assert math.isclose(e, -0.5)
    assert math.isclose(se, math.sqrt((1 - 0.25) / 80))
    assert all(math.isnan(v) for v in correlator_from_counts(np.zeros((2, 2))))


def test_simulated_s_approaches_tsirelson_for_large_samples():
    rounds, bell = run_measurement_only(ExperimentConfig(n_pairs=400_000, seed=11))
    assert bell.s_stderr < 0.01
    assert abs(bell.s_value - TSIRELSON_BOUND) < 5 * bell.s_stderr
    assert bell.violates_classical and bell.violation_confirmed
    assert bell.significance > 50


def test_all_nine_correlators_within_statistical_error():
    cfg = ExperimentConfig(n_pairs=200_000, seed=5)
    _, bell = run_measurement_only(cfg)
    th = correlation_matrix(cfg.validate())
    for (i, j), c in bell.correlators.items():
        assert abs(c.expectation - th[i, j]) < 5 * c.stderr + 1e-9, (i, j)


def test_local_hidden_variable_model_never_violates():
    """Deterministic local strategies (±1 per setting) obey |S| ≤ 2 — checked exhaustively."""
    best = 0
    for a0, a2, b0, b2 in itertools.product((1, -1), repeat=4):
        s = abs(a2 * b0 + a2 * b2 + a0 * b0 - a0 * b2)
        best = max(best, s)
    assert best == CLASSICAL_BOUND


def test_separable_product_states_never_exceed_two():
    """Random product states of two qubits: |S| ≤ 2 with optimal Ekert settings."""
    from entanglesecure.quantum import correlation

    rng = np.random.default_rng(0)
    lab = choose_labelling(EKERT_A, EKERT_B)
    for _ in range(200):
        vs = []
        for _ in range(2):
            v = rng.normal(size=2) + 1j * rng.normal(size=2)
            vs.append(v / np.linalg.norm(v))
        psi = np.kron(*vs)
        rho = np.outer(psi, psi.conj())
        s = abs(sum(sign * correlation(rho, EKERT_A[i], EKERT_B[j]) for (i, j), sign in lab.terms()))
        assert s <= 2 + 1e-12


def test_labelling_chosen_from_angles_not_data():
    """Same angles ⇒ same labelling regardless of the seed / data."""
    labs = {run_measurement_only(ExperimentConfig(n_pairs=500, seed=s))[1].labelling for s in range(5)}
    assert len(labs) == 1


def test_s_error_shrinks_like_inverse_sqrt_n():
    _, small = run_measurement_only(ExperimentConfig(n_pairs=10_000, seed=3))
    _, large = run_measurement_only(ExperimentConfig(n_pairs=160_000, seed=3))
    ratio = small.s_stderr / large.s_stderr
    assert 3.5 < ratio < 4.5  # √16 = 4


@pytest.mark.parametrize("noise", [0.0, 0.1, 0.2])
def test_noise_reduces_s_as_predicted(noise):
    cfg = ExperimentConfig(n_pairs=200_000, depolarizing_noise=noise, seed=8)
    _, bell = run_measurement_only(cfg)
    expected = TSIRELSON_BOUND * (1 - noise) ** 2
    assert abs(bell.s_value - expected) < 5 * bell.s_stderr
