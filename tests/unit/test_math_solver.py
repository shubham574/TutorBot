"""Unit tests for SymPy mathematical verification tool."""
import pytest
from app.tools.math_solver import verify_mathematical_equivalence, clean_math_string


def test_clean_math_string():
    assert clean_math_string("x^2 + 4") == "x**2 + 4"
    assert clean_math_string("3 × 4 ÷ 2") == "3 * 4 / 2"
    assert clean_math_string("Ans: x = 15") == "15"


def test_algebraic_equivalence():
    # Commutative & expanded expressions
    match, msg = verify_mathematical_equivalence("2*x + 3", "3 + 2*x")
    assert match is True

    match_sq, _ = verify_mathematical_equivalence("(x + 1)**2", "x**2 + 2*x + 1")
    assert match_sq is True


def test_numerical_fraction_equivalence():
    match, msg = verify_mathematical_equivalence("1/2", "0.5")
    assert match is True

    match_pi, _ = verify_mathematical_equivalence("22/7", "3.142857", tolerance=1e-3)
    assert match_pi is True


def test_non_equivalent_expressions():
    match, msg = verify_mathematical_equivalence("x**2", "x**3")
    assert match is False
    assert "not mathematically equivalent" in msg


def test_invalid_syntax_handled_gracefully():
    match, msg = verify_mathematical_equivalence("2*x + 1", "invalid ++ syntax ///")
    assert match is False
    assert "Could not parse" in msg
