# AGENTS.md — Descent

Local single-user learning app that teaches C gamedev (syllabus in `c-gamedev-complete-syllabus.md`, design in `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`). Python/FastAPI backend serves a vanilla JS SPA (no build step).

## Commands

Run from `backend/` (the app is `app` package there). The venv is at repo **root** (`../.venv`), not under `backend/`.

```bash
# tests — MUST run from backend/ with PYTHONPATH=. :
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q

# single test file / test:
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py::test_boss0_reference_passes_validator -q

# run the server (serves API + static frontend, no separate dev server):
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Deps live in `backend/requirements.txt`. First setup: `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.

## Architecture / layout

- `backend/app/` — FastAPI app (`main.py` wires everything). `hlr.py` (spaced repetition), `gating.py` (unlock chain), `store.py` (JSON persistence), `runner.py` (C compile/run), `llm.py` (OpenRouter), `content.py` (curriculum loader).
- `backend/content/` — `tree.json` = metadata for **all 8 worlds**; `worldN.json` = authored lessons. Only `world0.json` has real content (18 lessons + Boss 0); worlds 1–7 are placeholders.
- `frontend/` — ES-module SPA, no build. `index.html` → `app.js` → `views/{path,lesson,review}.js` + `api.js` + `views/dom.js`.
- `data/state.json` — learner state, generated at first run; gitignored, safe to delete to reset.

## Gotchas

- **Tests fail from repo root** — they import `app.*`, so run them from `backend/` with `PYTHONPATH=.`.
- **C checkpoints**: backend runs learner code with real `gcc`. Function checkpoints: harness (from content) does `#include "learner.c"`; `exit 0` = pass. Program/boss checkpoints (`kind: "program"`) need a named validator in `runner.py` `VALIDATORS` and a `validator` field in content — add both when adding one.
- **Never leak quiz answers**: `GET /api/lesson/{id}` strips the practice `answer` field; if you add a field used for grading, hide it from that endpoint too.
- **OpenRouter key** in `backend/.env` (gitignored, loaded via python-dotenv). `llm.py` works keyless and falls back to static authored hints — don't hardcode the key anywhere.
- **Gating stalls on content-less units**: units in worlds 1–7 have no lessons, so the linear unlock chain stops there by design until you author their `worldN.json`.
- `views/*.js` import `refreshHud` from `../app.js`, and `app.js` imports the views — a runtime-safe circular import; keep `refreshHud` exported from `app.js`.
