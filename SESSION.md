# SESSION.md — Descent handoff state

Snapshot for continuing work on a fresh machine/session. The app: local single-user
C-gamedev learning app. FastAPI backend + vanilla-JS SPA, real `gcc` checkpoints,
HLR spaced repetition, OpenRouter hints (keyless w/ static fallback).
Authoritative docs: `AGENTS.md`, `docs/superpowers/specs/2026-09-05-descent-learning-app-design.md`.

## Commands (run from `backend/`; venv is at repo ROOT `../.venv`)

```bash
cd backend
PYTHONPATH=. ../.venv/bin/pytest tests -q          # 53/53 passing as of handoff
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# frontend smoke tests (node + jsdom, no build step):
npm test                                        # from frontend/
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

### 2026-09-06 batch (systematic audit fixes — all tested)

- **`store.update(fn)`** (thread-safe read→mutate→write under one lock) backs all
  score-and-persist paths in `main.py`; `runner.compile_and_run` runs outside the
  lock (it is the slow part).
- **`runner.py`: warnings are now surfaced** — `_compile` returns `(errors, warnings)`,
  stderr is never discarded. Learners see `-Wall -Wextra` notes (sign mismatches,
  uninitialized vars) rendered as `.console-warn`.
- **Timeout containment = process-group kill** (`start_new_session` + `os.killpg`).
  The audit's naive RLIMIT_NPROC "fix" was tried and REJECTED with a comment: it
  caps the UID's *total* processes and makes LeakSanitizer's exit fork fail every
  sanctioned binary. RLIMIT_CPU 5 s + RLIMIT_FSIZE 2 MB + 6 s wall are the limits.
- **Practice answers redistributed**: every lesson's first practice question had
  the correct answer at index 0 (and `-1` used one elsewhere). All 41 answers
  re-spread to a 14/14/13 counter; client shuffles choices with session-stable
  shuffle keys (`shuffleStable`) so order is fixed per question per session.
  Invariant test `test_practice_answers_are_distributed_across_positions` guards it.
- **Shuffle-key collision bug (caught by the jsdom suite)**: the inline warm-up
  reused the lesson's own practice shuffle key (`w0u0l1:p0`), so a 2-choice
  warm-up pinned a permutation that truncated the lesson's 3-choice question.
  Warm-up keys are namespaced `warmup:`/`w:`; lesson practice stays `{id}:p{n}`
  so review page and lesson page pin the same order.
- **`w0u2l3` rewritten around velocity Verlet** (kick-drift-kick) — the scheme
  Boss 0's turning-point energy check requires. Gravity closed-form harness
  (x = 100 + ½a·t², v = a·t), verified `passed: True`. The old "Euler vs RK4"
  framing implied RK4 was the answer; RK4 is damping-free but this lesson now
  teaches the interpolator that actually matters here.
- **LLM review questions**: `REVIEW_SYSTEM` + lesson theory → a fresh MCQ per
  lesson per UTC day (cached, even negative), 2-generated-per-queue-load budget,
  answers held server-side in a one-shot token registry (`FOLLOWUPS`, popped on
  answer). Endpoint `POST /api/followup/answer`. Keyless LLM → falls back to
  authored practice silently.
- **Re-pass checkpoint XP is gated**: `post_run` pays XP_REVIEW on a re-pass only
  when the skill is actually due (`hlr.is_due`) — otherwise 0. No more farming a
  passed checkpoint for XP.
- **Frontend jsdom suite added** — `frontend/tests/{dom,app}.test.js` under
  `node --test` (10 tests). Big gotchas captured for later sessions:
  (1) `app.js` only *registers* a DOMContentLoaded listener, jsdom never fires it
  — tests must `document.dispatchEvent(new window.Event('DOMContentLoaded'))`;
  (2) views are imported directly for page tests (unique query strings like
  `?lv_a` give fresh module instances since apps cache module-scope refs);
  (3) jsdom needs `window.scrollTo` + `Element.prototype.scrollIntoView` stubbed.
- **Compile errors no longer decay the skill** (follow-up batch, all tested):
  `record_result(False)` runs only when `res["compiled"]` is True — a syntax typo
  no longer shrinks the half-life; runtime/test failures and timeouts still decay.
  Guarded by `test_compile_error_does_not_decay_skill`. Practiced the skill
  memory; code attempts are a separate track.
- **Sanitizer output is now visible**: `lesson.js` renders `runtime_stderr`
  (ASan/UBSan crash dumps) under a `runtime:` console line; the frontend suite
  asserts it (`runtime_stderr` mocked on a failed run). Raw pages: crash output
  was silent before — learners saw only "Tests failed".
- **`POST /api/answer` validates the choice index** — out-of-range or negative
  choice is a 400 (`IndexError` crash fixed; `test_answer_out_of_range_choice_is_400`).
- **Dead CSS hooks removed** — `.review-page` / `.review-card` had no rules and
  were dropped from `review.js`; the review test now selects `.panel`.
- **Review "Re-run checkpoint" fixed honestly** — the button used to POST the
  blank `starter_code`, so it failed for everyone every time (its mock only
  asserted the POST fired). Now:
  - Checkpoint editor extracted to `frontend/views/editor.js` (`checkpointEditor`)
    shared by lesson + review pages (gutter, Tab→4-space, Run, Hint, result box).
  - Review card's "Re-attempt from memory" expands the editor pre-filled with
    the blank starter — genuine retrieval practice, and pass/fail drives HLR
    normally. (Replays of a persisted solution were rejected: a deterministic
    pass would falsely grow `h_days` on a forgotten skill.)
  - The **last-passing submission persists** (`state.solutions`, set in
    `/api/checkpoint/run` on pass, shown via `has_solution` flags + new
    `GET /api/lesson/{id}/solution`). "Show old solution" → `revealed: true`
    run, which is graded but **scores nothing** (no XP, no HLR update) — the
    reveal is visible but silent in the signal. Guarded by
    `test_revealed_run_scores_nothing` + jsdom reveal test.

## Deferred backlog (top first)

### 1. Author world 1 ("Seeing") so the unlock chain advances past the stall
`gating.refresh_unlocks` breaks on the first content-less unit by design, so the
path currently dead-ends after world 0. Authoring `backend/content/world1.json`
(raylib Fundamentals, Into 3D, First-Person Controller, Boss 1) is the next real
content milestone. Placeholder cards already communicate the stall gracefully.

### 2. Optional polish
- Boss 0 works, but only world 0 is playable — consider a "content roadmap" modal
  on the path page so the coming-soon units set expectations.
- "Unit -1": a syntax-on-ramp world (or unit) teaching C syntax for absolute C
  beginners before world 0. **Pending owner decision** — don't author unilaterally.
- Boss 3 cross-ref (see Decisions above) when world 3 is authored.

## Gotchas (verify against AGENTS.md — it may be stale after the review-gate change)

- Tests MUST run from `backend/` with `PYTHONPATH=.` (imports `app.*`).
- `frontend/highlight.js` was deleted — `highlightC` lives in `frontend/views/dom.js`.
- `get_skill`/`record_result` in `store.py`; HLR idle.
- `backend/.env` (OpenRouter key) and `data/state.json` are gitignored;
  include them in any zip if you want key + progress carried over.
- `views/*.js` `refreshHud` circular import from `../app.js` — keep it exported.