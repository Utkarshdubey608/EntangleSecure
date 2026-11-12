"""E91 rounds, sifting, key agreement, reproducibility."""

import math
from dataclasses import replace

import numpy as np

from entanglesecure.protocol import SECURE, ExperimentConfig, run_experiment
from entanglesecure.protocol.roles import ROLE_CHSH, ROLE_DISCARD, ROLE_KEY, ROLE_LOST, ROLE_MATRIX


def test_role_matrix():
    assert {(i, j) for i in range(3) for j in range(3) if ROLE_MATRIX[i, j] == ROLE_KEY} == {(1, 0), (2, 1)}
    assert {(i, j) for i in range(3) for j in range(3) if ROLE_MATRIX[i, j] == ROLE_CHSH} == {(0, 0), (0, 2), (2, 0), (2, 2)}
    assert int((ROLE_MATRIX == ROLE_DISCARD).sum()) == 3


def test_role_frequencies_follow_uniform_settings():
    r = run_experiment(ExperimentConfig(n_pairs=180_000, seed=1))
    counts = r.role_counts()
    n = 180_000
    for role, p in (("key", 2 / 9), ("chsh", 4 / 9), ("discard", 3 / 9)):
        sd = math.sqrt(n * p * (1 - p))
        assert abs(counts[role] - n * p) < 5 * sd, role
    assert counts["lost"] == 0
    assert sum(counts.values()) == n


def test_key_rounds_use_matching_directions():
    r = run_experiment(ExperimentConfig(n_pairs=5_000))
    cfg = r.config
    key = r.rounds.role == ROLE_KEY
    a = np.asarray(cfg.alice_angles_deg)[r.rounds.alice_setting[key]]
    b = np.asarray(cfg.bob_angles_deg)[r.rounds.bob_setting[key]]
    np.testing.assert_array_equal(a, b)


def test_ideal_keys_agree_perfectly():
    r = run_experiment(ExperimentConfig(n_pairs=20_000, seed=7))
    k = r.keys
    assert len(k.sifted) > 0
    np.testing.assert_array_equal(k.sifted.alice, k.sifted.bob)
    assert k.sifted_qber == 0.0 and k.agreement == 1.0
    assert not k.aborted and k.keys_match
    assert 0 < k.final_length < len(k.sifted)  # not every round contributes
    assert r.security_status == SECURE


def test_raw_outcomes_are_anticorrelated_on_key_rounds():
    r = run_experiment(ExperimentConfig(n_pairs=10_000))
    key = r.rounds.role == ROLE_KEY
    assert np.all(r.rounds.alice_outcome[key] == -r.rounds.bob_outcome[key])


def test_single_party_outcomes_are_unbiased():
    """No-signalling: each party alone sees fair coin flips."""
    r = run_experiment(ExperimentConfig(n_pairs=100_000, seed=2))
    for out in (r.rounds.alice_outcome, r.rounds.bob_outcome):
        assert abs(out.mean()) < 5 / math.sqrt(100_000)


def test_reproducibility_with_seed():
    cfg = ExperimentConfig(n_pairs=8_000, seed=1234, depolarizing_noise=0.03)
    a, b = run_experiment(cfg), run_experiment(cfg)
    for field in a.rounds.__dict__:
        np.testing.assert_array_equal(getattr(a.rounds, field), getattr(b.rounds, field))
    np.testing.assert_array_equal(a.keys.final_alice, b.keys.final_alice)
    assert a.bell.s_value == b.bell.s_value
    c = run_experiment(replace(cfg, seed=4321))
    assert not np.array_equal(a.rounds.alice_outcome, c.rounds.alice_outcome)


def test_eve_toggle_keeps_setting_choices():
    cfg = ExperimentConfig(n_pairs=5_000, seed=99)
    off, on = run_experiment(cfg), run_experiment(cfg.with_eve(True))
    np.testing.assert_array_equal(off.rounds.alice_setting, on.rounds.alice_setting)
    np.testing.assert_array_equal(off.rounds.bob_setting, on.rounds.bob_setting)


def test_misaligned_key_directions_raise_qber():
    cfg = ExperimentConfig(n_pairs=60_000, alice_angles_deg=(0, 60, 90), seed=3)  # A1 = 60° vs B0 = 45°
    r = run_experiment(cfg)
    # Key setting (A1,B0) errs with prob sin²(15°/2); (A2,B1) is still perfect.
    expected = 0.5 * math.sin(math.radians(7.5)) ** 2 + 0.5 * 0.0
    assert abs(r.keys.sifted_qber - expected) < 0.01
    assert abs(r.theory_qber - expected) < 1e-12


def test_detection_losses():
    r = run_experiment(ExperimentConfig(n_pairs=50_000, detection_efficiency=0.8, seed=4))
    lost = r.role_counts()["lost"]
    expected = 50_000 * (1 - 0.8**2)
    assert abs(lost - expected) < 5 * math.sqrt(50_000 * 0.36 * 0.64)
    assert np.all(r.rounds.alice_outcome[r.rounds.role == ROLE_LOST] == 0)
    assert r.keys.sifted_qber == 0.0


def test_metrics_are_complete_and_consistent():
    r = run_experiment(ExperimentConfig(n_pairs=10_000))
    m = r.metrics()
    assert m["key_rounds"] + m["chsh_rounds"] + m["discarded_rounds"] + m["lost_rounds"] == m["total_pairs"]
    assert m["alice_key_length"] == m["bob_key_length"] == m["key_rounds"]
    assert m["final_key_length"] <= len(m["final_key_hex"]) * 4 < m["final_key_length"] + 8
