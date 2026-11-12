"""Closed-form predictions, written independently of the density-matrix engine.

These formulas are used (a) as theory overlays in the UI and (b) as an
independent oracle in the test-suite for the simulated statistics.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from .config import ExperimentConfig
from .roles import CHSH_SETTINGS, KEY_SETTINGS, bob_flips

TSIRELSON_BOUND = 2 * math.sqrt(2)
CLASSICAL_BOUND = 2.0


def binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * math.log2(p) - (1 - p) * math.log2(1 - p))


def visibility(depolarizing_noise: float) -> float:
    """Local depolarizing noise p on both particles turns |ψ⁻> into a Werner state of visibility (1 − p)²."""
    return (1.0 - depolarizing_noise) ** 2


def correlation(
    a: float,
    b: float,
    vis: float = 1.0,
    intercept_fraction: float = 0.0,
    eve_angles: Sequence[float] = (),
) -> float:
    """E(a, b) in radians for the (noisy, possibly attacked) singlet.

    No attack: −V cos(a − b). Intercept-resend along θ on Bob's particle leaves the
    product state |−e,θ>|e,θ>, giving −V cos(a − θ) cos(b − θ), averaged over Eve's directions.
    """
    ideal = -math.cos(a - b)
    if intercept_fraction > 0 and len(eve_angles) > 0:
        attacked = float(np.mean([-math.cos(a - t) * math.cos(b - t) for t in eve_angles]))
        e = (1 - intercept_fraction) * ideal + intercept_fraction * attacked
    else:
        e = ideal
    return vis * e


def correlation_matrix(config: ExperimentConfig) -> np.ndarray:
    alice = np.radians(config.alice_angles_deg)
    bob = np.radians(config.bob_angles_deg)
    q, eve = _eve_params(config)
    vis = visibility(config.depolarizing_noise)
    return np.array([[correlation(a, b, vis, q, eve) for b in bob] for a in alice])


def chsh_value(config: ExperimentConfig, labelling) -> float:
    """Predicted |S| for a given CHSH labelling (see chsh.CHSHLabelling)."""
    m = correlation_matrix(config)
    s = sum(sign * m[i, j] for (i, j), sign in labelling.terms())
    return abs(float(s))


def qber(config: ExperimentConfig) -> float:
    """Expected QBER of the sifted key, averaged over the equally likely key settings."""
    m = correlation_matrix(config)
    alice = np.radians(config.alice_angles_deg)
    bob = np.radians(config.bob_angles_deg)
    errors = []
    for i, j in KEY_SETTINGS:
        e = m[i, j]
        # Bob flips his bit when anti-correlation is expected: error ⇔ equal outcomes.
        errors.append((1 + e) / 2 if bob_flips(alice[i], bob[j]) else (1 - e) / 2)
    return float(np.mean(errors))


def role_probabilities() -> dict[str, float]:
    return {"key": len(KEY_SETTINGS) / 9, "chsh": len(CHSH_SETTINGS) / 9, "discard": 1 - (len(KEY_SETTINGS) + len(CHSH_SETTINGS)) / 9}


def eve_holevo_bound(s: float) -> float:
    """Upper bound on Eve's information per bit for a CHSH value S (Acín et al., PRL 98, 230501, 2007)."""
    if not math.isfinite(s) or s <= CLASSICAL_BOUND:
        return 1.0
    s = min(s, TSIRELSON_BOUND)
    return binary_entropy((1 + math.sqrt((s / 2) ** 2 - 1)) / 2)


def di_key_rate(s: float, q: float) -> float:
    """Device-independent asymptotic key rate per sifted bit: 1 − h(Q) − χ(S), clipped at 0."""
    return max(0.0, 1.0 - binary_entropy(q) - eve_holevo_bound(s))


def bbm92_key_rate(q: float) -> float:
    """Standard (device-dependent) entanglement-based BB84/BBM92 asymptotic rate 1 − 2h(Q)."""
    return max(0.0, 1.0 - 2.0 * binary_entropy(q))


def _eve_params(config: ExperimentConfig) -> tuple[float, tuple[float, ...]]:
    if not config.eve.enabled:
        return 0.0, ()
    return config.eve.intercept_fraction, tuple(np.radians(config.eve.basis_angles_deg))
