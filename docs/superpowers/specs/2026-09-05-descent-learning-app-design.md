# Descent — Gamified C Gamedev Learning App (Design Spec)

Date: 2026-09-05. Status: approved by user. Implements Part 5 of `c-gamedev-complete-syllabus.md`.

Changes since approval (recorded in SESSION.md 2026-09-06):
- Review queue no longer *gates* unlocks — reviews are a reinforcement track only
  (a due review never re-locks the path). Removed the "review queue empty" unlock
  condition.
- `RLIMIT_AS` removed: ASan reserves ~15 TB of *virtual* shadow address space,
  which trips any hard limit. Sandboxing = RLIMIT_CPU, RLIMIT_FSIZE, process-group
  kill on timeout. `RLIMIT_NPROC` was also dropped after testing: it counts the
  UID's *total* processes and made LeakSanitizer's shutdown fork fail.
- Practice answers are distributed across choice positions (audited: all answerable
  questions had the correct answer at index 0) and shuffled client-side with
  session-stable identity.
- Adaptive follow-up questions and LLM-generated review questions (answers kept
  server-side), inline review warm-up on the lesson page, checkpoint re-run in
  review, compiler warnings surfaced to the learner, atomic `Store.update()`,
  `Runner` passes warnings through and kills the process group on timeout.
- World 0 now has 19 lessons + Boss 0; lesson w0u2l3 teaches *velocity* Verlet
  (kick-drift-kick), the scheme Boss 0 requires.

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
  harnesses in a temp dir; timeout + POSIX rlimits (CPU, FS size); learner process
  killed as a process group on timeout.
- Content: full 8-world tree metadata; World 0 (Units 0–3, 19 lessons + Boss 0)
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
  app/gating.py    linear unlock chain; unlock when prev unit checkpoints pass;
                   sticky unlocks; reviews are a separate, non-blocking track
  app/runner.py    gcc compile + run, 6s timeout, rlimits, process-group kill,
                   warnings surfaced; function-level (harness.c #includes
                   learner.c) and program-level (Boss 0: run twice, compare +
                   invariant checks) validators
  app/llm.py       model discovery, chat completion w/ per-model fallback,
                   429/529 backoff, None on total failure
  app/content.py   content loading + validation (ids unique, 3-phase lessons)
  content/tree.json    all worlds/units/bosses metadata
  content/world*.json  authored lessons (world 0 complete)
frontend/
  index.html, styles.css, app.js, api.js, views/(path|lesson|review|dom).js
data/state.json          learner state (xp, streak, last_active_date, skills{},
                         attempts, unlocked, passed)
```

### API

- `GET /api/state` — xp, streak, crowns, due-review count
- `GET /api/curriculum` — tree with per-node status (locked/available/done/review-due)
- `GET /api/lesson/{id}` — theory, worked example, practice items, checkpoint spec
  (practice `answer` field stripped; never sent to the browser)
- `POST /api/answer` — `{lesson_id, q_index, choice}` → correctness, xp, hint,
  `answer_index` (also used to highlight the correct choice post-answer); on a
  wrong answer may include an adaptive `followup` (answer kept server-side)
- `POST /api/checkpoint/run` — `{lesson_id, code}` → compile/run result + xp/unlock gift
- `GET /api/review-queue` — due lessons (p_recall < 0.85) plus up to two fresh
  LLM-generated questions per load (day-cached; answers kept server-side) and the
  checkpoint spec so review can re-run a lesson's checkpoint
- `POST /api/followup/answer` — `{token, choice}` → grades an LLM follow-up/generated
  question (one-shot token, answer never exposed)
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

API key only in `backend/.env`. Server binds 127.0.0.1. C runner: 6 s wall
timeout, RLIMIT_CPU 5 s, RLIMIT_FSIZE 2 MB, temp dir per run, learner code runs
as the local user (single-user app — documented, not a multi-tenant sandbox).
No RLIMIT_AS (ASan's shadow-memory reservation makes it impossible) and no
RLIMIT_NPROC (ASan's LeakSanitizer forks on exit); fork-bomb containment is the
process-group kill on timeout.
