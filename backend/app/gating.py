"""Mastery gating (syllabus Part 1, point 4 and Part 5).

The curriculum is a linear chain of units. Unit N+1 unlocks when every
checkpoint of unit N has passed. Reviews are a separate reinforcement track
(their own queue + HUD pill); a due review never re-locks the path, so a
learner returning after days away isn't blocked from continuing — only
reminded to review.

Unlocks are sticky: once earned they are stored in state["unlocked_units"]
and never removed.
"""

from __future__ import annotations

import time

from . import hlr


def checkpoint_ids(lessons: list[dict]) -> list[str]:
    return [l["checkpoint"]["id"] for l in lessons]


def unit_passed(state: dict, lessons: list[dict]) -> bool:
    passed = set(state["passed"])
    return bool(lessons) and all(cid in passed for cid in checkpoint_ids(lessons))


def unit_review_due(state: dict, lessons: list[dict], now: float | None = None) -> list[str]:
    """Lesson ids in this unit whose skill is currently due for review."""
    due = []
    for lesson in lessons:
        sk = state["skills"].get(lesson["id"])
        if sk and sk["last_practiced"] is not None and hlr.is_due(
            sk["h_days"], sk["last_practiced"], now
        ):
            due.append(lesson["id"])
    return due


def refresh_unlocks(
    state: dict,
    ordered_units: list[str],
    lessons_by_unit: dict[str, list[dict]],
    now: float | None = None,
) -> list[str]:
    """Recompute sticky unlocks along the linear chain. Returns newly unlocked.

    `now` is accepted (and ignored) for signature compatibility with callers
    that compute a timestamp once; unlock decisions depend only on passed
    checkpoints, never on the review clock.
    """
    unlocked = set(state["unlocked_units"])
    newly: list[str] = []
    if not ordered_units:
        return newly
    if ordered_units[0] not in unlocked:
        unlocked.add(ordered_units[0])
        newly.append(ordered_units[0])
    for i in range(1, len(ordered_units)):
        unit, prev = ordered_units[i], ordered_units[i - 1]
        if unit in unlocked:
            continue
        if not lessons_by_unit.get(unit):
            break  # unit itself has no content; chain stalls (placeholder future world)
        prev_lessons = lessons_by_unit.get(prev, [])
        if not prev_lessons:
            break
        if not unit_passed(state, prev_lessons):
            break
        unlocked.add(unit)
        newly.append(unit)
    state["unlocked_units"] = [u for u in ordered_units if u in unlocked]
    return newly


def lesson_statuses(state: dict, lessons: list[dict]) -> list[str]:
    """Per-lesson: 'done' | 'available' | 'locked'. Sequential within a unit."""
    statuses: list[str] = []
    prev_passed = True
    passed = set(state["passed"])
    for lesson in lessons:
        cid = lesson["checkpoint"]["id"]
        if cid in passed:
            statuses.append("done")
        elif prev_passed:
            statuses.append("available")
        else:
            statuses.append("locked")
        prev_passed = cid in passed
    return statuses
