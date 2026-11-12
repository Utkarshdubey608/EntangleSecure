import pytest

from entanglesecure.quantum.threat import factor_steps, factors_of, first_working_base, order_mod


def test_order_of_seven_mod_fifteen_is_four():
    assert order_mod(7, 15) == 4


@pytest.mark.parametrize("n", [15, 21])
def test_supported_numbers_factor_correctly(n):
    a = first_working_base(n)
    factors = factors_of(n, a)
    assert factors is not None
    assert set(factors) == ({3, 5} if n == 15 else {3, 7})
    assert factors[0] * factors[1] == n


@pytest.mark.parametrize("n", [2, 4, 9_999_999, 1, 0])
def test_invalid_n_raises(n):
    with pytest.raises(ValueError):
        factor_steps(n, 2)


def test_prime_n_is_rejected():
    with pytest.raises(ValueError):
        factor_steps(13, 2)


def test_base_must_be_coprime():
    with pytest.raises(ValueError):
        factor_steps(15, 5)
