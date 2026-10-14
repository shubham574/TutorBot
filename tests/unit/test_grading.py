"""Unit tests for subjective grading service."""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.grading.service import grading_service, GradingReport, StepScore


@pytest.mark.asyncio
async def test_grade_text_answer_with_sympy():
    mock_report = GradingReport(
        max_marks=5.0,
        total_awarded=4.5,
        percentage=90.0,
        step_breakdown=[
            StepScore(step_name="Core Concept", max_marks=2.0, marks_awarded=2.0, feedback="Identified Work-Energy theorem correctly."),
            StepScore(step_name="Intermediate Steps", max_marks=2.0, marks_awarded=1.5, feedback="Correct algebraic steps."),
            StepScore(step_name="Final Answer", max_marks=1.0, marks_awarded=1.0, feedback="Accurate magnitude and Joules unit."),
        ],
        strengths=["Clear conceptual understanding", "Correct units"],
        areas_for_improvement=["State initial assumptions explicitly"],
        sympy_verified=True,
        overall_summary="Excellent solution with well-explained steps.",
    )

    with patch("app.services.grading.service.llm_client.extract_structured", new=AsyncMock(return_value=mock_report)):
        report = await grading_service.grade_text_answer(
            question_text="Calculate work done when a 2 kg block stops from 10 m/s.",
            student_answer="Using W = 1/2 * m * v^2 = 0.5 * 2 * 10^2 = 100 Joules",
            expected_solution="100",
            max_marks=5.0,
        )

    assert report.total_awarded == 4.5
    assert report.percentage == 90.0
    assert report.sympy_verified is True
    assert len(report.step_breakdown) == 3


def test_format_grading_for_whatsapp():
    mock_report = GradingReport(
        max_marks=5.0,
        total_awarded=4.0,
        percentage=80.0,
        step_breakdown=[
            StepScore(step_name="Formula", max_marks=2.0, marks_awarded=2.0, feedback="Good"),
            StepScore(step_name="Steps", max_marks=2.0, marks_awarded=1.0, feedback="Minor arithmetic error"),
            StepScore(step_name="Units", max_marks=1.0, marks_awarded=1.0, feedback="Proper unit"),
        ],
        strengths=["Right formula"],
        areas_for_improvement=["Double check multiplication"],
        sympy_verified=True,
        overall_summary="Very solid attempt.",
    )

    msg_body, buttons = grading_service.format_grading_for_whatsapp(mock_report)
    assert "Assessment & Grading Report" in msg_body
    assert "4.0 / 5.0" in msg_body
    assert "SymPy Verified Symbolic Equivalence" in msg_body
    assert len(buttons) == 2
