"""Learner state persistence: single JSON file, atomic writes, thread-safe.

State shape:
{
  "xp": int,
  "streak": int,
  "last_active_date": "YYYY-MM-DD" | null,
  "skills": {lesson_id: {"h_days": float, "last_practiced": epoch | null,
                          "correct": int, "incorrect": int}},
  "attempts": {checkpoint_id: int},
  "passed": [checkpoint_id, ...],
  "unlocked_units": [unit_id, ...],
  "completed_lessons": [lesson_id, ...]
}
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
import time
from pathlib import Path

from . import hlr

_LOCK = threading.Lock()


def default_state() -> dict:
    return {
        "xp": 0,
        "streak": 0,
        "last_active_date": None,
        "skills": {},
        "attempts": {},
        "passed": [],
        "unlocked_units": [],
        "completed_lessons": [],
    }


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(default_state())

    def _write(self, state: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self.path)  # atomic on POSIX

    def load(self) -> dict:
        with _LOCK:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            # forward-compat: fill any missing keys
            for k, v in default_state().items():
                state.setdefault(k, v)
            return state

    def save(self, state: dict) -> None:
        with _LOCK:
            self._write(state)

    def reset(self) -> None:
        self.save(default_state())


def touch_activity(state: dict, now: float | None = None) -> None:
    """Update the daily streak. Call on any scored learner action."""
    now = time.time() if now is None else now
    today = _dt.date.fromtimestamp(now).isoformat()
    last = state.get("last_active_date")
    if last == today:
        return
    yesterday = (_dt.date.fromtimestamp(now) - _dt.timedelta(days=1)).isoformat()
    state["streak"] = state["streak"] + 1 if last == yesterday else 1
    state["last_active_date"] = today


def get_skill(state: dict, lesson_id: str) -> dict:
    """Fetch (or lazily create) the skill record for a lesson."""
    skills = state["skills"]
    if lesson_id not in skills:
        skills[lesson_id] = {
            "h_days": hlr.INITIAL_H_DAYS,
            "last_practiced": None,
            "correct": 0,
            "incorrect": 0,
        }
    return skills[lesson_id]


def record_result(state: dict, lesson_id: str, correct: bool, now: float | None = None) -> dict:
    """Apply HLR update for a practice/review attempt on a lesson's skill."""
    now = time.time() if now is None else now
    sk = get_skill(state, lesson_id)
    if correct:
        sk["h_days"] = hlr.on_correct(sk["h_days"])
        sk["correct"] += 1
    else:
        sk["h_days"] = hlr.on_wrong(sk["h_days"])
        sk["incorrect"] += 1
    sk["last_practiced"] = now
    touch_activity(state, now)
    return sk
