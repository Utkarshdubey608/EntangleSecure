"""E91 protocol engine."""

from .chsh import BellAnalysis, CHSHLabelling, analyze_bell, choose_labelling
from .config import EKERT_ALICE_DEG, EKERT_BOB_DEG, ConfigError, EveConfig, ExperimentConfig
from .experiment import INCONCLUSIVE, INSECURE, SECURE, ExperimentResult, run_experiment, run_measurement_only

__all__ = [
    "BellAnalysis",
    "CHSHLabelling",
    "ConfigError",
    "EKERT_ALICE_DEG",
    "EKERT_BOB_DEG",
    "EveConfig",
    "ExperimentConfig",
    "ExperimentResult",
    "INCONCLUSIVE",
    "INSECURE",
    "SECURE",
    "analyze_bell",
    "choose_labelling",
    "run_experiment",
    "run_measurement_only",
]
