"""Projective spin measurements along directions in the x–z plane of the Bloch sphere.

Convention: a direction θ (radians) corresponds to the unit vector
n(θ) = (sin θ, 0, cos θ) and the observable σ(θ) = cos θ Z + sin θ X.
Outcome +1 ↔ |+θ> = cos(θ/2)|0> + sin(θ/2)|1>,
outcome −1 ↔ |−θ> = −sin(θ/2)|0> + cos(θ/2)|1>.

Physically a measurement along θ is implemented as the basis change R_y(−θ)
followed by a computational-basis (Z) measurement: R_y(−θ)|±θ> = |0>/|1>.
"""

from __future__ import annotations

import numpy as np

from .gates import X, Z, kron, on_qubit, ry

OUTCOMES = (1, -1)  # index 0 ↔ +1, index 1 ↔ −1


def spin_observable(theta: float) -> np.ndarray:
    return np.cos(theta) * Z + np.sin(theta) * X


def eigenstate(theta: float, outcome: int) -> np.ndarray:
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    if outcome == 1:
        return np.array([c, s], dtype=complex)
    if outcome == -1:
        return np.array([-s, c], dtype=complex)
    raise ValueError(f"outcome must be +1 or -1, got {outcome}")


def projector(theta: float, outcome: int) -> np.ndarray:
    v = eigenstate(theta, outcome)
    return np.outer(v, v.conj())


def basis_change(theta: float) -> np.ndarray:
    """Unitary that rotates the θ-measurement basis onto the computational basis."""
    return ry(-theta)


def joint_probabilities(rho: np.ndarray, theta_a: float, theta_b: float) -> np.ndarray:
    """Born-rule joint distribution P[x, y] for Alice (qubit 0) along θ_a and Bob (qubit 1) along θ_b.

    Computed circuit-style: ρ' = (U_a ⊗ U_b) ρ (U_a ⊗ U_b)†, P = diag(ρ').
    Index 0 ↔ outcome +1, index 1 ↔ outcome −1 for each party.
    """
    u = kron(basis_change(theta_a), basis_change(theta_b))
    rotated = u @ rho @ u.conj().T
    probs = np.clip(np.real(np.diag(rotated)), 0.0, None)
    probs = probs / probs.sum()
    return probs.reshape(2, 2)


def joint_probabilities_projective(rho: np.ndarray, theta_a: float, theta_b: float) -> np.ndarray:
    """Same distribution computed directly from Tr[(Π_x ⊗ Π_y) ρ] — used to cross-check."""
    out = np.empty((2, 2))
    for i, x in enumerate(OUTCOMES):
        for j, y in enumerate(OUTCOMES):
            out[i, j] = np.real(np.trace(kron(projector(theta_a, x), projector(theta_b, y)) @ rho))
    return out


def correlation(rho: np.ndarray, theta_a: float, theta_b: float) -> float:
    """E(a, b) = <σ(a) ⊗ σ(b)>."""
    return float(np.real(np.trace(kron(spin_observable(theta_a), spin_observable(theta_b)) @ rho)))


def measure_qubit(rho: np.ndarray, qubit: int, theta: float, outcome: int) -> tuple[float, np.ndarray]:
    """Lüders rule: probability of ``outcome`` and the normalised post-measurement state.

    Returns (p, ρ_post); ρ_post is None-safe: if p == 0 the input state is returned.
    """
    proj = on_qubit(projector(theta, outcome), qubit)
    unnormalised = proj @ rho @ proj
    p = float(np.real(np.trace(unnormalised)))
    if p <= 1e-15:
        return 0.0, rho
    return p, unnormalised / p
