"""FastAPI app: JSON API + static frontend. Single process, single user, local only.

Run:  ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import json
import os
import secrets
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

FOLLOWUP_SYSTEM = (
    "You are a C/gamedev tutor generating a follow-up multiple-choice question for "
    "a learner who answered wrong. Output ONLY a JSON object with keys: "
    '"q" (question string), "choices" (3 short strings), "answer" (0-based index of '
    'the correct choice), "explanation" (1-2 sentences). Adapt difficulty to the '
    "learner's mastery: half-life < 1 day means generate an easier stepping-stone "
    "question; >= 4 days means a harder one. No markdown fences, no extra text."
)

# Ephemeral answers for LLM-generated follow-up/review questions:
# token -> {"answer", "explanation"}. In-memory only — a restart drops
# unanswered questions, which is fine (regenerated on demand).
FOLLOWUPS: dict[str, dict] = {}

REVIEW_SYSTEM = (
    "You are a C/gamedev tutor writing ONE multiple-choice review question for "
    "spaced repetition. Test recall of the lesson's core concept from a slightly "
    "different angle than the original practice question. Output ONLY a JSON "
    'object with keys: "q", "choices" (3 short strings), "answer" (0-based index '
    'of the correct choice), "explanation" (1-2 sentences). No markdown fences.'
)

# (lesson_id, utc-day) -> generated question dict or None. Regenerated daily;
# None is cached too so a keyless/down LLM isn't retried on every page load.
_REVIEW_GEN_CACHE: dict[tuple[str, str], dict | None] = {}


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


class FollowupReq(BaseModel):
    token: str
    choice: int


def _parse_followup(text: str | None) -> dict | None:
    """Validate the LLM's follow-up JSON; tolerate markdown fences around it."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    q, choices, answer = obj.get("q"), obj.get("choices"), obj.get("answer")
    if not isinstance(q, str) or not isinstance(choices, list):
        return None
    if len(choices) < 2 or not all(isinstance(c, str) for c in choices):
        return None
    if not isinstance(answer, int) or not (0 <= answer < len(choices)):
        return None
    return {"q": q, "choices": choices, "answer": answer,
            "explanation": str(obj.get("explanation", ""))}


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
                else:
                    unit_state = "locked"
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
    # Recompute unlocks in case state was seeded or manually edited — atomically.
    def refresh(state):
        gating.refresh_unlocks(state, content.ordered_units(), content.lessons_by_unit())
        return _curriculum_view(state)

    return db.update(refresh)


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
    gen_left = 2  # fresh-question budget per queue load (free-tier rate limits)
    for lid, sk in state["skills"].items():
        if sk["last_practiced"] is None:
            continue
        p = hlr.current_p_recall(sk["h_days"], sk["last_practiced"], now)
        if p < hlr.DUE_THRESHOLD:
            lesson = content.lesson(lid)
            generated = None
            if lesson and gen_left > 0:
                generated = _generated_review_question(lesson)
            if generated is not None:
                gen_left -= 1
            cp = lesson["checkpoint"] if lesson else None
            due.append(
                {
                    "lesson_id": lid,
                    "title": lesson["title"] if lesson else lid,
                    "p_recall": round(p, 3),
                    "practice": [
                        {k: q[k] for k in ("q", "choices")}
                        for q in (lesson["practice"] if lesson else [])
                    ],
                    "generated": generated,
                    "checkpoint": (
                        {"title": cp["title"], "kind": cp.get("kind"), "starter_code": cp["starter_code"]}
                        if cp else None
                    ),
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
    if not (0 <= req.choice < len(item["choices"])):
        raise HTTPException(status_code=400, detail="choice out of range")
    correct = req.choice == item["answer"]
    cp = lesson["checkpoint"]

    def score(state: dict) -> tuple[float, int]:
        is_review = cp["id"] in state["passed"]
        record = store.record_result(state, req.lesson_id, correct)
        xp = (XP_REVIEW if is_review else XP_PRACTICE) if correct else 0
        state["xp"] += xp
        return record["h_days"], xp

    h_days, xp_delta = db.update(score)
    resp: dict = {
        "correct": correct,
        "explanation": item.get("explanation", ""),
        "xp": xp_delta,
        "h_days": round(h_days, 3),
        "answer_index": item["answer"],  # safe post-answer: revealed for highlighting
    }
    if not correct:
        followup = _try_followup(lesson, item, req.choice, h_days)
        if followup:
            resp["followup"] = followup
    return resp


def _try_followup(lesson: dict, item: dict, wrong_choice: int, h_days: float) -> dict | None:
    """Ask the LLM for an adjusted-difficulty follow-up. Answer stays server-side."""
    prompt = (
        f"Lesson: {lesson['title']}\nQuestion: {item['q']}\n"
        f"Learner picked (wrong): {item['choices'][wrong_choice]}\n"
        f"Correct answer: {item['choices'][item['answer']]}\n"
        f"Mastery half-life: {h_days:.2f} days"
    )
    parsed = _parse_followup(llm_client.chat(FOLLOWUP_SYSTEM, prompt, max_models=3)[0])
    if not parsed:
        return None
    token = secrets.token_urlsafe(12)
    FOLLOWUPS[token] = {"answer": parsed["answer"], "explanation": parsed["explanation"]}
    return {"token": token, "q": parsed["q"], "choices": parsed["choices"]}


def _generated_review_question(lesson: dict) -> dict | None:
    """One fresh LLM review question per lesson per day; answer stays server-side.
    Static authored practice remains the fallback when the LLM is unavailable."""
    key = (lesson["id"], time.strftime("%Y-%m-%d", time.gmtime()))
    if key in _REVIEW_GEN_CACHE:
        return _REVIEW_GEN_CACHE[key]
    out = None
    parsed = _parse_followup(
        llm_client.chat(REVIEW_SYSTEM, f"Lesson: {lesson['title']}\n"
                                       f"The core concept:\n{lesson['theory'][:1200]}",
                        max_models=3)[0]
    )
    if parsed:
        token = secrets.token_urlsafe(12)
        FOLLOWUPS[token] = {"answer": parsed["answer"], "explanation": parsed["explanation"]}
        out = {"token": token, "q": parsed["q"], "choices": parsed["choices"]}
    _REVIEW_GEN_CACHE[key] = out
    return out


@app.post("/api/followup/answer")
def post_followup_answer(req: FollowupReq):
    rec = FOLLOWUPS.pop(req.token, None)  # one-shot
    if not rec:
        raise HTTPException(status_code=404, detail="unknown follow-up")
    return {"correct": req.choice == rec["answer"], "explanation": rec["explanation"],
            "answer_index": rec["answer"]}


@app.post("/api/checkpoint/run")
def post_run(req: RunReq):
    lesson = content.lesson(req.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="lesson not found")
    cp = lesson["checkpoint"]
    res = runner.compile_and_run(cp, req.code)  # slow: stays outside the lock

    def score(state: dict) -> tuple[int, int, list[str]]:
        state["attempts"][cp["id"]] = state["attempts"].get(cp["id"], 0) + 1
        attempt_n = state["attempts"][cp["id"]]
        xp, newly = 0, []
        if res["passed"]:
            if cp["id"] in state["passed"]:
                # Re-pass as review: pays XP only when the skill is actually due.
                sk = state["skills"].get(lesson["id"])
                if sk and sk["last_practiced"] and hlr.is_due(sk["h_days"], sk["last_practiced"]):
                    xp = XP_REVIEW
            else:
                xp = (XP_BOSS if cp.get("kind") == "program" else XP_CHECKPOINT) + (
                    XP_FIRST_TRY_BONUS if attempt_n == 1 else 0
                )
                state["passed"].append(cp["id"])
                state["completed_lessons"].append(lesson["id"])
                newly = gating.refresh_unlocks(state, content.ordered_units(), content.lessons_by_unit())
            store.record_result(state, lesson["id"], True)
        elif res["compiled"]:
            store.record_result(state, lesson["id"], False)
        state["xp"] += xp
        return attempt_n, xp, newly

    attempt_n, xp_delta, newly = db.update(score)
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
