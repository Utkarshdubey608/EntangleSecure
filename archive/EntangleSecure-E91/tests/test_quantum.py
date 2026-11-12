"""Validation of the exact two-qubit simulator."""

import numpy as np
import pytest

from entanglesecure.quantum import (
    concurrence,
    correlation,
    density_matrix,
    depolarize_both,
    depolarizing_kraus,
    eigenstate,
    is_valid_density_matrix,
    joint_probabilities,
    joint_probabilities_projective,
    measure_qubit,
    partial_trace,
    prepare_singlet_statevector,
    purity,
    spin_observable,
)

ANGLES = np.radians([0, 22.5, 45, 90, 135, 180, 237, 300])


@pytest.fixture
def singlet():
    return prepare_singlet_statevector()


def test_singlet_amplitudes(singlet):
    expected = np.array([0, 1, -1, 0]) / np.sqrt(2)
    np.testing.assert_allclose(singlet, expected, atol=1e-12)
    assert np.isclose(np.linalg.norm(singlet), 1.0)


def test_singlet_density_matrix_properties(singlet):
    rho = density_matrix(singlet)
    assert is_valid_density_matrix(rho)
    assert np.isclose(purity(rho), 1.0)
    assert np.isclose(concurrence(rho), 1.0)
    # Maximally entangled: both reduced states maximally mixed.
    np.testing.assert_allclose(partial_trace(rho, 0), np.eye(2) / 2, atol=1e-12)
    np.testing.assert_allclose(partial_trace(rho, 1), np.eye(2) / 2, atol=1e-12)


def test_singlet_is_rotationally_invariant(singlet):
    """σ(θ)⊗σ(θ)|ψ⁻> = −|ψ⁻> for any θ: perfect anti-correlation in every common direction."""
    for t in ANGLES:
        op = np.kron(spin_observable(t), spin_observable(t))
        np.testing.assert_allclose(op @ singlet, -singlet, atol=1e-12)


@pytest.mark.parametrize("theta", ANGLES)
def test_eigenstates(theta):
    obs = spin_observable(theta)
    for outcome in (1, -1):
        v = eigenstate(theta, outcome)
        np.testing.assert_allclose(obs @ v, outcome * v, atol=1e-12)


def test_circuit_measurement_equals_projectors(singlet):
    rho = density_matrix(singlet)
    for a in ANGLES:
        for b in ANGLES:
            np.testing.assert_allclose(joint_probabilities(rho, a, b), joint_probabilities_projective(rho, a, b), atol=1e-12)


def test_born_probabilities_match_closed_form(singlet):
    """P(x, y | a, b) = (1 − x y cos(a − b)) / 4 for the singlet; marginals are 1/2."""
    rho = density_matrix(singlet)
    for a in ANGLES:
        for b in ANGLES:
            p = joint_probabilities(rho, a, b)
            for i, x in enumerate((1, -1)):
                for j, y in enumerate((1, -1)):
                    assert np.isclose(p[i, j], (1 - x * y * np.cos(a - b)) / 4, atol=1e-12)
            np.testing.assert_allclose(p.sum(axis=1), [0.5, 0.5], atol=1e-12)
            np.testing.assert_allclose(p.sum(axis=0), [0.5, 0.5], atol=1e-12)


def test_correlation_is_minus_cosine(singlet):
    rho = density_matrix(singlet)
    for a in ANGLES:
        for b in ANGLES:
            assert np.isclose(correlation(rho, a, b), -np.cos(a - b), atol=1e-12)


def test_measurement_collapse(singlet):
    """After Alice obtains x along θ, Bob's particle is in |−x, θ>."""
    rho = density_matrix(singlet)
    theta = np.radians(30)
    for x in (1, -1):
        p, post = measure_qubit(rho, 0, theta, x)
        assert np.isclose(p, 0.5)
        bob = partial_trace(post, 1)
        v = eigenstate(theta, -x)
        np.testing.assert_allclose(bob, np.outer(v, v.conj()), atol=1e-12)
        assert np.isclose(concurrence(post), 0.0, atol=1e-6)


def test_depolarizing_kraus_complete():
    for p in (0, 0.1, 0.5, 1):
        s = sum(k.conj().T @ k for k in depolarizing_kraus(p))
        np.testing.assert_allclose(s, np.eye(2), atol=1e-12)
    with pytest.raises(ValueError):
        depolarizing_kraus(1.5)


@pytest.mark.parametrize("p", [0.0, 0.05, 0.2, 0.5])
def test_depolarizing_gives_werner_visibility(singlet, p):
    rho = depolarize_both(density_matrix(singlet), p)
    assert is_valid_density_matrix(rho)
    v = (1 - p) ** 2
    for a in ANGLES[:4]:
        for b in ANGLES[:4]:
            assert np.isclose(correlation(rho, a, b), -v * np.cos(a - b), atol=1e-12)
    # Werner state: entangled iff V > 1/3, concurrence = max(0, (3V − 1)/2).
    assert np.isclose(concurrence(rho), max(0.0, (3 * v - 1) / 2), atol=1e-9)
