"""CSV/JSON exports of an experiment."""

from __future__ import annotations

import math

import pandas as pd

from ..protocol.experiment import ExperimentResult


def rounds_frame(result: ExperimentResult) -> pd.DataFrame:
    return result.rounds.to_frame(result.config)


def correlators_frame(result: ExperimentResult) -> pd.DataFrame:
    cfg = result.config
    chsh = {idx: (sym, sign) for sym, (idx, sign) in zip(result.bell.labelling.symbols(), result.bell.labelling.terms())}
    rows = []
    for (i, j), c in sorted(result.bell.correlators.items()):
        sym, sign = chsh.get((i, j), ("", 0))
        rows.append(
            {
                "alice_setting": f"A{i}",
                "bob_setting": f"B{j}",
                "alice_angle_deg": cfg.alice_angles_deg[i],
                "bob_angle_deg": cfg.bob_angles_deg[j],
                "n": c.n,
                "N_pp": int(c.counts[0, 0]),
                "N_pm": int(c.counts[0, 1]),
                "N_mp": int(c.counts[1, 0]),
                "N_mm": int(c.counts[1, 1]),
                "E_measured": c.expectation,
                "E_stderr": c.stderr,
                "E_theory": c.theory,
                "chsh_term": sym,
                "chsh_sign": sign,
            }
        )
    return pd.DataFrame(rows)


def metrics_frame(result: ExperimentResult) -> pd.DataFrame:
    m = result.metrics()
    rows = [{"metric": k, "value": v} for k, v in m.items() if not (isinstance(v, float) and math.isnan(v))]
    return pd.DataFrame(rows)


def summary_csv(result: ExperimentResult) -> str:
    """Single CSV containing metrics, correlators and the configuration (sectioned)."""
    parts = [
        "# EntangleSecure experiment summary",
        "# section: metrics",
        metrics_frame(result).to_csv(index=False),
        "# section: correlators",
        correlators_frame(result).to_csv(index=False),
        "# section: key_pipeline",
        pd.DataFrame(result.keys.stages, columns=["stage", "bits_or_pairs"]).to_csv(index=False),
        "# section: configuration",
        pd.DataFrame([{"parameter": k, "value": v} for k, v in _flatten(result.config.to_dict()).items()]).to_csv(index=False),
    ]
    return "\n".join(parts)


def rounds_csv(result: ExperimentResult) -> str:
    return rounds_frame(result).to_csv(index=False)


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out
