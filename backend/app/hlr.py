"""Half-Life Regression (simplified) — the syllabus's Part 5 formula.

Each skill has a memory half-life `h` (in days). Probability of recall after
`dt` days since last practice:

    p = 2 ** (-dt / h)

Correct recall grows h, wrong recall shrinks it. A skill is due for review
when its current recall probability drops below DUE_THRESHOLD.
"""

from __future__ import annotations

import time

GROWTH_FACTOR = 1.7        # h multiplier on correct recall (tunable, plan: 1.3–2.0)
SHRINK_FACTOR = 0.4        # h multiplier on wrong recall (plan: 0.3–0.5)
H_MIN_DAYS = 1.0 / 24.0    # 1 hour floor after a wrong answer
INITIAL_H_DAYS = 1.0       # new skills start with a 1-day half-life
DUE_THRESHOLD = 0.85       # review once p_recall drops below this

SECONDS_PER_DAY = 86400.0


def p_recall(h_days: float, dt_days: float) -> float:
    """Probability of recalling a skill with half-life h after dt days."""
    if dt_days <= 0:
        return 1.0
    return 2.0 ** (-dt_days / h_days)


def on_correct(h_days: float) -> float:
    return h_days * GROWTH_FACTOR


def on_wrong(h_days: float) -> float:
    return max(h_days * SHRINK_FACTOR, H_MIN_DAYS)


def days_until_due(h_days: float) -> float:
    """Days after practice at which p_recall first hits DUE_THRESHOLD.

    Solves 2**(-t/h) = threshold  ->  t = -h * log2(threshold).
    """
    import math

    return -h_days * math.log2(DUE_THRESHOLD)


def current_p_recall(h_days: float, last_practiced_ts: float, now_ts: float | None = None) -> float:
    """Recall probability right now for a skill last practiced at last_practiced_ts."""
    now = time.time() if now_ts is None else now_ts
    dt_days = max(0.0, (now - last_practiced_ts) / SECONDS_PER_DAY)
    return p_recall(h_days, dt_days)


def is_due(h_days: float, last_practiced_ts: float, now_ts: float | None = None) -> bool:
    return current_p_recall(h_days, last_practiced_ts, now_ts) < DUE_THRESHOLD
