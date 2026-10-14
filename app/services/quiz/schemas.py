"""Pydantic schemas for MCQ generation and autonomous verifier."""
from typing import Dict, Literal
from pydantic import BaseModel, Field


class GeneratedMCQ(BaseModel):
    """MCQ question structure generated from grounded curriculum materials."""
    question: str = Field(..., description="The multiple choice question stem")
    options: Dict[str, str] = Field(
        ...,
        description="Options dict with keys 'A', 'B', 'C' (max 3 options for WhatsApp 1-tap reply buttons)",
    )
    correct_answer: Literal["A", "B", "C"] = Field(
        ...,
        description="The letter corresponding to the correct option",
    )
    explanation: str = Field(
        ...,
        description="Detailed educational explanation of why the correct option is right and others are wrong",
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        "medium",
        description="Difficulty level of the question",
    )


class VerifierEvaluation(BaseModel):
    """Output from the independent verifier re-solving the question blind."""
    solved_answer: Literal["A", "B", "C"] = Field(
        ...,
        description="The answer selected by the verifier independently",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level of the verifier",
    )
    reasoning: str = Field(
        ...,
        description="Step-by-step reasoning used by the verifier to arrive at the solution",
    )
