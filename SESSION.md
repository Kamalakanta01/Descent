# SESSION.md — Descent handoff state

Snapshot for continuing work on a fresh machine/session. The app: local single-user
C-gamedev learning app. FastAPI backend + vanilla-JS SPA, real `gcc` checkpoints,
HLR spaced repetition, OpenRouter hints (keyless w/ static fallback).
Authoritative docs: `AGENTS.md`, `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`.

## Commands (run from `backend/`; venv is at repo ROOT `../.venv`)

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q          # 42/42 passing as of handoff
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Fresh machine setup: `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.


## Decisions baked in at handoff

- **HTTP errors**: `main.py` now raises `HTTPException(404/400)` (was Flask-style
  `return {...}, 404` — a silent no-op returning 200 + array body; fixed all 5 sites).
  Covered by `tests/test_api.py` (TestClient).
- **Review-gate REMOVED** (user-approved): unit unlock depends ONLY on
  checkpoints passed (`gating.py::refresh_unlocks`). Reviews are a separate
  reinforcement track; a due review never re-locks the path.
- **Sanitizers ON** in `runner.py`: `-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g`.
  Consequences: compile is slower; ASan needs ~15TB *virtual* VA so **RLIMIT_AS is removed**
  (CPU timeout + FSIZE limits + ASan's own allocator remain as backstops).
- **XP_REVIEW now real**: practice answer = +5 XP, but if the lesson's checkpoint was
  already passed it counts as review (+3), per spec. Detection is server-side
  (`cp["id"] in state["passed"]`).
- **Boss 0 is a spring sim** (was gravity-bounce; old sim passed under explicit
  Euler so the "energy leak" promise never fired — FIXED). Balls are tethered to
  box centre (50,50) by Hooke springs, stiffness per ball `K = {40,30,35}`,
  `dt = 0.01`, 200 ticks x 3 balls = 600 lines of `T <tick> <id> <x> <y>`.
  Discriminator = **turning-point radius growth**: later radius local maxima must
  exceed the first by <= 0.5. Explicit Euler starter leaks (~5.2 max growth, FAILS);
  velocity Verlet (kick-drift-kick) has ~0 drift (PASSES). Caveat: semi-implicit
  Euler (symplectic) also passes — by design, any energy-stable scheme does.
  Verified: `test_boss0_euler_starter_fails_energy_check`, `test_boss0_reference_passes_validator`.
- **Placeholder worlds render** (was unstyled empty cards): `_curriculum_view`
  keeps `unit_state: "empty"` for content-less units instead of forcing "locked";
  `path.js` now has a `.unit-card.empty` branch ("coming soon" + spark icon) and
  `.unit-empty` CSS. Worlds 1–7 all render as coming-soon cards.
- **Syllabus gap fixes**: added `w0u1l6 "Quaternions: Rotations Without Gimbal Lock"`
  (slerp function checkpoint, verified passable under ASan/UBSan) and a
  `P·V·M` chain coda + practice Q in `w0u1l4` — closes the two hard gaps from the
  syllabus audit. `llm.py` now sleeps 5s on 429/529 rate-limit statuses vs 0.5s on
  other failures (`test_chat_backs_off_short_on_generic_failure`).
- Next audit follow-up: Boss 3 (syllabus line 143) references Boss 0's sim — now
  spring-based; update the cross-ref when authoring world 3.

## Deferred backlog (top first)

### 1. Author world 1 ("Seeing") so the unlock chain advances past the stall
`gating.refresh_unlocks` breaks on the first content-less unit by design, so the
path currently dead-ends after world 0. Authoring `backend/content/world1.json`
(raylib Fundamentals, Into 3D, First-Person Controller, Boss 1) is the next real
content milestone. Placeholder cards already communicate the stall gracefully.

### 2. Optional polish
- Boss 0 works, but only world 0 is playable — consider a "content roadmap" modal
  on the path page so the coming-soon units set expectations.
- `frontend/` has no automated tests; a smoke test that renders `renderPath`
  against a stubbed `api.js` would de-risk future `path.js`/`dom.js` changes.

## Gotchas (verify against AGENTS.md — it may be stale after the review-gate change)

- Tests MUST run from `backend/` with `PYTHONPATH=.` (imports `app.*`).
- `frontend/highlight.js` was deleted — `highlightC` lives in `frontend/views/dom.js`.
- `get_skill`/`record_result` in `store.py`; HLR idle.
- `backend/.env` (OpenRouter key) and `data/state.json` are gitignored;
  include them in any zip if you want key + progress carried over.
- `views/*.js` `refreshHud` circular import from `../app.js` — keep it exported.