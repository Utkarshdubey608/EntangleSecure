"""CHSH Bell-inequality analysis of measured E91 data.

S = |E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)|,  a, a′ ∈ {A0, A2},  b, b′ ∈ {B0, B2}.

The correlator carrying the minus sign is fixed *before* looking at data, as
the placement maximising |S| for an ideal singlet at the configured angles.
Choosing it from the measured data would bias S upwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .e91 import RoundData
from .roles import CHSH_SETTINGS, ROLE_LOST
from .theory import CLASSICAL_BOUND, TSIRELSON_BOUND


@dataclass(frozen=True)
class CHSHLabelling:
    """Mapping of protocol settings to the symbols a, a′, b, b′ (indices into A and B)."""

    a: int
    a_prime: int
    b: int
    b_prime: int

    def terms(self) -> list[tuple[tuple[int, int], int]]:
        """[(alice_idx, bob_idx), sign] in the order E(a,b), E(a,b′), E(a′,b), E(a′,b′)."""
        return [
            ((self.a, self.b), +1),
            ((self.a, self.b_prime), +1),
            ((self.a_prime, self.b), +1),
            ((self.a_prime, self.b_prime), -1),
        ]

    def symbols(self) -> list[str]:
        return ["E(a,b)", "E(a,b′)", "E(a′,b)", "E(a′,b′)"]


def choose_labelling(alice_rad: np.ndarray, bob_rad: np.ndarray) -> CHSHLabelling:
    """Pick which CHSH correlator carries the minus sign, using only the configured angles."""
    alice_pair = sorted({i for i, _ in CHSH_SETTINGS})  # [0, 2]
    bob_pair = sorted({j for _, j in CHSH_SETTINGS})  # [0, 2]
    best: tuple[float, CHSHLabelling] | None = None
    for a_prime in alice_pair:
        for b_prime in bob_pair:
            a = next(i for i in alice_pair if i != a_prime)
            b = next(j for j in bob_pair if j != b_prime)
            lab = CHSHLabelling(a, a_prime, b, b_prime)
            s = abs(sum(sign * -math.cos(alice_rad[i] - bob_rad[j]) for (i, j), sign in lab.terms()))
            if best is None or s > best[0] + 1e-12:
                best = (s, lab)
    assert best is not None
    return best[1]


@dataclass
class Correlator:
    alice_idx: int
    bob_idx: int
    counts: np.ndarray  # 2×2: [x=+1/−1, y=+1/−1]
    expectation: float
    stderr: float
    theory: float

    @property
    def n(self) -> int:
        return int(self.counts.sum())


@dataclass
class BellAnalysis:
    labelling: CHSHLabelling
    correlators: dict[tuple[int, int], Correlator]
    s_signed: float
    s_value: float
    s_stderr: float
    s_theory: float
    confidence_sigma: float
    chsh_rounds: int
    notes: list[str] = field(default_factory=list)

    @property
    def s_lower(self) -> float:
        """Conservative CHSH value S − zσ used for the security decision."""
        return self.s_value - self.confidence_sigma * self.s_stderr

    @property
    def violates_classical(self) -> bool:
        return bool(np.isfinite(self.s_value) and self.s_value > CLASSICAL_BOUND)

    @property
    def violation_confirmed(self) -> bool:
        """Violation that survives the z-sigma statistical margin."""
        return bool(np.isfinite(self.s_lower) and self.s_lower > CLASSICAL_BOUND)

    @property
    def significance(self) -> float:
        """Number of standard errors by which S exceeds the classical bound (negative if below)."""
        if not np.isfinite(self.s_value) or self.s_stderr <= 0:
            return float("nan")
        return (self.s_value - CLASSICAL_BOUND) / self.s_stderr

    @property
    def exceeds_tsirelson(self) -> bool:
        """A finite-sample estimate can fluctuate above 2√2; flag it (it is not a physical violation)."""
        return bool(np.isfinite(self.s_value) and self.s_value > TSIRELSON_BOUND)

    def chsh_terms(self) -> list[tuple[str, Correlator, int]]:
        return [(sym, self.correlators[idx], sign) for sym, (idx, sign) in zip(self.labelling.symbols(), self.labelling.terms())]

    def correlation_matrix(self) -> np.ndarray:
        m = np.full((3, 3), np.nan)
        for (i, j), c in self.correlators.items():
            m[i, j] = c.expectation
        return m

    def theory_matrix(self) -> np.ndarray:
        m = np.full((3, 3), np.nan)
        for (i, j), c in self.correlators.items():
            m[i, j] = c.theory
        return m


def correlator_from_counts(counts: np.ndarray) -> tuple[float, float]:
    """E = (N₊₊ + N₋₋ − N₊₋ − N₋₊)/N and its standard error √((1 − E²)/N)."""
    n = counts.sum()
    if n == 0:
        return float("nan"), float("nan")
    e = (counts[0, 0] + counts[1, 1] - counts[0, 1] - counts[1, 0]) / n
    return float(e), float(math.sqrt(max(1.0 - e * e, 0.0) / n))


def count_outcomes(rounds: RoundData) -> np.ndarray:
    """counts[i, j, x, y] over detected rounds; x/y index 0 ↔ +1, 1 ↔ −1."""
    ok = rounds.role != ROLE_LOST
    x = (rounds.alice_outcome[ok] == -1).astype(np.int64)
    y = (rounds.bob_outcome[ok] == -1).astype(np.int64)
    flat = ((rounds.alice_setting[ok].astype(np.int64) * 3 + rounds.bob_setting[ok]) * 2 + x) * 2 + y
    return np.bincount(flat, minlength=36).reshape(3, 3, 2, 2)


def analyze_bell(
    rounds: RoundData,
    alice_rad: np.ndarray,
    bob_rad: np.ndarray,
    theory_matrix: np.ndarray,
    confidence_sigma: float = 2.0,
    labelling: CHSHLabelling | None = None,
) -> BellAnalysis:
    labelling = labelling or choose_labelling(alice_rad, bob_rad)
    counts = count_outcomes(rounds)
    correlators: dict[tuple[int, int], Correlator] = {}
    for i in range(3):
        for j in range(3):
            e, se = correlator_from_counts(counts[i, j])
            correlators[(i, j)] = Correlator(i, j, counts[i, j], e, se, float(theory_matrix[i, j]))

    terms = labelling.terms()
    s_signed = float(sum(sign * correlators[idx].expectation for idx, sign in terms))
    s_err = float(math.sqrt(sum(correlators[idx].stderr ** 2 for idx, _ in terms)))
    s_theory = abs(float(sum(sign * theory_matrix[idx] for idx, sign in terms)))
    chsh_rounds = int(sum(correlators[idx].n for idx, _ in terms))

    notes: list[str] = []
    if any(correlators[idx].n == 0 for idx, _ in terms):
        notes.append("At least one CHSH setting combination has no detected rounds; S is undefined. Increase the number of pairs.")
    elif min(correlators[idx].n for idx, _ in terms) < 30:
        notes.append("Fewer than 30 rounds in some CHSH combination; statistical uncertainty is large.")
    s_value = abs(s_signed)
    if np.isfinite(s_value) and s_value > TSIRELSON_BOUND:
        notes.append("Measured S exceeds 2√2 only through finite-sample fluctuation; quantum theory forbids S > 2√2.")
    return BellAnalysis(labelling, correlators, s_signed, s_value, s_err, s_theory, confidence_sigma, chsh_rounds, notes)
