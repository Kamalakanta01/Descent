"""FastAPI app: JSON API + static frontend. Single process, single user, local only.

Run:  ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gating, hlr, llm, runner, store
from .content import Content

BASE = Path(__file__).resolve().parent.parent
FRONTEND = BASE.parent / "frontend"
STATE_PATH = BASE.parent / "data" / "state.json"

load_dotenv(BASE / ".env")

content = Content(BASE / "content")
db = store.Store(STATE_PATH)
llm_client = llm.LLMClient(api_key=os.environ.get("OPENROUTER_API_KEY") or None)

app = FastAPI(title="Descent", docs_url=None, redoc_url=None, openapi_url=None)

# ---------------------------------------------------------------------------
# XP economy
# ---------------------------------------------------------------------------
XP_PRACTICE = 5
XP_CHECKPOINT = 20
XP_FIRST_TRY_BONUS = 10
XP_REVIEW = 3
XP_BOSS = 100

SOCRATIC_SYSTEM = (
    "You are a Socratic C/gamedev tutor embedded in a learning app. The learner "
    "is stuck. Never give the direct answer or corrected code. Ask ONE short, "
    "concrete guiding question that leads them toward the fix. 2-3 sentences max. "
    "Plain text, no markdown."
)


class AnswerReq(BaseModel):
    lesson_id: str
    q_index: int
    choice: int


class RunReq(BaseModel):
    lesson_id: str
    code: str


class HintReq(BaseModel):
    lesson_id: str
    q_index: int | None = None
    wrong_answer: str | None = None
    compile_errors: str | None = None


def _skill_summary(state: dict) -> dict:
    """{lesson_id: p_recall} for every practiced skill, plus due count."""
    now = time.time()
    out = {}
    due = 0
    for lid, sk in state["skills"].items():
        if sk["last_practiced"] is None:
            continue
        p = hlr.current_p_recall(sk["h_days"], sk["last_practiced"], now)
        out[lid] = round(p, 3)
        if p < hlr.DUE_THRESHOLD:
            due += 1
    return {"skills": out, "due": due}


def _curriculum_view(state: dict) -> dict:
    now = time.time()
    unlocked = set(state["unlocked_units"])
    worlds = []
    for w in content.worlds_view():
        w_units = []
        for u in w["units"]:
            lessons = content.unit_lessons(u["id"])
            statuses = gating.lesson_statuses(state, lessons) if lessons else []
            unit_state = "empty"
            if lessons:
                if all(s == "done" for s in statuses):
                    unit_state = "done"
                elif u["id"] in unlocked:
                    unit_state = "available"
            unit_state = unit_state if u["id"] in unlocked else "locked"
            lesson_list = []
            for les, st in zip(lessons, statuses):
                sk = state["skills"].get(les["id"])
                p = (
                    hlr.current_p_recall(sk["h_days"], sk["last_practiced"], now)
                    if sk and sk["last_practiced"]
                    else None
                )
                lesson_list.append(
                    {
                        "id": les["id"],
                        "title": les["title"],
                        "status": st,
                        "p_recall": None if p is None else round(p, 3),
                        "due": p is not None and p < hlr.DUE_THRESHOLD,
                        "kind": les["checkpoint"].get("kind", "function"),
                    }
                )
            w_units.append(
                {
                    "id": u["id"],
                    "title": u["title"],
                    "kind": u["kind"],
                    "state": unit_state,
                    "lessons": lesson_list,
                }
            )
        worlds.append(
            {
                "id": w["id"],
                "title": w["title"],
                "subtitle": w.get("subtitle", ""),
                "units": w_units,
            }
        )
    return {
        "worlds": worlds,
        "xp": state["xp"],
        "streak": state["streak"],
        "due_reviews": sum(
            1 for w in worlds for u in w["units"] for l in u["lessons"] if l["due"]
        ),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/state")
def get_state():
    state = db.load()
    s = _skill_summary(state)
    return {
        "xp": state["xp"],
        "streak": state["streak"],
        "due_reviews": s["due"],
        "completed_lessons": state["completed_lessons"],
        "passed": state["passed"],
    }


@app.get("/api/curriculum")
def get_curriculum():
    state = db.load()
    # Recompute unlocks in case state was seeded or manually edited.
    gating.refresh_unlocks(state, content.ordered_units(), content._lessons_by_unit)
    db.save(state)
    return _curriculum_view(state)


@app.get("/api/lesson/{lesson_id}")
def get_lesson(lesson_id: str):
    lesson = content.lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson not found")
    state = db.load()
    cp = lesson["checkpoint"]
    return {
        "id": lesson["id"],
        "title": lesson["title"],
        "theory": lesson["theory"],
        "worked_example": lesson["worked_example"],
        "practice": [
            {k: q[k] for k in ("q", "choices")}  # never leak 'answer' to the client
            for q in lesson["practice"]
        ],
        "checkpoint": {
            "id": cp["id"],
            "title": cp["title"],
            "instructions": cp["instructions"],
            "starter_code": cp["starter_code"],
            "kind": cp.get("kind", "function"),
        },
        "attempts": state["attempts"].get(cp["id"], 0),
        "passed": cp["id"] in state["passed"],
    }


@app.get("/api/review-queue")
def get_review_queue():
    state = db.load()
    now = time.time()
    due = []
    for lid, sk in state["skills"].items():
        if sk["last_practiced"] is None:
            continue
        p = hlr.current_p_recall(sk["h_days"], sk["last_practiced"], now)
        if p < hlr.DUE_THRESHOLD:
            lesson = content.lesson(lid)
            due.append(
                {
                    "lesson_id": lid,
                    "title": lesson["title"] if lesson else lid,
                    "p_recall": round(p, 3),
                    "practice": [
                        {k: q[k] for k in ("q", "choices")}
                        for q in (lesson["practice"] if lesson else [])
                    ],
                }
            )
    return {"due": due}


@app.post("/api/answer")
def post_answer(req: AnswerReq):
    lesson = content.lesson(req.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson not found")
    try:
        item = lesson["practice"][req.q_index]
    except IndexError:
        raise HTTPException(status_code=400, detail="bad q_index")
    correct = req.choice == item["answer"]
    state = db.load()
    cp = lesson["checkpoint"]
    is_review = cp["id"] in state["passed"]
    record = store.record_result(state, req.lesson_id, correct)
    xp_delta = 0
    if correct:
        xp_delta = XP_REVIEW if is_review else XP_PRACTICE
        state["xp"] += xp_delta
    db.save(state)
    return {
        "correct": correct,
        "explanation": item.get("explanation", ""),
        "xp": xp_delta,
        "h_days": round(record["h_days"], 3),
    }


@app.post("/api/checkpoint/run")
def post_run(req: RunReq):
    lesson = content.lesson(req.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson not found")
    cp = lesson["checkpoint"]
    state = db.load()
    state["attempts"][cp["id"]] = state["attempts"].get(cp["id"], 0) + 1
    attempt_n = state["attempts"][cp["id"]]

    res = runner.compile_and_run(cp, req.code)

    xp_delta = 0
    newly: list[str] = []
    hint = None
    if res["passed"]:
        first_time = cp["id"] not in state["passed"]
        if first_time:
            base = XP_BOSS if cp.get("kind") == "program" else XP_CHECKPOINT
            bonus = XP_FIRST_TRY_BONUS if attempt_n == 1 else 0
            xp_delta = base + bonus
            state["xp"] += xp_delta
            state["passed"].append(cp["id"])
            state["completed_lessons"].append(lesson["id"])
            store.record_result(state, lesson["id"], True)
            newly = gating.refresh_unlocks(
                state, content.ordered_units(), content._lessons_by_unit
            )
    else:
        store.record_result(state, lesson["id"], False)

    db.save(state)
    return {**res, "xp": xp_delta, "attempt": attempt_n, "newly_unlocked": newly}


@app.post("/api/hint")
def post_hint(req: HintReq):
    lesson = content.lesson(req.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson not found")
    cp = lesson["checkpoint"]
    state = db.load()
    sk = state["skills"].get(req.lesson_id, {})
    parts = [f"Lesson: {lesson['title']} ({req.lesson_id})",
             f"Checkpoint: {cp['title']}", f"Instructions: {cp['instructions']}"]
    if req.wrong_answer:
        parts.append(f"Learner's wrong code/answer: {req.wrong_answer[:800]}")
    if req.compile_errors:
        parts.append(f"Compiler output: {req.compile_errors[:800]}")
    parts.append(f"Memory half-life for this skill: {sk.get('h_days', 1.0)} days")
    user = "\n".join(parts)
    content_txt, model = llm_client.chat(SOCRATIC_SYSTEM, user)
    if content_txt:
        return {"hint": content_txt, "source": f"llm:{model}"}
    hints = cp.get("static_hints", [])
    if hints:
        n = state["attempts"].get(cp["id"], 0)
        return {"hint": hints[n % len(hints)], "source": "static"}
    return {"hint": "Re-read the worked example above; your checkpoint is one concrete step from it.", "source": "static"}


# ---------------------------------------------------------------------------
# Frontend (mounted last so /api/* wins)
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
