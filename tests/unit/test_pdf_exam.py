"""Unit tests for Exam blueprint and PDF paper generator."""
import pytest
from app.services.exam.schemas import ExamBlueprint, ExamSection, ExamQuestion
from app.services.exam.pdf_generator import exam_pdf_generator


def test_exam_pdf_generation_valid():
    blueprint = ExamBlueprint(
        title="Class 12 Physics Pre-Board Examination",
        subject="Physics",
        target_exam="CBSE Board Assessment",
        total_marks=25.0,
        duration_minutes=90,
        instructions=[
            "All questions are compulsory.",
            "Write neatly and show all steps.",
        ],
        sections=[
            ExamSection(
                section_name="Section A: Multiple Choice",
                instructions="1 mark each",
                marks_per_question=1.0,
                questions=[
                    ExamQuestion(
                        question_num=1,
                        question_text="What is the unit of electric flux?",
                        marks=1.0,
                    )
                ],
            ),
            ExamSection(
                section_name="Section B: Long Answer",
                instructions="5 marks each",
                marks_per_question=5.0,
                questions=[
                    ExamQuestion(
                        question_num=2,
                        question_text="Derive Gauss's theorem for an infinitely long charged wire.",
                        marks=5.0,
                    )
                ],
            ),
        ],
    )

    pdf_bytes = exam_pdf_generator.generate_exam_pdf(blueprint)
    assert len(pdf_bytes) > 1000
    # Standard PDF header check
    assert pdf_bytes.startswith(b"%PDF")
