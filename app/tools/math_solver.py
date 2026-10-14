"""SymPy mathematical verification tool for grading equations, algebra, and calculus."""
import re
from typing import Tuple
import sympy as sp
from app.config.logging_config import logger


def clean_math_string(expr_str: str) -> str:
    """Pre-processes raw student math strings into SymPy-compatible format."""
    if not expr_str:
        return ""
    cleaned = expr_str.strip()
    # Replace LaTeX \frac{a}{b} -> (a)/(b)
    cleaned = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", cleaned)
    # Replace ^ with **
    cleaned = cleaned.replace("^", "**")
    # Replace unicode symbols
    cleaned = cleaned.replace("×", "*").replace("÷", "/")
    # Remove equation lhs if student wrote e.g. "x = 5" -> "5"
    if "=" in cleaned:
        parts = cleaned.split("=")
        cleaned = parts[-1].strip()
    # Remove common physical unit names (e.g. Joules, meters, seconds, kg, etc.)
    cleaned = re.sub(
        r"\b(joules?|meters?|seconds?|kg|newtons?|watts?|volts?|amperes?|hz|kelvin|j|n|m|s|w|v|a|k)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def verify_mathematical_equivalence(
    expected_expr_str: str,
    student_expr_str: str,
    tolerance: float = 1e-4,
) -> Tuple[bool, str]:
    """
    Symbolically and numerically verifies if a student's answer is equivalent to the expected answer.

    Args:
        expected_expr_str: The correct reference expression (e.g., '2*x + 1' or '4.5')
        student_expr_str: The student's submitted expression (e.g., '1 + 2*x' or '9/2')
        tolerance: Numerical float tolerance

    Returns:
        Tuple of (is_equivalent: bool, message: str)
    """
    cleaned_exp = clean_math_string(expected_expr_str)
    cleaned_stu = clean_math_string(student_expr_str)

    if not cleaned_exp or not cleaned_stu:
        return False, "Empty or invalid mathematical expression."

    try:
        exp_sym = sp.sympify(cleaned_exp)
        stu_sym = sp.sympify(cleaned_stu)
    except Exception as e:
        logger.info("SymPy parse failed", error=str(e), expected=cleaned_exp, student=cleaned_stu)
        return False, f"Could not parse mathematical syntax: {str(e)}"

    # 1. Direct Symbolic Equivalence
    try:
        diff = sp.simplify(exp_sym - stu_sym)
        if diff == 0:
            return True, "Symbolically identical expression."
    except Exception:
        pass

    # 2. Numerical Equivalence
    try:
        exp_val = float(exp_sym.evalf())
        stu_val = float(stu_sym.evalf())
        if abs(exp_val - stu_val) <= tolerance:
            return True, f"Numerically equivalent within tolerance ({tolerance})."
    except Exception:
        pass

    # 3. Trigonometric / Factorization Equivalence
    try:
        if sp.trigsimp(exp_sym - stu_sym) == 0:
            return True, "Trigonometrically equivalent expression."
    except Exception:
        pass

    return False, f"Expressions are not mathematically equivalent. Expected: {expected_expr_str}, Got: {student_expr_str}"
