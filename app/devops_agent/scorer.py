from __future__ import annotations


def calculate_score(total_time_seconds: float, commit_count: int) -> dict:
    """Calculate final score based on time taken and number of commits."""
    base_score = 100
    speed_bonus = 10 if total_time_seconds < 300 else 0
    efficiency_penalty = max(0, (commit_count - 20) * 2)
    final_score = max(0, base_score + speed_bonus - efficiency_penalty)
    return {
        "base_score": base_score,
        "speed_bonus": speed_bonus,
        "efficiency_penalty": efficiency_penalty,
        "final_score": final_score,
    }
