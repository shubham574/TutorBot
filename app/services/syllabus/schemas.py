"""Pydantic schemas for syllabus extraction and validation."""
from typing import List, Optional
from pydantic import BaseModel, Field


class SubtopicExtraction(BaseModel):
    """Leaf node representing an atomic subtopic concept."""
    title: str = Field(..., description="Title of the subtopic concept")
    estimated_minutes: int = Field(30, description="Estimated study time in minutes")


class TopicExtraction(BaseModel):
    """Topic grouping several subtopics."""
    title: str = Field(..., description="Title of the topic")
    subtopics: List[SubtopicExtraction] = Field(
        default_factory=list,
        description="List of subtopics under this topic",
    )
    estimated_minutes: int = Field(45, description="Estimated study time in minutes")


class UnitExtraction(BaseModel):
    """Curriculum unit or chapter containing topics."""
    title: str = Field(..., description="Unit or Chapter title (e.g., Unit 1: Kinematics)")
    marks_weightage: Optional[float] = Field(
        None,
        description="Marks allocated to this unit in the exam if specified",
    )
    topics: List[TopicExtraction] = Field(
        default_factory=list,
        description="List of topics under this unit",
    )


class SyllabusExtractionResult(BaseModel):
    """Root structured tree extracted from syllabus text or document."""
    subject: str = Field(..., description="Name of the subject (e.g. Physics, Chemistry, Mathematics)")
    target_exam: Optional[str] = Field(
        None,
        description="Target exam if mentioned (e.g. CBSE Class 12, JEE Main, NEET)",
    )
    exam_date: Optional[str] = Field(
        None,
        description="Target exam date in YYYY-MM-DD format if mentioned",
    )
    units: List[UnitExtraction] = Field(
        ...,
        description="List of units / chapters in sequential syllabus order",
    )
