"""Intercept-resend eavesdropping."""

import math
from dataclasses import replace

import numpy as np

from entanglesecure.analysis import eve_sweep
from entanglesecure.protocol import INSECURE, EveConfig, ExperimentConfig, run_experiment
from entanglesecure.protocol.e91 import build_quantum_model
from entanglesecure.protocol.theory import CLASSICAL_BOUND, chsh_value, qber
from entanglesecure.quantum import concurrence, is_valid_density_matrix


def full_attack(n=200_000, seed=21, **eve):
    return ExperimentConfig(n_pairs=n, seed=seed, eve=EveConfig(enabled=True, **eve))


def test_eve_branches_are_physical_and_disentangled():
    model = build_quantum_model(full_attack(n=100).validate())
    assert len(model.eve_branches) == 6
    for br in model.eve_branches:
        assert math.isclose(br.probability, 0.5, abs_tol=1e-12)
        assert is_valid_density_matrix(br.state)
        assert concurrence(br.state) < 1e-6  # product state after measure-resend (sqrt amplifies float noise)
    np.testing.assert_allclose(model.eve_outcome_probs.sum(axis=1), 1.0)


def test_qber_matches_analytic_prediction():
    """Eve guessing among Bob's directions: QBER = ½[½(1 − ⟨cos²⟩)] averaged over key settings ≈ 20.8 %."""
    cfg = full_attack()
    r = run_experiment(cfg)
    expected = 0.5 * (0.5 * (1 - 0.5) + 0.5 * (1 - 2 / 3))
    assert math.isclose(qber(cfg.validate()), expected, rel_tol=1e-12)
    sd = math.sqrt(expected * (1 - expected) / len(r.keys.sifted))
    assert abs(r.keys.sifted_qber - expected) < 5 * sd


def test_full_attack_destroys_bell_violation():
    r = run_experiment(full_attack())
    assert r.bell.s_value < CLASSICAL_BOUND
    assert abs(r.bell.s_value - r.bell.s_theory) < 5 * r.bell.s_stderr
    assert not r.bell.violates_classical
    assert r.keys.aborted and r.keys.final_length == 0
    assert r.security_status == INSECURE


def test_separable_bound_holds_for_any_eve_direction():
    for angles in [(0.0,), (45.0,), (22.5, 112.5), (0.0, 30.0, 60.0, 90.0, 120.0, 150.0)]:
        cfg = full_attack(n=100, basis_angles_deg=angles).validate()
        from entanglesecure.protocol import choose_labelling

        lab = choose_labelling(np.radians(cfg.alice_angles_deg), np.radians(cfg.bob_angles_deg))
        assert chsh_value(cfg, lab) <= CLASSICAL_BOUND + 1e-12


def test_partial_attack_interpolates_linearly():
    df = eve_sweep(ExperimentConfig(n_pairs=150_000, seed=2), np.array([0.0, 0.5, 1.0]))
    for _, row in df.iterrows():
        assert abs(row.S - row.S_theory) < 5 * row.S_stderr
        assert abs(row.qber - row.qber_theory) < 0.01
    assert df.S.is_monotonic_decreasing and df.qber.is_monotonic_increasing


def test_eve_gains_information():
    r = run_experiment(full_attack(n=50_000))
    assert r.keys.eve_agreement > 0.75  # Eve learns a lot …
    off = run_experiment(replace(full_attack(n=50_000), eve=EveConfig(enabled=False)))
    assert abs(off.keys.eve_agreement - 0.5) < 0.03  # … and nothing without intercepting


def test_eve_increases_qber_relative_to_clean_channel():
    cfg = ExperimentConfig(n_pairs=30_000, seed=5)
    off, on = run_experiment(cfg), run_experiment(cfg.with_eve(True))
    assert off.keys.sifted_qber == 0.0
    assert on.keys.sifted_qber > 0.15
    assert on.bell.s_value < off.bell.s_value - 1.0
