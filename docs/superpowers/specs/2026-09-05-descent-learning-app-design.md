# Descent — Gamified C Gamedev Learning App (Design Spec)

Date: 2026-09-05. Status: approved by user. Implements Part 5 of `c-gamedev-complete-syllabus.md`.

## Goal

Single-user local web app ("Descent") that teaches the C gamedev curriculum in the
syllabus, Duolingo-style: Worlds → Units → Lessons → Boss checkpoints, with
worked-example → guided-practice → solo-checkpoint lesson shape, Half-Life
Regression spaced repetition, mastery gating, XP/streak/crowns, and Socratic
LLM hints via OpenRouter (free models), with static-hint fallback.

## Decisions (user-approved)

- Backend: Python FastAPI + uvicorn, serves the static frontend; port 8000.
- Frontend: vanilla HTML/CSS/JS SPA, no build step, hash router.
- Storage: single JSON file (`data/state.json`), atomic writes. SQLite later only if needed.
- Checkpoints: real compile+run. Backend invokes gcc (C11) against per-checkpoint
  harnesses in a temp dir; timeout + POSIX rlimits (CPU, address space).
- Content: full 8-world tree metadata; World 0 (Units 0–3, 18 lessons + Boss 0)
  fully authored; Worlds 1–7 shown locked ("coming soon").
- LLM: OpenRouter key in `backend/.env` (gitignored, never sent to browser).
  Dynamic free-model discovery (`/api/v1/models`, `pricing.prompt == "0"`, MiniMax
  preferred), hardcoded fallback list, static authored hints as final fallback.

## Architecture

```
backend/
  app/main.py      FastAPI: API routes + static file mounting
  app/hlr.py       p = 2^(-Δt/h); correct: h*=1.7; wrong: h=max(h*0.4, h_min);
                   due when p < 0.85; pure functions
  app/store.py     thread-safe JSON load/save (tmp+rename), activity/streak helpers
  app/gating.py    linear unlock chain; unlock when prev unit checkpoints pass AND
                   its review queue is empty; sticky unlocks
  app/runner.py    gcc compile + run, 5s timeout, rlimits, structured results;
                   function-level (harness.c #includes learner.c) and
                   program-level (Boss 0: run twice, compare + invariant checks)
  app/llm.py       model discovery, chat completion w/ per-model fallback,
                   429 backoff, None on total failure
  app/content.py   content loading + validation (ids unique, 3-phase lessons)
  content/tree.json    all worlds/units/bosses metadata
  content/world*.json  authored lessons (world 0 complete)
frontend/
  index.html, styles.css, app.js, api.js, highlight.js, views/(path|lesson|review).js
data/state.json          learner state (xp, streak, last_active_date, skills{},
                         attempts, unlocked, passed)
```

### API

- `GET /api/state` — xp, streak, crowns, due-review count
- `GET /api/curriculum` — tree with per-node status (locked/available/done/review-due)
- `GET /api/lesson/{id}` — theory, worked example, practice items, checkpoint spec
- `POST /api/answer` — `{lesson_id, q_index, choice}` → correctness, xp, hint
- `POST /api/checkpoint/run` — `{lesson_id, code}` → compile/run result + xp/unlock grant
- `GET /api/review-queue` — due lessons (p_recall < 0.85)
- `POST /api/hint` — `{lesson_id, context}` → Socratic hint (LLM → static fallback)

### Data model

- skill per lesson: `{h_days, last_practiced, correct, incorrect}`
- `attempts[checkpoint_id]` for first-try bonus XP
- XP: practice item +5; checkpoint pass +20 (+10 first try); review item +3; Boss 0 +100.

### Testing/verification

pytest: HLR math vs hand-computed values, gating transitions, runner on
known-good/bad/infinite-loop C, store atomicity, content validation, LLM fallback
(mocked HTTP). Scripted end-to-end run via HTTP: fresh state → answer practice →
fail+pass checkpoint → verify xp/streak/unlock/review behavior. Live OpenRouter
smoke test for one hint.

### Security

API key only in `backend/.env`. Server binds 127.0.0.1. C runner: 5 s wall
timeout, RLIMIT_CPU 5 s, RLIMIT_AS 512 MB, temp dir per run, learner code runs
as the local user (single-user app — documented, not a multi-tenant sandbox).
