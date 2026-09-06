# Descent

Gamified C gamedev learning app. Local single-user: FastAPI backend serves a
vanilla-JS SPA (no build step) and evaluates learner C code with real `gcc`
checkpoints. Spaced repetition (HLR), XP/streak economy, and a linear unlock
chain of 8 worlds with per-world boss battles.

Syllabus: `c-gamedev-complete-syllabus.md`
Design spec: `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`
Handoff state: `SESSION.md`

## Setup

```bash
python3 -m venv .venv                       # at the repo ROOT
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env        # optional OpenRouter key for hints
```

## Commands (run from `backend/`; the app is the `app` package there)

The venv is at the repo **root** (`../.venv`), not under `backend/`.

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

Then open http://127.0.0.1:8000.

## Architecture / layout

- `backend/app/` — FastAPI app (`main.py` wires everything). `hlr.py` (spaced repetition), `gating.py` (unlock chain), `store.py` (JSON persistence), `runner.py` (C compile/run), `llm.py` (OpenRouter), `content.py` (curriculum loader).
- `backend/content/` — `tree.json` = metadata for **all 8 worlds**; `worldN.json` = authored lessons. Only `world0.json` has real content; worlds 1–7 are placeholders.
- `frontend/` — ES-module SPA, no build. `index.html` → `app.js` → `views/{path,lesson,review}.js` + `api.js` + `views/dom.js`.
- `data/state.json` — learner state, generated at first run; gitignored, safe to delete to reset.