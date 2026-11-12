"""Input validation, serialisation and report generation."""

import io
import json

import pandas as pd
import pytest

from entanglesecure.protocol import ConfigError, EveConfig, ExperimentConfig, run_experiment
from entanglesecure.reporting import build_pdf_report, correlators_frame, rounds_csv, summary_csv


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_pairs": 10},
        {"n_pairs": 10_000_000},
        {"n_pairs": 1000.5},
        {"n_pairs": "many"},
        {"n_pairs": True},
        {"alice_angles_deg": (0, 45)},
        {"bob_angles_deg": (0, 45, "x")},
        {"bob_angles_deg": (0, 45, float("nan"))},
        {"alice_angles_deg": (0, 45, 900)},
        {"depolarizing_noise": -0.1},
        {"depolarizing_noise": 1.2},
        {"detection_efficiency": 0.0},
        {"seed": -1},
        {"seed": 2**40},
        {"seed": 1.5},
        {"estimation_fraction": 0.0},
        {"estimation_fraction": 1.0},
        {"bell_confidence_sigma": 9},
        {"cascade_passes": 0},
        {"eve": EveConfig(enabled=True, intercept_fraction=1.5)},
        {"eve": EveConfig(enabled=True, basis_angles_deg=())},
    ],
)
def test_invalid_configs_rejected(kwargs):
    with pytest.raises(ConfigError) as exc:
        ExperimentConfig(**kwargs).validate()
    assert str(exc.value)  # human-readable message


def test_run_experiment_validates():
    with pytest.raises(ConfigError):
        run_experiment(ExperimentConfig(n_pairs=5))


def test_json_round_trip():
    cfg = ExperimentConfig(n_pairs=1234, seed=77, depolarizing_noise=0.05, eve=EveConfig(enabled=True, intercept_fraction=0.3, basis_angles_deg=(10.0, 20.0))).validate()
    back = ExperimentConfig.from_json(cfg.to_json())
    assert back == cfg


@pytest.mark.parametrize(
    "text",
    ["not json", "[1, 2]", json.dumps({"n_pairs": 1000, "colour": "red"}), json.dumps({"eve": {"mood": 1}}), json.dumps({"n_pairs": 3})],
)
def test_bad_json_rejected(text):
    with pytest.raises(ConfigError):
        ExperimentConfig.from_json(text)


@pytest.fixture(scope="module")
def result():
    return run_experiment(ExperimentConfig(n_pairs=6_000, seed=10))


def test_rounds_csv(result):
    df = pd.read_csv(io.StringIO(rounds_csv(result)))
    assert len(df) == 6_000
    assert {"alice_setting", "bob_setting", "alice_outcome", "bob_outcome", "role", "eve_intercepted"} <= set(df.columns)
    assert set(df.role) <= {"key", "chsh", "discard", "lost"}
    assert set(df.alice_outcome) <= {1, -1}


def test_summary_csv_sections(result):
    text = summary_csv(result)
    for section in ("metrics", "correlators", "key_pipeline", "configuration"):
        assert f"# section: {section}" in text
    assert len(correlators_frame(result)) == 9


def test_pdf_report(result):
    pdf = build_pdf_report(result)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 3000
    attacked = run_experiment(result.config.with_eve(True))
    pdf2 = build_pdf_report(attacked, comparison=result)
    assert pdf2[:5] == b"%PDF-"
