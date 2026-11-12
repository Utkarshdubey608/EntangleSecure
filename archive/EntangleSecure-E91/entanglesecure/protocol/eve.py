"""Intercept-resend eavesdropping on Bob's particle.

Eve measures Bob's particle along a direction θ_E and forwards a fresh qubit
prepared in the eigenstate |e, θ_E> she observed. Because the projector is
rank-1 on Bob's qubit, "measure then resend the observed eigenstate" equals the
Lüders update ρ → (I ⊗ Π_e) ρ (I ⊗ Π_e) / p_e. For the singlet this also
collapses Alice's particle to |−e, θ_E>: the pair is now a product state, so
its statistics obey every Bell inequality.

Limitations: a single, individual (sub-optimal) attack strategy; no ancilla
entangling attacks, no collective/coherent attacks, no attack on Alice's arm.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..quantum import measure_qubit

BOB_QUBIT = 1


@dataclass(frozen=True)
class EveBranch:
    angle_index: int
    outcome: int  # +1 / −1, Eve's recorded result
    probability: float  # p(e | θ_E)
    state: np.ndarray  # post-attack two-qubit state forwarded to Alice/Bob


def intercept_resend_branches(rho: np.ndarray, eve_angles_rad: np.ndarray) -> list[EveBranch]:
    """All (direction, outcome) branches of Eve's measurement on Bob's particle."""
    branches: list[EveBranch] = []
    for k, theta in enumerate(eve_angles_rad):
        for e in (1, -1):
            p, post = measure_qubit(rho, BOB_QUBIT, float(theta), e)
            branches.append(EveBranch(k, e, p, post))
    return branches


def eve_guess_bits(eve_outcome: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Eve's guess of Bob's raw bit: her own outcome where she intercepted, a coin flip otherwise."""
    guess = (1 - eve_outcome) // 2  # +1 → 0, −1 → 1
    no_info = eve_outcome == 0
    guess = guess.astype(np.uint8)
    guess[no_info] = rng.integers(0, 2, size=int(no_info.sum()), dtype=np.uint8)
    return guess
