"""Load and validate curriculum content. Tree metadata lives in tree.json;
per-world lesson content lives in content/worldN.json. Worlds 1..7 are
metadata-only placeholders (content comes later); only world 0 has full
lessons in this build."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_LESSON_KEYS = {"id", "title", "theory", "worked_example", "practice", "checkpoint"}
REQUIRED_CHECKPOINT_KEYS = {"id", "title", "instructions", "starter_code", "static_hints"}
VALID_KINDS = {"function", "program"}


class ContentError(ValueError):
    pass


def _validate_lesson(lesson: dict) -> None:
    missing = REQUIRED_LESSON_KEYS - set(lesson.keys())
    if missing:
        raise ContentError(f"lesson {lesson.get('id')!r} missing keys: {sorted(missing)}")
    cp = lesson["checkpoint"]
    cp_missing = REQUIRED_CHECKPOINT_KEYS - set(cp.keys())
    if cp_missing:
        raise ContentError(f"checkpoint {cp.get('id')!r} missing: {sorted(cp_missing)}")
    kind = cp.get("kind", "function")
    if kind not in VALID_KINDS:
        raise ContentError(f"checkpoint {cp['id']} bad kind {kind!r}")
    if kind == "function" and "harness" not in cp:
        raise ContentError(f"function checkpoint {cp['id']} missing harness code")
    if kind == "program" and "validator" not in cp:
        raise ContentError(f"program checkpoint {cp['id']} missing validator name")
    we = lesson["worked_example"]
    for k in ("title", "code", "explanation"):
        if k not in we:
            raise ContentError(f"worked_example missing {k!r} in {lesson['id']}")
    for i, q in enumerate(lesson["practice"]):
        for k in ("q", "choices", "answer"):
            if k not in q:
                raise ContentError(f"practice[{i}] in {lesson['id']} missing {k!r}")


class Content:
    def __init__(self, content_dir: str | Path):
        self.content_dir = Path(content_dir)
        self.tree = json.loads((self.content_dir / "tree.json").read_text(encoding="utf-8"))
        self.worlds: dict[int, dict] = {}
        for w in self.tree["worlds"]:
            path = self.content_dir / f"world{w['id']}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for unit in data["units"]:
                    for lesson in unit["lessons"]:
                        _validate_lesson(lesson)
                self.worlds[w["id"]] = data
        self._lessons: dict[str, dict] = {}
        self._lessons_by_unit: dict[str, list[dict]] = {}
        for w in self.worlds.values():
            for unit in w["units"]:
                self._lessons_by_unit[unit["unit_id"]] = unit["lessons"]
                for lesson in unit["lessons"]:
                    self._lessons[lesson["id"]] = lesson
        self._unit_ids_ordered = self._flatten_units()

    def _flatten_units(self) -> list[str]:
        out: list[str] = []
        for world in self.tree["worlds"]:
            for unit in world["units"]:
                out.append(unit["id"])
        return out

    def ordered_units(self) -> list[str]:
        return list(self._unit_ids_ordered)

    def unit_lessons(self, unit_id: str) -> list[dict]:
        return list(self._lessons_by_unit.get(unit_id, []))

    def lesson(self, lesson_id: str) -> dict | None:
        return self._lessons.get(lesson_id)

    def worlds_view(self) -> list[dict]:
        return self.tree["worlds"]
