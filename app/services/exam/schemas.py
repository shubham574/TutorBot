"""Pydantic schemas for examination blueprints and sections."""
from typing import List, Optional
from pydantic import BaseModel, Field


class ExamQuestion(BaseModel):
    question_num: int = Field(..., description="Sequential question number (e.g. 1, 2, 3)")
    question_text: str = Field(..., description="Full text of the question or numerical problem")
    question_type: str = Field("subjective", description="mcq, short_answer, long_answer, numerical")
    marks: float = Field(..., description="Marks allocated to this question")
    topic_name: Optional[str] = Field(None, description="Topic from syllabus")


class ExamSection(BaseModel):
    section_name: str = Field(..., description="Section letter & title (e.g. 'Section A: Short Answer')")
    instructions: str = Field(..., description="Instructions for this section")
    marks_per_question: float = Field(..., description="Marks per question in this section")
    questions: List[ExamQuestion] = Field(..., description="List of questions in this section")


class ExamBlueprint(BaseModel):
    title: str = Field(..., description="Exam title (e.g. 'Class 12 Physics Pre-Board Examination')")
    subject: str = Field(..., description="Subject name")
    target_exam: Optional[str] = Field("Annual Examination", description="Target examination or board")
    total_marks: float = Field(..., description="Sum of all question marks")
    duration_minutes: int = Field(180, description="Examination duration in minutes (e.g. 180 = 3 hours)")
    instructions: List[str] = Field(
        default_factory=lambda: [
            "All questions are compulsory.",
            "Use of calculators is not permitted.",
            "Write your answers clearly and show all intermediate working.",
        ],
        description="General instructions printed on the paper",
    )
    sections: List[ExamSection] = Field(..., description="Exam sections following the blueprint")
