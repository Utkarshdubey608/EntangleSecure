"""Classical post-processing: sifting → parameter estimation → Cascade → verification → privacy amplification.

What is real and what is idealised:
* Sifting, parameter estimation, Cascade and Toeplitz hashing are genuine
  algorithms operating on the simulated bit strings, and every bit disclosed
  over the public channel is counted.
* The classical channel is assumed authenticated (not implemented).
* The final key length uses the asymptotic device-independent bound
  χ(S) of Acín et al. (2007) for collective attacks; finite-key corrections
  are not applied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import theory
from .chsh import BellAnalysis
from .e91 import RoundData
from .eve import eve_guess_bits
from .roles import ROLE_KEY, bob_flips

VERIFY_TAG_BITS = 64
MIN_SIFTED_BITS = 16
MIN_QBER_FOR_BLOCKS = 0.005  # Cascade block size floor when the estimate is 0


def outcome_to_bit(outcome: np.ndarray) -> np.ndarray:
    """+1 → 0, −1 → 1."""
    return ((1 - outcome.astype(np.int16)) // 2).astype(np.uint8)


# ---------------------------------------------------------------------------
# Sifting
# ---------------------------------------------------------------------------


@dataclass
class SiftedKeys:
    round_index: np.ndarray  # index into RoundData of each sifted bit
    alice: np.ndarray  # uint8 bits
    bob: np.ndarray  # uint8 bits after Bob's anti-correlation flip
    eve_guess: np.ndarray  # Eve's guess of Bob's bit
    intercepted: np.ndarray  # bool per sifted bit

    def __len__(self) -> int:
        return int(self.alice.size)


def sift(rounds: RoundData, alice_rad: np.ndarray, bob_rad: np.ndarray, rng: np.random.Generator) -> SiftedKeys:
    idx = np.flatnonzero(rounds.role == ROLE_KEY)
    a_bits = outcome_to_bit(rounds.alice_outcome[idx])
    b_bits = outcome_to_bit(rounds.bob_outcome[idx])
    flip_table = np.array([[bob_flips(a, b) for b in bob_rad] for a in alice_rad])
    flips = flip_table[rounds.alice_setting[idx], rounds.bob_setting[idx]]
    b_bits = np.where(flips, b_bits ^ 1, b_bits).astype(np.uint8)
    eve_bits = eve_guess_bits(rounds.eve_outcome[idx], rng)
    eve_bits = np.where(flips, eve_bits ^ 1, eve_bits).astype(np.uint8)
    # Eve guessed Bob's *raw* outcome; apply the same public flip rule Bob uses.
    return SiftedKeys(idx, a_bits, b_bits, eve_bits, rounds.intercepted[idx])


# ---------------------------------------------------------------------------
# Cascade error correction (Brassard & Salvail, 1993)
# ---------------------------------------------------------------------------


@dataclass
class CascadeReport:
    initial_errors: int
    residual_errors: int
    leaked_bits: int
    block_sizes: list[int]
    corrections_per_pass: list[int]
    verification_passed: bool

    @property
    def success(self) -> bool:
        return self.residual_errors == 0


def cascade(
    alice: np.ndarray,
    bob: np.ndarray,
    qber_estimate: float,
    passes: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, CascadeReport]:
    """Correct Bob's key towards Alice's by interactive parity comparison.

    Pass 1 uses contiguous blocks of size k₁ ≈ 0.73/Q; each later pass doubles the
    block size over a fresh public random permutation. An odd-parity block is
    bisected (BINARY) to locate one error; each correction is cascaded back to the
    blocks of earlier passes that contain the corrected bit. Every parity Alice
    discloses is counted as leaked information.
    """
    n = alice.size
    bob = bob.copy()
    initial_errors = int(np.count_nonzero(alice != bob))
    if n == 0:
        return bob, CascadeReport(0, 0, 0, [], [], True)

    q = max(qber_estimate, MIN_QBER_FOR_BLOCKS)
    k1 = int(min(max(math.ceil(0.73 / q), 2), n))
    leaked = 0
    perms: list[np.ndarray] = []
    inv_perms: list[np.ndarray] = []
    sizes: list[int] = []
    alice_par: list[np.ndarray] = []
    corrections: list[int] = []
    odd: set[tuple[int, int]] = set()

    def block_members(p: int, b: int) -> np.ndarray:
        return perms[p][b * sizes[p] : (b + 1) * sizes[p]]

    def flip(pos: int) -> None:
        bob[pos] ^= 1
        for p in range(len(perms)):
            key = (p, int(inv_perms[p][pos] // sizes[p]))
            odd.symmetric_difference_update({key})

    def binary(members: np.ndarray) -> int:
        nonlocal leaked
        while members.size > 1:
            half = members[: members.size // 2]
            leaked += 1  # Alice discloses parity of the first half
            if (int(alice[half].sum()) ^ int(bob[half].sum())) & 1:
                members = half
            else:
                members = members[members.size // 2 :]
        return int(members[0])

    for p in range(passes):
        perm = np.arange(n) if p == 0 else rng.permutation(n)
        size = int(min(k1 * 2**p, n))
        inv = np.empty(n, dtype=np.int64)
        inv[perm] = np.arange(n)
        perms.append(perm)
        inv_perms.append(inv)
        sizes.append(size)
        starts = np.arange(0, n, size)
        a_par = np.add.reduceat(alice[perm].astype(np.int64), starts) & 1
        b_par = np.add.reduceat(bob[perm].astype(np.int64), starts) & 1
        alice_par.append(a_par)
        leaked += starts.size
        odd.update((p, int(b)) for b in np.flatnonzero(a_par != b_par))

        fixed = 0
        while odd:
            p_sel, b_sel = min(odd, key=lambda t: (sizes[t[0]], t))
            flip(binary(block_members(p_sel, b_sel)))
            fixed += 1
        corrections.append(fixed)

    # Verification: compare a 64-bit random-matrix (universal) hash; disclosed bits count as leakage.
    m = rng.integers(0, 2, size=(VERIFY_TAG_BITS, n), dtype=np.uint8)
    tag_a = (m.astype(np.int64) @ alice.astype(np.int64)) & 1
    tag_b = (m.astype(np.int64) @ bob.astype(np.int64)) & 1
    leaked += VERIFY_TAG_BITS
    report = CascadeReport(
        initial_errors=initial_errors,
        residual_errors=int(np.count_nonzero(alice != bob)),
        leaked_bits=leaked,
        block_sizes=sizes,
        corrections_per_pass=corrections,
        verification_passed=bool(np.array_equal(tag_a, tag_b)),
    )
    return bob, report


# ---------------------------------------------------------------------------
# Privacy amplification: Toeplitz universal hashing over GF(2)
# ---------------------------------------------------------------------------


def toeplitz_hash(bits: np.ndarray, out_len: int, seed_bits: np.ndarray) -> np.ndarray:
    """y = T·x mod 2 with T[i, j] = s[i − j + n − 1] (an out_len × n Toeplitz matrix).

    Computed as a linear convolution (FFT for large inputs): (s * x)[i + n − 1] = Σ_j s[i − j + n − 1] x_j.
    """
    n = bits.size
    if out_len <= 0 or n == 0:
        return np.zeros(0, dtype=np.uint8)
    if seed_bits.size != n + out_len - 1:
        raise ValueError("Toeplitz seed must have n + out_len − 1 bits")
    x = bits.astype(np.float64)
    s = seed_bits.astype(np.float64)
    if n * out_len <= 4_000_000:
        conv = np.convolve(s, x)
    else:
        size = 1 << int(math.ceil(math.log2(s.size + x.size - 1)))
        conv = np.fft.irfft(np.fft.rfft(s, size) * np.fft.rfft(x, size), size)[: s.size + x.size - 1]
    window = np.rint(conv[n - 1 : n - 1 + out_len]).astype(np.int64)
    return (window & 1).astype(np.uint8)


def toeplitz_matrix(n: int, out_len: int, seed_bits: np.ndarray) -> np.ndarray:
    """Explicit matrix — used only by tests to validate :func:`toeplitz_hash`."""
    i = np.arange(out_len)[:, None]
    j = np.arange(n)[None, :]
    return seed_bits[i - j + n - 1].astype(np.uint8)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


@dataclass
class KeyPipeline:
    sifted: SiftedKeys
    sifted_qber: float  # true error rate of the whole sifted key (simulation-only knowledge)
    estimation_size: int
    qber_estimate: float
    remaining_length: int
    cascade: CascadeReport | None
    s_used: float
    eve_info_bound: float
    final_length: int
    final_alice: np.ndarray
    final_bob: np.ndarray
    di_rate: float
    bbm92_rate: float
    eve_agreement: float  # fraction of sifted bits Eve guessed correctly
    eve_agreement_intercepted: float
    aborted: bool
    abort_reason: str = ""
    stages: list[tuple[str, int]] = field(default_factory=list)

    @property
    def keys_match(self) -> bool:
        return self.final_length > 0 and bool(np.array_equal(self.final_alice, self.final_bob))

    @property
    def agreement(self) -> float:
        return 1.0 - self.sifted_qber if len(self.sifted) else float("nan")


def bits_to_hex(bits: np.ndarray) -> str:
    if bits.size == 0:
        return ""
    padded = np.concatenate([bits, np.zeros((-bits.size) % 8, dtype=np.uint8)])
    return np.packbits(padded).tobytes().hex()


def run_key_pipeline(
    rounds: RoundData,
    bell: BellAnalysis,
    alice_rad: np.ndarray,
    bob_rad: np.ndarray,
    estimation_fraction: float,
    cascade_passes: int,
    rng: np.random.Generator,
) -> KeyPipeline:
    sifted = sift(rounds, alice_rad, bob_rad, rng)
    n_sift = len(sifted)
    errors = sifted.alice != sifted.bob
    true_qber = float(errors.mean()) if n_sift else float("nan")
    eve_ok = sifted.eve_guess == sifted.bob
    eve_agree = float(eve_ok.mean()) if n_sift else float("nan")
    eve_agree_hit = float(eve_ok[sifted.intercepted].mean()) if sifted.intercepted.any() else float("nan")

    stages = [("Entangled pairs", len(rounds)), ("Detected pairs", int(rounds.detected.sum())), ("Sifted key", n_sift)]
    empty = np.zeros(0, dtype=np.uint8)

    def finish(**kw) -> KeyPipeline:
        base = dict(
            sifted=sifted, sifted_qber=true_qber, estimation_size=0, qber_estimate=float("nan"),
            remaining_length=0, cascade=None, s_used=bell.s_lower, eve_info_bound=theory.eve_holevo_bound(bell.s_lower),
            final_length=0, final_alice=empty, final_bob=empty, di_rate=0.0, bbm92_rate=0.0,
            eve_agreement=eve_agree, eve_agreement_intercepted=eve_agree_hit, aborted=True, stages=stages,
        )
        base.update(kw)
        return KeyPipeline(**base)

    if n_sift < MIN_SIFTED_BITS:
        return finish(abort_reason=f"Only {n_sift} sifted bits — too few for parameter estimation. Increase the number of pairs.")

    # Parameter estimation: publicly compare a random subset, then discard it.
    n_est = max(1, int(round(estimation_fraction * n_sift)))
    est_idx = rng.choice(n_sift, size=n_est, replace=False)
    keep = np.ones(n_sift, dtype=bool)
    keep[est_idx] = False
    q_est = float(errors[est_idx].mean())
    alice_rem, bob_rem = sifted.alice[keep], sifted.bob[keep]
    stages.append(("After QBER estimation", int(keep.sum())))

    di_rate = theory.di_key_rate(bell.s_lower, q_est)
    bbm_rate = theory.bbm92_key_rate(q_est)
    common = dict(estimation_size=n_est, qber_estimate=q_est, remaining_length=int(keep.sum()), di_rate=di_rate, bbm92_rate=bbm_rate)

    if not bell.violation_confirmed:
        reason = (
            f"Bell test failed: S − {bell.confidence_sigma:g}σ = {bell.s_lower:.3f} ≤ 2. "
            "Correlations are compatible with a local-realistic (classical) model — "
            "the channel may be eavesdropped or too noisy. Key discarded."
        )
        return finish(abort_reason=reason, **common)

    bob_corr, report = cascade(alice_rem, bob_rem, q_est, cascade_passes, rng)
    stages.append(("After error correction", int(alice_rem.size)))
    chi = theory.eve_holevo_bound(bell.s_lower)
    final_len = int(math.floor(alice_rem.size * (1.0 - chi) - report.leaked_bits))
    common.update(cascade=report)

    if not report.verification_passed:
        return finish(abort_reason="Error-correction verification hash mismatch — keys differ; protocol aborted.", **common)
    if final_len <= 0:
        reason = (
            f"No secret key can be distilled: n·(1 − χ) = {alice_rem.size * (1 - chi):.0f} bits "
            f"does not exceed the {report.leaked_bits} bits leaked during error correction."
        )
        return finish(abort_reason=reason, **common)

    seed_bits = rng.integers(0, 2, size=alice_rem.size + final_len - 1, dtype=np.uint8)
    final_a = toeplitz_hash(alice_rem, final_len, seed_bits)
    final_b = toeplitz_hash(bob_corr, final_len, seed_bits)
    stages.append(("Final secret key", final_len))
    return finish(aborted=False, final_length=final_len, final_alice=final_a, final_bob=final_b, **common)
