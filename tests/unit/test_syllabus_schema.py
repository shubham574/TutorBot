"""Unit tests for syllabus Pydantic schemas."""
import pytest
from pydantic import ValidationError
from app.services.syllabus.schemas import (
    SyllabusExtractionResult,
    UnitExtraction,
    TopicExtraction,
    SubtopicExtraction,
)


def test_valid_syllabus_schema():
    raw_dict = {
        "subject": "Physics",
        "target_exam": "CBSE Class 12",
        "exam_date": "2026-03-15",
        "units": [
            {
                "title": "Unit 1: Electrostatics",
                "marks_weightage": 16.0,
                "topics": [
                    {
                        "title": "Electric Charges and Fields",
                        "estimated_minutes": 50,
                        "subtopics": [
                            {"title": "Coulomb's Law"},
                            {"title": "Electric Dipole"},
                        ],
                    }
                ],
            }
        ],
    }

    tree = SyllabusExtractionResult.model_validate(raw_dict)
    assert tree.subject == "Physics"
    assert len(tree.units) == 1
    assert tree.units[0].marks_weightage == 16.0
    assert len(tree.units[0].topics[0].subtopics) == 2
    assert tree.units[0].topics[0].subtopics[0].estimated_minutes == 30  # Default value


def test_missing_subject_raises_validation_error():
    with pytest.raises(ValidationError):
        SyllabusExtractionResult.model_validate({"units": []})


def test_missing_units_raises_validation_error():
    with pytest.raises(ValidationError):
        SyllabusExtractionResult.model_validate({"subject": "Mathematics"})
