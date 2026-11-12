import numpy as np
import pytest

from entanglesecure.protocol.bb84 import BB84_QBER_LIMIT, BB84Config, run_bb84
from entanglesecure.protocol.config import ConfigError


def test_no_eve_no_noise_has_zero_qber():
    res = run_bb84(BB84Config(n_photons=20_000, seed=7))
    assert res.sifted_length > 0
    assert res.qber == 0.0
    assert res.secure


def test_sifting_keeps_about_half_the_photons():
    res = run_bb84(BB84Config(n_photons=20_000, seed=7))
    assert res.sifted_fraction == pytest.approx(0.5, abs=0.02)


def test_eve_raises_qber_toward_quarter():
    res = run_bb84(BB84Config(n_photons=40_000, eve_enabled=True, seed=11))
    assert res.qber == pytest.approx(0.25, abs=0.02)
    assert res.qber > BB84_QBER_LIMIT
    assert not res.secure


def test_same_seed_is_reproducible():
    a = run_bb84(BB84Config(n_photons=5_000, eve_enabled=True, channel_error=0.02, seed=3))
    b = run_bb84(BB84Config(n_photons=5_000, eve_enabled=True, channel_error=0.02, seed=3))
    np.testing.assert_array_equal(a.alice_key, b.alice_key)
    np.testing.assert_array_equal(a.bob_key, b.bob_key)
    assert a.qber == b.qber


def test_different_seed_changes_the_key():
    a = run_bb84(BB84Config(n_photons=5_000, seed=3))
    b = run_bb84(BB84Config(n_photons=5_000, seed=4))
    assert not np.array_equal(a.alice_key, b.alice_key)


def test_channel_error_produces_errors_without_eve():
    res = run_bb84(BB84Config(n_photons=40_000, channel_error=0.05, seed=5))
    assert res.qber == pytest.approx(0.05, abs=0.01)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_photons": 10},
        {"n_photons": 2_000_000},
        {"n_photons": 1000.5},
        {"channel_error": 0.9},
        {"channel_error": -0.1},
        {"seed": -1},
        {"eve_enabled": "yes"},
    ],
)
def test_invalid_config_is_rejected(kwargs):
    with pytest.raises(ConfigError):
        run_bb84(BB84Config(**kwargs))
