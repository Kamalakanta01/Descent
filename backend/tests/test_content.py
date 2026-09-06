"""Tree metadata for the full 8-world curriculum. World 0 has authored
content in world0.json; worlds 1..7 are placeholders."""

import json
import pytest

from app.content import Content, ContentError


def test_tree_loads_and_worlds_present():
    c = Content("content")
    worlds = c.worlds_view()
    assert len(worlds) == 8
    assert [w["id"] for w in worlds] == list(range(8))


def test_world0_has_full_units_and_lessons():
    c = Content("content")
    units = c.worlds_view()[0]["units"]
    assert [u["id"] for u in units] == ["w0u0", "w0u1", "w0u2", "w0u3", "w0b0"]
    for u in units:
        assert c.unit_lessons(u["id"]), f"unit {u['id']} missing lessons"


def test_ordered_units_chains_across_worlds():
    c = Content("content")
    ordered = c.ordered_units()
    assert ordered[0] == "w0u0"
    assert ordered.count("w0b0") == 1
    assert any(u.startswith("w1") for u in ordered)


def test_practice_answers_are_distributed_across_positions():
    c = Content("content")
    qs = [
        q for u in c.worlds_view()[0]["units"]
        for l in c.unit_lessons(u["id"])
        for q in l["practice"]
    ]
    assert len(qs) >= 30
    positions = [q["answer"] for q in qs]
    assert len(set(positions)) >= 2, "correct answers must not all sit at index 0"
    assert positions.count(0) / len(positions) < 0.6
    for q in qs:
        assert 0 <= q["answer"] < len(q["choices"])


def test_validation_catches_missing_practice_answer(tmp_path):
    bad = {
        "world": 0,
        "units": [{
            "id": "tu",
            "lessons": [{
                "id": "t1", "title": "t",
                "theory": "...", "xp": 10,
                "worked_example": {"title": "x", "code": "c", "explanation": "e"},
                "practice": [{"q": "?", "choices": ["a", "b"]}],
                "checkpoint": {
                    "id": "t1c", "title": "c", "instructions": "i",
                    "starter_code": "s", "kind": "function",
                    "harness": "h", "static_hints": ["h"],
                },
            }],
        }],
    }
    p = tmp_path / "tree.json"
    p.write_text(json.dumps({"worlds": [{"id": 0, "title": "x", "units": [{"id": "tu", "title": "t", "kind": "unit"}]}]}))
    (tmp_path / "world0.json").write_text(json.dumps(bad))
    with pytest.raises(ContentError):
        Content(p.parent)
