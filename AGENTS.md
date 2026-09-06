# AGENTS.md — Descent

Local single-user learning app that teaches C gamedev (syllabus in `c-gamedev-complete-syllabus.md`, design in `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`). Python/FastAPI backend serves a vanilla JS SPA (no build step).

## Commands

Run from `backend/` (the app is `app` package there). The venv is at repo **root** (`../.venv`), not under `backend/`.

```bash
# run the app (API + frontend, auto-reload); bootstraps venv+deps on first run:
./run.sh                        # from repo root; ./run.sh 9000 for another port

# tests — MUST run from backend/ with PYTHONPATH=. :
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q

# single test file / test:
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py::test_boss0_reference_passes_validator -q

# run the server directly (serves API + static frontend; ./run.sh is a thin wrapper):
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend smoke tests (node + jsdom, no browser; `jsdom` in `frontend/` deps):

```bash
cd frontend && npm test
# npm test wraps: node --test "tests/*.test.js"
# bare `node --test tests/` FAILS (MODULE_NOT_FOUND) — always use the glob form.
```

Deps live in `backend/requirements.txt`. First setup: `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.

## Architecture / layout

- `backend/app/` — FastAPI app (`main.py` wires everything). `hlr.py` (spaced repetition), `gating.py` (unlock chain), `store.py` (JSON persistence), `runner.py` (C compile/run), `llm.py` (OpenRouter), `content.py` (curriculum loader).
- `backend/content/` — `tree.json` = metadata for **all 8 worlds**; `worldN.json` = authored lessons. Only `world0.json` has real content (19 lessons + Boss 0); worlds 1–7 are placeholders.
- `frontend/` — ES-module SPA, no build. `index.html` → `app.js` → `views/{path,lesson,review}.js` + `api.js` + `views/dom.js`. Build-a-checkpoint UI is shared: `views/editor.js` (`checkpointEditor`) is used by both the lesson page and the review page's "Re-attempt from memory".
- `data/state.json` — learner state, generated at first run; gitignored, safe to delete to reset. Now includes `solutions: {checkpoint_id: code}` (last-passing submission; used only by the gated "Show old solution" reveal — revealed runs are graded but never mutate XP/HLR).

## Gotchas

- **Tests fail from repo root** — they import `app.*`, so run them from `backend/` with `PYTHONPATH=.`.
- **C checkpoints**: backend runs learner code with real `gcc`. Function checkpoints: harness (from content) does `#include "learner.c"`; `exit 0` = pass. Program/boss checkpoints (`kind: "program"`) need a named validator in `runner.py` `VALIDATORS` and a `validator` field in content — add both when adding one.
- **Boss 0**: spring sim (`F = -k·r` to box centre (50,50), `K={40,30,35}`, 200 ticks × 3 balls). Pass = velocity Verlet (or any symplectic scheme): the energy check trips on turning-point radius growth > 0.5, which explicit Euler causes. Don't "fix" it back to gravity-bounce — that physics is energy-stable under any integrator and can't discriminate.
- **Never leak quiz answers**: `GET /api/lesson/{id}` strips the practice `answer` field; if you add a field used for grading, hide it from that endpoint too.
- **OpenRouter key** in `backend/.env` (gitignored, loaded via python-dotenv). `llm.py` works keyless and falls back to static authored hints — don't hardcode the key anywhere.
- **Gating stalls on content-less units**: units in worlds 1–7 have no lessons, so the linear unlock chain stops there by design until you author their `worldN.json`.
- **Frontend tests (node + jsdom)**: `app.js` only *registers* a DOMContentLoaded listener, and jsdom never auto-fires it — tests must `document.dispatchEvent(new window.Event('DOMContentLoaded'))` after importing `app.js`. Page tests import views directly with a unique query string (`../views/lesson.js?lv_a`) so each test gets a fresh module instance. Stub `window.scrollTo` and `scrollIntoView` in jsdom.
- **Shuffle keys must never collide across purposes**: `shuffleStable` pins a permutation per key; the lesson-page warm-up uses `warmup:`/`w:`-prefixed keys while lesson practice uses `{lesson_id}:p{n}` (same key on review page = same order). Reusing one key for two differently-sized question lists truncates the shorter permutation over the longer list.
- `views/*.js` import `refreshHud` from `../app.js`, and `app.js` imports the views — a runtime-safe circular import; keep `refreshHud` exported from `app.js`.
