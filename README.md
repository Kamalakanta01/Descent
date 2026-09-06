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
./run.sh          # one command: creates venv + installs deps on first run, then serves on :8000
# optional: ./run.sh 9000   to serve on a different port
```

Manual setup if you prefer:

```bash
python3 -m venv .venv                       # at the repo ROOT
.venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env        # optional OpenRouter key for hints
```

## Commands

The venv lives at the repo **root** (`../.venv` if you're in `backend/`).

```bash
# run the app (API + frontend, auto-reload). Default port 8000:
./run.sh                  # e.g. ./run.sh 9000 for another port

# backend tests — MUST run from backend/ with PYTHONPATH=. :
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q

# single test file or test:
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py
PYTHONPATH=. ../.venv/bin/pytest tests/test_runner.py::test_boss0_reference_passes_validator -q
```

Frontend smoke tests (node + jsdom, no browser):

```bash
cd frontend && npm test     # wraps: node --test "tests/*.test.js"
```

Then open http://127.0.0.1:8000.

## Architecture / layout

- `backend/app/` — FastAPI app (`main.py` wires everything). `hlr.py` (spaced repetition), `gating.py` (unlock chain), `store.py` (JSON persistence), `runner.py` (C compile/run), `llm.py` (OpenRouter), `content.py` (curriculum loader).
- `backend/content/` — `tree.json` = metadata for **all 8 worlds**; `worldN.json` = authored lessons. Only `world0.json` has real content (19 lessons + Boss 0); worlds 1–7 are placeholders.
- `frontend/` — ES-module SPA, no build. `index.html` → `app.js` → `views/{path,lesson,review}.js` + `api.js` + `views/dom.js`.
- `data/state.json` — learner state, generated at first run; gitignored, safe to delete to reset.