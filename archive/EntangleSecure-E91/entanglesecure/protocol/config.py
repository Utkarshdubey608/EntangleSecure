"""Validated, immutable, JSON-serialisable experiment configuration."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from typing import Any

# Ekert (1991) measurement directions in degrees on the Bloch sphere (x–z plane).
EKERT_ALICE_DEG: tuple[float, float, float] = (0.0, 45.0, 90.0)
EKERT_BOB_DEG: tuple[float, float, float] = (45.0, 90.0, 135.0)

MIN_PAIRS = 100
MAX_PAIRS = 1_000_000
MAX_EVE_ANGLES = 8


class ConfigError(ValueError):
    """Raised when a configuration value is invalid. Messages are user-facing."""


def _as_angle_tuple(values: Any, name: str, length: int | None = None) -> tuple[float, ...]:
    try:
        out = tuple(float(v) for v in values)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a list of numbers (degrees).") from exc
    if length is not None and len(out) != length:
        raise ConfigError(f"{name} must contain exactly {length} angles, got {len(out)}.")
    for v in out:
        if not math.isfinite(v):
            raise ConfigError(f"{name} contains a non-finite angle.")
        if not -360.0 <= v <= 360.0:
            raise ConfigError(f"{name}: angle {v}° is outside the allowed range [−360°, 360°].")
    return out


@dataclass(frozen=True)
class EveConfig:
    """Intercept-resend eavesdropper on Bob's channel."""

    enabled: bool = False
    intercept_fraction: float = 1.0
    basis_angles_deg: tuple[float, ...] = EKERT_BOB_DEG

    def validate(self) -> EveConfig:
        if not isinstance(self.enabled, bool):
            raise ConfigError("Eve 'enabled' must be true or false.")
        try:
            q = float(self.intercept_fraction)
        except (TypeError, ValueError) as exc:
            raise ConfigError("Eve's interception fraction must be a number.") from exc
        if not 0.0 <= q <= 1.0 or math.isnan(q):
            raise ConfigError("Eve's interception fraction must be between 0 and 1.")
        angles = _as_angle_tuple(self.basis_angles_deg, "Eve's measurement directions")
        if not 1 <= len(angles) <= MAX_EVE_ANGLES:
            raise ConfigError(f"Eve needs between 1 and {MAX_EVE_ANGLES} measurement directions.")
        return replace(self, intercept_fraction=q, basis_angles_deg=angles)


@dataclass(frozen=True)
class ExperimentConfig:
    """Everything needed to reproduce an experiment exactly."""

    n_pairs: int = 5000
    alice_angles_deg: tuple[float, float, float] = EKERT_ALICE_DEG
    bob_angles_deg: tuple[float, float, float] = EKERT_BOB_DEG
    depolarizing_noise: float = 0.0
    detection_efficiency: float = 1.0
    seed: int = 2026
    estimation_fraction: float = 0.2
    bell_confidence_sigma: float = 2.0
    cascade_passes: int = 4
    eve: EveConfig = field(default_factory=EveConfig)

    def validate(self) -> ExperimentConfig:
        """Return a normalised copy or raise ConfigError with a readable message."""
        if isinstance(self.n_pairs, bool):
            raise ConfigError("Number of entangled pairs must be an integer.")
        try:
            n = int(self.n_pairs)
        except (TypeError, ValueError) as exc:
            raise ConfigError("Number of entangled pairs must be an integer.") from exc
        if n != self.n_pairs:
            raise ConfigError("Number of entangled pairs must be a whole number.")
        if not MIN_PAIRS <= n <= MAX_PAIRS:
            raise ConfigError(f"Number of entangled pairs must be between {MIN_PAIRS:,} and {MAX_PAIRS:,}.")

        alice = _as_angle_tuple(self.alice_angles_deg, "Alice's angles", 3)
        bob = _as_angle_tuple(self.bob_angles_deg, "Bob's angles", 3)

        p = _number(self.depolarizing_noise, "Depolarizing noise")
        if not 0.0 <= p <= 1.0:
            raise ConfigError("Depolarizing noise probability must be between 0 and 1.")

        eta = _number(self.detection_efficiency, "Detection efficiency")
        if not 0.05 <= eta <= 1.0:
            raise ConfigError("Detection efficiency must be between 0.05 and 1.")

        seed_value = _number(self.seed, "Random seed")
        if seed_value != int(seed_value):
            raise ConfigError("Random seed must be an integer.")
        seed = int(seed_value)
        if not 0 <= seed < 2**32:
            raise ConfigError("Random seed must be between 0 and 4,294,967,295.")

        f = _number(self.estimation_fraction, "Estimation fraction")
        if not 0.0 < f < 1.0:
            raise ConfigError("The fraction of sifted bits revealed for QBER estimation must be strictly between 0 and 1.")

        z = _number(self.bell_confidence_sigma, "Bell confidence")
        if not 0.0 <= z <= 5.0:
            raise ConfigError("Bell-test confidence must be between 0σ and 5σ.")

        passes = _number(self.cascade_passes, "Cascade passes")
        if passes != int(passes) or not 1 <= passes <= 8:
            raise ConfigError("Cascade passes must be between 1 and 8.")

        eve = self.eve if isinstance(self.eve, EveConfig) else EveConfig(**dict(self.eve))
        return replace(
            self,
            n_pairs=n,
            alice_angles_deg=alice,
            bob_angles_deg=bob,
            depolarizing_noise=p,
            detection_efficiency=eta,
            seed=seed,
            estimation_fraction=f,
            bell_confidence_sigma=z,
            cascade_passes=int(passes),
            eve=eve.validate(),
        )

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["alice_angles_deg"] = list(self.alice_angles_deg)
        d["bob_angles_deg"] = list(self.bob_angles_deg)
        d["eve"]["basis_angles_deg"] = list(self.eve.basis_angles_deg)
        return d

    def to_json(self) -> str:
        return json.dumps({"entanglesecure_config": 1, **self.to_dict()}, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        if not isinstance(data, dict):
            raise ConfigError("Configuration must be a JSON object.")
        data = {k: v for k, v in data.items() if k != "entanglesecure_config"}
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"Unknown configuration field(s): {', '.join(sorted(unknown))}.")
        eve_data = data.pop("eve", {}) or {}
        if not isinstance(eve_data, dict):
            raise ConfigError("'eve' must be a JSON object.")
        eve_unknown = set(eve_data) - set(EveConfig.__dataclass_fields__)
        if eve_unknown:
            raise ConfigError(f"Unknown Eve field(s): {', '.join(sorted(eve_unknown))}.")
        try:
            cfg = cls(**data, eve=EveConfig(**eve_data))
        except TypeError as exc:
            raise ConfigError(f"Malformed configuration: {exc}") from exc
        return cfg.validate()

    @classmethod
    def from_json(cls, text: str) -> ExperimentConfig:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Configuration file is not valid JSON ({exc.msg}, line {exc.lineno}).") from exc
        return cls.from_dict(data)

    def with_eve(self, enabled: bool) -> ExperimentConfig:
        return replace(self, eve=replace(self.eve, enabled=enabled))


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be a number.")
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a number.") from exc
    if math.isnan(v):
        raise ConfigError(f"{name} must be a number.")
    return v
