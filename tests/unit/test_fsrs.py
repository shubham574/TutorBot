"""Unit tests for FSRS spaced repetition engine."""
import datetime
import pytest
from app.services.fsrs.engine import fsrs_engine, INITIAL_STABILITY


def test_initial_correct_answer():
    state = fsrs_engine.calculate_next_state(
        current_stability=1.0,
        current_difficulty=5.0,
        reps=0,
        lapses=0,
        is_correct=True,
    )
    assert state.stability == INITIAL_STABILITY[3]
    assert state.reps == 1
    assert state.lapses == 0
    assert state.state == "review"
    assert state.next_review > datetime.datetime.now(datetime.timezone.utc)
    assert 0.0 < state.mastery_score <= 1.0


def test_initial_incorrect_answer():
    state = fsrs_engine.calculate_next_state(
        current_stability=1.0,
        current_difficulty=5.0,
        reps=0,
        lapses=0,
        is_correct=False,
    )
    assert state.stability == INITIAL_STABILITY[1]
    assert state.reps == 0
    assert state.lapses == 1
    assert state.state == "learning"


def test_consecutive_correct_increases_stability():
    # First correct
    s1 = fsrs_engine.calculate_next_state(
        current_stability=1.0,
        current_difficulty=5.0,
        reps=0,
        lapses=0,
        is_correct=True,
    )
    # Second correct
    s2 = fsrs_engine.calculate_next_state(
        current_stability=s1.stability,
        current_difficulty=s1.difficulty,
        reps=s1.reps,
        lapses=s1.lapses,
        is_correct=True,
    )
    assert s2.stability > s1.stability
    assert s2.reps == 2
    assert s2.mastery_score >= s1.mastery_score


def test_lapse_decreases_stability():
    # After good stability, student fails
    s_failed = fsrs_engine.calculate_next_state(
        current_stability=10.0,
        current_difficulty=4.0,
        reps=4,
        lapses=0,
        is_correct=False,
    )
    assert s_failed.stability < 10.0
    assert s_failed.lapses == 1
    assert s_failed.state == "learning"
