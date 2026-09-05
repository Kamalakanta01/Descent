import time

from app import gating

NOW = 1_700_000_000.0


def make_state():
    return {
        "xp": 0, "streak": 0, "last_active_date": None,
        "skills": {}, "attempts": {}, "passed": [],
        "unlocked_units": [], "completed_lessons": [],
    }


def lesson(lid):
    return {"id": lid, "checkpoint": {"id": lid + "c"}}


UNITS = ["w0u0", "w0u1", "w0u2", "w9uX"]  # w9uX has no authored content
LESSONS = {
    "w0u0": [lesson("l1"), lesson("l2")],
    "w0u1": [lesson("l3")],
    "w0u2": [lesson("l4")],
    # "w9uX": absent on purpose
}


def test_first_unit_unlocked_by_default():
    st = make_state()
    newly = gating.refresh_unlocks(st, UNITS, LESSONS, NOW)
    assert newly == ["w0u0"]
    assert st["unlocked_units"] == ["w0u0"]


def test_next_unit_unlocks_only_after_all_previous_passed():
    st = make_state()
    gating.refresh_unlocks(st, UNITS, LESSONS, NOW)
    st["passed"] = ["l1c"]  # l2 still missing
    assert gating.refresh_unlocks(st, UNITS, LESSONS, NOW) == []

    st["passed"].append("l2c")
    st["skills"]["l1"] = {"h_days": 1.0, "last_practiced": NOW, "correct": 1, "incorrect": 0}
    st["skills"]["l2"] = {"h_days": 1.0, "last_practiced": NOW, "correct": 1, "incorrect": 0}
    assert gating.refresh_unlocks(st, UNITS, LESSONS, NOW) == ["w0u1"]


def test_due_reviews_do_not_block_unlock():
    st = make_state()
    st["passed"] = ["l1c", "l2c"]
    week_ago = NOW - 7 * 86400
    st["skills"]["l1"] = {"h_days": 1.0, "last_practiced": week_ago, "correct": 1, "incorrect": 0}
    st["skills"]["l2"] = {"h_days": 1.0, "last_practiced": week_ago, "correct": 1, "incorrect": 0}
    newly = gating.refresh_unlocks(st, UNITS, LESSONS, NOW)
    assert "w0u1" in newly
    assert gating.unit_review_due(st, LESSONS["w0u0"], NOW) == ["l1", "l2"]


def test_unlocks_are_sticky():
    st = make_state()
    st["passed"] = ["l1c", "l2c"]
    st["skills"]["l1"] = {"h_days": 1.0, "last_practiced": NOW, "correct": 1, "incorrect": 0}
    st["skills"]["l2"] = {"h_days": 1.0, "last_practiced": NOW, "correct": 1, "incorrect": 0}
    gating.refresh_unlocks(st, UNITS, LESSONS, NOW)
    # reviews later come due; w0u1 must stay unlocked
    later = NOW + 10 * 86400
    gating.refresh_unlocks(st, UNITS, LESSONS, later)
    assert "w0u1" in st["unlocked_units"]


def test_units_without_content_gate_the_chain():
    st = make_state()
    st["passed"] = ["l1c", "l2c", "l3c", "l4c"]
    for lid in ("l1", "l2", "l3", "l4"):
        st["skills"][lid] = {"h_days": 1.0, "last_practiced": NOW, "correct": 1, "incorrect": 0}
    newly = gating.refresh_unlocks(st, UNITS, LESSONS, NOW)
    assert "w0u1" in newly and "w0u2" in newly
    assert "w9uX" not in st["unlocked_units"]


def test_lesson_statuses_sequential():
    st = make_state()
    st["passed"] = ["l1c"]
    assert gating.lesson_statuses(st, LESSONS["w0u0"]) == ["done", "available"]
    st2 = make_state()
    assert gating.lesson_statuses(st2, LESSONS["w0u0"]) == ["available", "locked"]
