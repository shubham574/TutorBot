"""FSRS (Free Spaced Repetition Scheduler) memory retention engine."""
import datetime
import math
from typing import NamedTuple

# Standard FSRS default parameter weights
INITIAL_STABILITY = {
    1: 0.4,   # Again / Failed
    2: 1.0,   # Hard
    3: 2.5,   # Good / Correct
    4: 4.0,   # Easy
}

TARGET_RETENTION = 0.90  # 90% target retrieval probability


class FSRSState(NamedTuple):
    stability: float
    difficulty: float
    reps: int
    lapses: int
    state: str
    next_review: datetime.datetime
    mastery_score: float


class FSRSEngine:
    """Computes memory decay, interval scheduling, and mastery progress."""

    @staticmethod
    def calculate_next_state(
        current_stability: float,
        current_difficulty: float,
        reps: int,
        lapses: int,
        is_correct: bool,
        review_time: datetime.datetime = None,
    ) -> FSRSState:
        """
        Updates memory stability and difficulty based on response correctness.
        Rating: is_correct=True -> Grade 3 (Good); is_correct=False -> Grade 1 (Again).
        """
        now = review_time or datetime.datetime.now(datetime.timezone.utc)
        grade = 3 if is_correct else 1

        # First repetition (new state)
        if reps == 0 and lapses == 0:
            stability = INITIAL_STABILITY[grade]
            difficulty = min(max(5.0 - (grade - 3) * 0.8, 1.0), 10.0)
            new_reps = 1 if is_correct else 0
            new_lapses = 0 if is_correct else 1
            new_state = "review" if is_correct else "learning"
        else:
            # Subsequent reviews
            if is_correct:
                # Retention bonus increases stability
                difficulty = min(max(current_difficulty - 0.2, 1.0), 10.0)
                factor = 1.0 + math.exp(2.0) * math.pow(current_difficulty, -0.5)
                stability = current_stability * factor
                new_reps = reps + 1
                new_lapses = lapses
                new_state = "review"
            else:
                # Lapse reduces stability
                difficulty = min(max(current_difficulty + 0.5, 1.0), 10.0)
                stability = max(0.4, current_stability * 0.2)
                new_reps = reps
                new_lapses = lapses + 1
                new_state = "learning"

        # Calculate interval in days (for 90% retention, interval approx equals stability)
        interval_days = max(1.0, stability * (math.log(TARGET_RETENTION) / math.log(0.9)))
        next_review = now + datetime.timedelta(days=round(interval_days, 1))

        # Mastery score normalized in [0.0, 1.0]
        # Full mastery reached when stability reaches 30+ days and difficulty is low
        raw_mastery = min(stability / 30.0, 1.0) * (1.0 - 0.04 * (difficulty - 1.0))
        mastery_score = round(min(max(raw_mastery, 0.0), 1.0), 2)

        return FSRSState(
            stability=round(stability, 2),
            difficulty=round(difficulty, 2),
            reps=new_reps,
            lapses=new_lapses,
            state=new_state,
            next_review=next_review,
            mastery_score=mastery_score,
        )


fsrs_engine = FSRSEngine()
