"""Quantum channels in Kraus form."""

from __future__ import annotations

import numpy as np

from .gates import I2, X, Y, Z, on_qubit


def depolarizing_kraus(p: float) -> list[np.ndarray]:
    """Kraus operators of D_p(ρ) = (1 − p) ρ + p I/2.

    K0 = √(1 − 3p/4) I, K1..3 = √(p/4) {X, Y, Z}.
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"depolarizing probability must be in [0, 1], got {p}")
    return [np.sqrt(1 - 3 * p / 4) * I2] + [np.sqrt(p / 4) * P for P in (X, Y, Z)]


def apply_channel(rho: np.ndarray, kraus: list[np.ndarray], qubit: int) -> np.ndarray:
    """Apply a single-qubit channel to ``qubit`` of a two-qubit density matrix."""
    out = np.zeros_like(rho)
    for k in kraus:
        k2 = on_qubit(k, qubit)
        out += k2 @ rho @ k2.conj().T
    return out


def depolarize_both(rho: np.ndarray, p: float) -> np.ndarray:
    """Independent depolarizing noise on Alice's and Bob's particles."""
    if p == 0:
        return rho
    kraus = depolarizing_kraus(p)
    return apply_channel(apply_channel(rho, kraus, 0), kraus, 1)
