# SESSION.md — Descent handoff state

Snapshot for continuing work on a fresh machine/session. The app: local single-user
C-gamedev learning app. FastAPI backend + vanilla-JS SPA, real `gcc` checkpoints,
HLR spaced repetition, OpenRouter hints (keyless w/ static fallback).
Authoritative docs: `AGENTS.md`, `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`.

## Commands (run from `backend/`; venv is at repo ROOT `../.venv`)

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q          # 40/40 passing as of handoff
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```


## Decisions baked in at handoff

- **HTTP errors**: `main.py` now raises `HTTPException(404/400)` (was Flask-style
  `return {...}, 404` — a silent no-op returning 200 + array body; fixed all 5 sites).
  Covered by `tests/test_api.py` (TestClient).
- **Review-gate REMOVED** (user-approved): unit unlock depends ONLY on
  checkpoints passed (`gating.py::refresh_unlocks`). Fixing the same thing in `main.py`.
  Opposite of what old `AGENTS.md` said in the spec docstring — the docstring + tests were updated.
- **Sanitizers ON** in `runner.py`: `-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g`.
  Consequences: compile is slower; ASan needs ~15TB *virtual* VA so **RLIMIT_AS is removed**
  (CPU timeout + FSIZE limits + ASan's own allocator remain as backstops).
- **XP_REVIEW now real**: practice answer = +5 XP, but if the lesson's checkpoint was
  already passed it counts as review (+3), per spec. Detection is server-side
  (`cp["id"] in state["passed"]`).
- **Boss 0 passes with the Euler starter** — this is DEFERRED backlog, NOT fixed
  (see below). `world0.json` boss + `runner.validator("boss0")` still use the
  gravity-bounce sim whose default starter (explicit Euler) passes all checks.

## Deferred backlog (top first)

### 1. Boss 0 must NOT pass with the Euler starter (highest priority)
Root cause: constant-gravity bounce physics is energy-stable under any first-order
integrator (verified by simulation), so the "energy leak" check can't fire; the
authored Euler starter legitimately passes. The lesson text promises "Euler leaks
energy, balls escape" — physics never delivers it.

Validated fix (simulated, constants tuned) — **spring/central-force sim**:
- Physics: balls tethered to box-center by springs `F = -k·r`; output stays
  `T <tick> <id> <x> <y>`, 200 ticks × 3 balls = 600 lines.
- Discriminator: velocity Verlet has 0 energy drift; explicit Euler pumps energy.
  Use a **turning-point radius growth** check (radius local maxima: later maxima
  must not exceed the first by > ~0.5), NOT a position-difference velocity energy
  check (that's an unreliable noise floor). Leave bounds/movement/determinism checks.
- Constants that discriminate in 200 ticks: `K=[40,30,35]`, balls
  `(65,50,8,0),(50,62,0,8),(40,50,7,5)` gives Euler turn-growth ~5.2 vs Verlet 0.0.
  (Milder: `K=[25,20,30]` → 2.68 vs 0.0.)
- Update `world0.json` boss lesson (theory/example/practice/hints), `runner.vvalidate_boss0`,
  and the `BOSS0_REFERENCE` in `tests/test_runner.py` to velocity Verlet.

### 2. Placeholder worlds (worlds 1–7) render as unstyled empty cards
`_curriculum_view` emits `unit_state: "empty"` for content-less unlocked units;
`path.js` has no `.unit-card.empty` branch and its lock-overlay requires
`lessons.length`. Add an "empty / coming soon" card branch + CSS (icon + copy).

### 3. Polish
`backend/.env.example` with `OPENROUTER_API_KEY=`; copy the Commands block from
`AGENTS.md` into `README.md` (currently one line).

## Gotchas (verify against AGENTS.md — it may be stale after the review-gate change)

- Tests MUST run from `backend/` with `PYTHONPATH=.` (imports `app.*`).
- `frontend/highlight.js` was deleted — `highlightC` lives in `frontend/views/dom.js`.
- `get_skill`/`record_result` in `store.py`; HLR idle.
- `backend/.env` (OpenRouter key) and `data/state.json` are gitignored;
  include them in any zip if you want key + progress carried over.
- `views/*.js` `refreshHud` circular import from `../app.js` — keep it exported.