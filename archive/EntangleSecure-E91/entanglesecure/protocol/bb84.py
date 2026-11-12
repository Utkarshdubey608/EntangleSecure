"""BB84 prepare-and-measure protocol, simulated for comparison with E91.

Alice sends single photons, each with a random bit encoded in a random basis
(rectilinear Z or diagonal X). Bob measures each photon in his own random basis.
Rounds where the bases agree form the sifted key. An optional intercept-resend
eavesdropper measures every photon in a random basis and resends it, which
randomises about half of the sifted bits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from .config import ConfigError
from .theory import binary_entropy

BB84_QBER_LIMIT = 0.11
MIN_PHOTONS = 100
MAX_PHOTONS = 1_000_000


@dataclass(frozen=True)
class BB84Config:
    n_photons: int = 4000
    eve_enabled: bool = False
    channel_error: float = 0.0
    seed: int = 2026

    def validate(self) -> BB84Config:
        if isinstance(self.n_photons, bool) or int(self.n_photons) != self.n_photons:
            raise ConfigError("Number of photons must be a whole number.")
        n = int(self.n_photons)
        if not MIN_PHOTONS <= n <= MAX_PHOTONS:
            raise ConfigError(f"Number of photons must be between {MIN_PHOTONS:,} and {MAX_PHOTONS:,}.")
        if not isinstance(self.eve_enabled, bool):
            raise ConfigError("Eve must be enabled or disabled.")
        p = float(self.channel_error)
        if not math.isfinite(p) or not 0.0 <= p <= 0.5:
            raise ConfigError("Channel error must be between 0 and 0.5.")
        if isinstance(self.seed, bool) or int(self.seed) != self.seed or not 0 <= int(self.seed) < 2**32:
            raise ConfigError("Random seed must be an integer between 0 and 4,294,967,295.")
        return replace(self, n_photons=n, channel_error=p, seed=int(self.seed))


@dataclass(frozen=True)
class BB84Result:
    config: BB84Config
    alice_key: np.ndarray
    bob_key: np.ndarray
    sifted_fraction: float
    qber: float
    key_rate_per_photon: float

    @property
    def sifted_length(self) -> int:
        return int(self.alice_key.size)

    @property
    def secret_key_length(self) -> int:
        return int(self.key_rate_per_photon * self.config.n_photons)

    @property
    def secure(self) -> bool:
        return self.qber < BB84_QBER_LIMIT and self.secret_key_length > 0


def run_bb84(config: BB84Config) -> BB84Result:
    cfg = config.validate()
    n = cfg.n_photons
    rng = np.random.default_rng(cfg.seed)

    alice_bits = rng.integers(0, 2, n)
    alice_bases = rng.integers(0, 2, n)
    bob_bases = rng.integers(0, 2, n)
    eve_bases = rng.integers(0, 2, n)
    eve_guesses = rng.integers(0, 2, n)

    photon_bits, photon_bases = alice_bits, alice_bases
    if cfg.eve_enabled:
        eve_bits = np.where(eve_bases == alice_bases, alice_bits, eve_guesses)
        photon_bits, photon_bases = eve_bits, eve_bases

    noise = rng.random(n) < cfg.channel_error
    bob_guesses = rng.integers(0, 2, n)
    bob_bits = np.where(bob_bases == photon_bases, photon_bits ^ noise, bob_guesses)

    sifted = bob_bases == alice_bases
    alice_key = alice_bits[sifted]
    bob_key = bob_bits[sifted]
    sifted_fraction = float(sifted.mean())
    qber = float(np.mean(alice_key != bob_key)) if alice_key.size else float("nan")

    if alice_key.size:
        secure_fraction = max(0.0, 1.0 - 2.0 * binary_entropy(qber))
    else:
        secure_fraction = 0.0
    key_rate = sifted_fraction * secure_fraction

    return BB84Result(cfg, alice_key, bob_key, sifted_fraction, qber, key_rate)
