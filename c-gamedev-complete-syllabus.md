# Complete C Gamedev Syllabus + Gamified Learning App

Supersedes v1. Two parts: (1) full curriculum, gap-checked against real teaching research and real gamedev practice, (2) how to build the Duolingo-clone app around it, adaptive model included.

---

# PART 1 — TEACHING METHODOLOGY (why lessons structured this way)

Not arbitrary. Each mechanic below traces to research, not vibes.

1. **Worked example → guided practice → solo checkpoint.** Sweller & Cooper (1985): studying worked solutions before solving alone beats solving-from-scratch for new material. CS1 programming research confirms explicitly pairing worked examples with completion problems boosts engagement + success rate over presenting them separately. Every lesson below follows this 3-step shape, never skip step 1.

2. **Retrieval practice / testing effect.** Recalling something strengthens memory more than re-reading it. Bjork's "desirable difficulties" — make retrieval effortful, not painful. App quizzes previous units' concepts before introducing new ones (interleaving), not just tests current lesson.

3. **Spaced repetition via Half-Life Regression (HLR).** This is literally Duolingo's real algorithm (Settles & Meeder, ACL 2016, "A Trainable Spaced Repetition Model for Language Learning"). Core idea: each fact/skill has a memory "half-life" h — probability of recall at time Δt since last practice is `p = 2^(-Δt/h)`. Correct recall → h grows. Wrong recall → h shrinks, review sooner. Section 2 below gives exact formula to implement.

4. **Mastery gating, not time gating.** Duolingo's 2022 redesign — skill tree to linear path — was driven by data: beginners complete more when path is linear + gated by mastery, not free-roam. Adopt same: unit N+1 locked until checkpoint code of unit N runs correctly.

5. **Adaptive difficulty via performance signal, not guesswork.** Duolingo's system watches error rate + response pattern and adjusts next content. Own version: same idea, cheaper — LLM call classifies struggle pattern from wrong answers, picks next question difficulty.

Gap-check: this covers content structure (what/when), motivation loop (Part 4), and difficulty adaptation (Part 4). Nothing missing from a pedagogy angle.

---

# PART 2 — LIBRARY + TOOLING DECISIONS (with reasoning, no gaps)

| Need | Pick | Why |
|---|---|---|
| Windowing/input/3D rendering | **raylib** | plain C99, zero external deps, scales from beginner draw calls down to raw OpenGL via `rlgl.h` — never forces a library switch |
| Vector/matrix/quaternion math | **raymath.h** (ships inside raylib) | already there, matches raylib types |
| Heavier SIMD-optimized math (post-ECS scale) | **cglm** | drop-in when raymath's non-SIMD math becomes the bottleneck at thousands of entities |
| Entity Component System | build minimal one yourself first (Unit 13), then **flecs** | flecs is real production C99 ECS — cache-friendly archetype/SoA storage, handles millions of entities, powers Hytale's engine, has a raylib integration example in its repo. Not a toy, graduate to it, don't reinvent forever |
| Physics (beyond raylib's basic AABB/ray helpers) | **JoltC** (github.com/SecondHalfGames/JoltC) | real C wrapper around Jolt Physics (same engine used in Horizon Forbidden West). A raylib+Jolt hello-world project already exists as reference (rodneylab/jolt-raylib-hello-world) |
| Noise for terrain/procgen | **stb_perlin.h** | single header, Sean Barrett's stb library, zero setup |
| Save data / structured world state | **cJSON** or **sqlite3.c** (amalgamation) | cJSON for simple save files, sqlite3 once world state gets relational (factions, jobs, inventories) |

No library gap here — this stack takes you from "hello triangle" to physics-backed open world without a rewrite.

---

# PART 3 — FULL CURRICULUM

Structured as **Worlds → Units → Lessons**. Every unit ends in a **Boss** (integration checkpoint, must run correctly before next unit unlocks — mastery gate per Part 1 point 4). Every lesson internally follows worked-example → guided-practice → solo-checkpoint.

## WORLD 0 — Foundations (C + math + CS fundamentals, no graphics yet)

**Unit 0 — C for Data-Oriented Games**
- arrays-of-structs as entity storage
- function pointers for behavior dispatch
- tagged unions for entity/state variants
- arena allocators (bulk alloc/free, avoid malloc churn in a game loop)
- fixed-size strings, avoid heap churn per frame

**Unit 1 — Linear Algebra From Zero**
- vectors: add/sub/scale/dot/length/normalize
- cross product (face normals, camera right-vector)
- 4x4 matrices: what they do to a point; translation/scale/rotation
- matrix multiply order (model→view→projection chain)
- quaternions: why (gimbal lock), basic slerp
- trig for camera: yaw/pitch from mouse delta, spherical↔cartesian

**Unit 2 — Calculus & Physics Intuition**
- derivative = rate of change = velocity from position
- integral = accumulation = position from velocity
- Newton's laws in code terms: F=ma, acceleration from force/mass
- numerical integration: Euler (simple, unstable) vs Verlet (stable, cheap) vs RK4 (accurate, costly) — when to use which
- basic optics/lighting math: angle of incidence, Lambert's cosine law (used again in Unit 7)

**Unit 3 — Core Data Structures & Algorithms for Games**
- dynamic arrays, hash maps (for entity lookup by ID, spatial buckets)
- priority queues (needed for A* — Unit 16)
- graphs (nav meshes/grids are graphs)
- Big-O intuition — why O(n²) collision checks die at scale (sets up Unit 6's spatial partitioning)

**Boss 0:** command-line particle sim — N balls, gravity, wall bounce, printed positions each tick. Pure math + data structures, zero rendering. Swap Euler for Verlet integration, watch stability difference.

## WORLD 1 — Seeing (raylib + 3D basics)

**Unit 4 — raylib Fundamentals**
- window + game loop skeleton, `BeginDrawing/EndDrawing`
- input polling: keyboard, mouse delta, gamepad
- 2D warm-up: move a square with input, frame-rate-independent via `GetFrameTime()`
- asset loading discipline: load once, `UnloadTexture` on exit, no leaks

**Unit 5 — Into 3D**
- `Camera3D` types: free, orbital, first-person
- draw primitives (cube/sphere/plane), build test scene
- load models (GLTF/OBJ) via `LoadModel`/`DrawModel`
- basic lighting shader (directional + point light)
- materials/texturing

**Unit 6 — First-Person Controller**
- mouse-look: yaw/pitch accumulation, clamp pitch
- movement relative to yaw-only look direction
- collision: AABB-AABB, then capsule-vs-world for player body
- ground detection, gravity, jump, step-up for stairs

**Boss 1:** walk/run/jump a blockout level, collide with walls, no floor-clipping.

## WORLD 2 — Rendering Depth + World Scale

**Unit 7 — Shaders & Lighting Depth**
- GLSL basics: vertex vs fragment role, uniforms/varyings
- Lambert + Blinn-Phong lighting models (ties back to Unit 2 optics)
- shadow mapping: depth pass then sample in main pass
- skybox + distance fog (critical for open-world scale-feel)
- instancing: `DrawMeshInstanced` for thousands of identical meshes (grass, rocks) in one draw call

**Unit 8 — World at Scale**
- chunking: grid of cells, load/unload around player
- frustum culling — skip drawing what's off-camera
- LOD — swap mesh detail by distance
- spatial partitioning: uniform grid first, octree only if profiling says so
- streaming on a separate thread — avoid frame hitches on chunk load

**Boss 2:** foggy outdoor scene, 50+ streamed chunks, shadows, one instanced field of 500+ props, stable frame time.

## WORLD 3 — Systems & Optimization ("the black magic")

This is the world that turns "code that works" into "code that scales." Nothing here is optional if the open-world/many-NPC goal is real.

**Unit 9 — Data-Oriented Design**
- why OOP-style one-struct-per-object thrashes cache at scale
- Array-of-Structs (AoS) vs Struct-of-Arrays (SoA) — same data, different memory layout, very different cache behavior
- structure your hot-loop data by what's accessed together, not by "logical" object boundaries

**Unit 10 — Bit Tricks & Numeric Black Magic**
- bit flags for entity state (one uint32 instead of 8 bools)
- fast inverse square root — the actual Quake III trick: reinterpret float bits as int, `0x5f3759df - (i >> 1)` gives a first-guess exponent-halving via IEEE-754 bit layout, one Newton-Raphson step refines it. Historically attributed to Carmack, actually traces through 3dfx/SGI back to Greg Walsh at Ardent Computer in the 1980s. Modern CPUs have `rsqrtss` hardware instruction that beats it now — teach it for what it teaches about float bit layout, not because you should ship it today.
- fixed-point arithmetic — when floats are overkill or determinism across platforms matters (relevant later for deterministic world sim replay)
- lookup tables — precompute sin/cos/noise once, index instead of recompute

**Unit 11 — SIMD & Branchless Programming**
- SSE/AVX intrinsics basics — process 4-8 floats per instruction instead of 1
- branch misprediction cost — why `if` in a hot loop can be slower than branchless min/max/select
- when to reach for this: profile first, this is a scalpel not a default

**Unit 12 — Custom Memory Management**
- arena/pool allocators for per-frame or per-entity-type allocation
- why `malloc`/`free` in a hot loop is a fragmentation + latency problem
- object pools for frequently spawned/destroyed things (bullets, particles, pathfinding nodes)

**Boss 3:** take Boss 0's particle sim, push to 100k particles at 60fps using SoA layout + arena allocation + (optionally) SIMD. Profile before and after, keep the numbers — this is the proof the black magic isn't cargo-culting.

## WORLD 4 — Entities & Brains (ECS + AI)

**Unit 13 — ECS Architecture**
- why polymorphism-in-C doesn't scale to thousands of NPCs
- entity = ID, components = plain data arrays, systems = functions over arrays
- build a minimal ECS yourself (sparse set or parallel arrays) — small, understand every line
- migrate to **flecs** once your hand-rolled version's limits are felt firsthand — better to feel the pain before reaching for the tool that removes it

**Unit 14 — FSM & Behavior Trees**
- finite state machines: Idle/Work/Eat/Sleep/Flee
- behavior trees: composable decision nodes, avoids deep FSM nesting hell

**Unit 15 — Utility AI**
- needs-based decisions: hunger/energy/social meters drive action choice, not scripted paths
- scheduling: daily routines, job assignment

**Unit 16 — GOAP + Pathfinding**
- Goal-Oriented Action Planning: goals + actions with preconditions/effects → emergent plans instead of hand-scripted behavior chains
- A* on a nav grid, path smoothing (ties back to Unit 3's priority queue + graph)

**Boss 4:** 20 NPCs, hunger/energy meters, autonomously path to food/bed when meter low, obstacle avoidance, using flecs.

## WORLD 5 — The Living World (Dwarf-Fortress-style simulation)

Dwarf Fortress's actual trick, confirmed by how it's built: it generates a world-scale map then simulates up to 1,000 years of history — wars, successions, migrations — before the player even starts, all from systemic rules acting on agents, not hand-authored scripts. The "living" feeling comes from simulation depth and event-driven state, not from smarter individual NPC AI. Build toward that specifically.

**Unit 17 — Simulation Tick vs Render Tick**
- decouple world simulation update rate from render frame rate
- **simulation LOD**: full-detail AI near the player, coarse/statistical simulation for anything far away — do not run full behavior trees on 10,000 offscreen NPCs, aggregate them (e.g. "village population trends up/down based on food surplus") until player gets close, then "unfold" into individuals

**Unit 18 — Event-Driven World State**
- decoupled event bus: NPC dies → notifies job system, economy, relations, without those systems polling each other
- simple economy loop: resources produced/consumed/traded
- factions with simple relationship state (ties to Unit 14's FSM for faction-level behavior)

**Unit 19 — Persistence**
- serialize entity + world state to disk (cJSON or custom binary)
- versioned save format — you will change your structs later, plan for it now

**Boss 5:** leave an area for in-game "days," come back, world changed believably (crops grew, an NPC changed job, a resource depleted) without the game having fully simulated it on-screen the entire time.

## WORLD 6 — Procedural Worlds

**Unit 20 — Noise-Based Terrain**
- Perlin/Simplex noise fundamentals — smooth, correlated randomness vs white noise
- octave layering (fractal noise) — big shapes from low frequency, detail from high frequency
- heightmap → mesh, normal calculation for lighting

**Unit 21 — Cellular Automata & Space Partitioning Generation**
- cellular automata for caves (repeatedly apply neighbor-count rules to carve organic cave shapes)
- BSP (binary space partitioning) for structured dungeon/building layouts

**Unit 22 — Wave Function Collapse**
- constraint-based tile generation: each tile type defines valid neighbors, algorithm "collapses" possibilities cell by cell until a locally-consistent layout emerges
- good fit for towns, road networks, structured layouts that need to look designed, not random

**Unit 23 — L-Systems**
- grammar-based recursive generation, originally for plant growth modeling
- generate trees/vegetation from a handful of rewrite rules instead of hand-modeling every plant

**Boss 6:** seeded, fully generated explorable region — terrain + biomes (Unit 20) + cave system (Unit 21) + one WFC-generated settlement (Unit 22) + L-system vegetation (Unit 23). Same seed always reproduces the same world — determinism matters, log seeds.

## WORLD 7 — Interaction, Physics, Polish

**Unit 24 — Interaction Systems**
- raycasting for object picking + AI line-of-sight
- trigger volumes (enter/exit events)
- inventory + item data tables

**Unit 25 — Physics**
- integrate JoltC for real rigidbody physics beyond raylib's basic collision helpers
- interactable physical objects (pick up, throw, physically simulated)

**Unit 26 — Tooling & Polish**
- in-game debug console (spawn entities, teleport, toggle debug draws)
- profiling — find real bottlenecks, don't guess (ties directly back to World 3 — optimize what profiling says, not what feels slow)
- debug draw layer: AABBs, nav paths, AI state labels
- audio + UI pass

**Boss 7 — CAPSTONE:** combine everything. Streamed open world (World 2), FPS controller (World 1), 30+ NPCs with needs/schedules/pathfinding (World 4), world sim ticking independent of render with simulation LOD (World 5), one small economy loop, procedurally generated starting region (World 6), save/load, basic physics interaction, audio+UI polish. This is the "living open world" proof — small in scope, real in every mechanic. Scale map size / NPC count after this works, never before.

---

# PART 4 — PACING

At 15+ hrs/week:

| World | Weeks |
|---|---|
| 0 — Foundations | 3 |
| 1 — Seeing | 2 |
| 2 — Rendering Depth + Scale | 2 |
| 3 — Systems & Optimization | 3 |
| 4 — Entities & Brains | 3 |
| 5 — Living World | 3 |
| 6 — Procedural Worlds | 3 |
| 7 — Interaction/Physics/Polish + Capstone | 3 |

~22 weeks to a real vertical slice. Longer than v1's estimate — v1 skipped World 3 (optimization) and shortchanged World 5/6 depth. This version has no skipped systems.

---

# PART 5 — BUILDING THE GAMIFIED LEARNING APP

## Architecture

Keep the app itself dead simple — you're learning C, not web dev, don't let the tool become the second project. Recommended: single local web app, vanilla HTML/CSS/JS frontend + a thin backend (Python/FastAPI or even a static site with a small serverless function) only to hide your OpenRouter API key. Store progress in a local JSON file or SQLite — no need for a real database at solo-user scale.

Data model (minimum):
- `units[]` — id, title, prerequisite unit ids, checkpoint definition
- `lessons[]` — id, unit id, content, worked example, practice prompt
- `skill_state{}` — per skill/lesson: half-life `h`, last-practiced timestamp, correct/incorrect history
- `xp`, `streak`, `last_active_date`

## Adaptive Spaced Repetition (real formula, not vibes)

Simplified Half-Life Regression, implementable without training a model yourself:

```
p_recall = 2 ^ (-delta_t / h)

on correct answer:  h = h * growth_factor      (growth_factor ~1.3–2.0, tune it)
on wrong answer:     h = max(h * shrink_factor, h_min)   (shrink_factor ~0.3–0.5)

next_review_time = now + h * ln(2)   // time until p_recall drops to 0.5
```

Start every new skill at a small `h` (e.g. 1 day). Schedule daily review queue: any skill whose `p_recall` (given current time since last practice) has dropped below a threshold (e.g. 0.85) gets queued for review before new content unlocks. This is literally the mechanism Duolingo ships in production, scaled down to single-user local state.

## Mastery Gating

Unit N+1 stays locked until:
1. All lesson checkpoints in Unit N pass (code compiles + runs + produces expected output — write small test harnesses per checkpoint)
2. Review queue for Unit N's concepts is empty (per HLR schedule above)

## Adaptive Difficulty via LLM (OpenRouter)

Use case: when a checkpoint fails or a quiz answer is wrong, send the wrong answer + concept + skill_state to the model, get back either a Socratic hint (don't give the answer directly) or an adjusted-difficulty follow-up question.

**Model note:** you mentioned a MiniMax free model — as of now the free MiniMax variant on OpenRouter is `minimax/minimax-m2.7:free` (id changes as MiniMax ships new versions; OpenRouter's free lineup also rotates entirely with little notice). Don't hardcode a model id and forget it — query OpenRouter's model list at app startup, filter for `pricing.prompt == "0"`, fall back to a hardcoded list if that call fails. Free tier limits as of now: 20 requests/minute, 50 requests/day with no credit purchase ever made, 1000/day after a one-time $10 credit purchase (credits don't need to be spent, just present). Build in graceful backoff for 429s — a personal learning app hitting a free tier will hit limits.

```javascript
// fetch current free models, pick one
async function pickFreeModel() {
  const res = await fetch('https://openrouter.ai/api/v1/models');
  const { data } = await res.json();
  const free = data.filter(m => m.pricing?.prompt === "0" && m.id.includes('minimax'));
  return free[0]?.id ?? 'minimax/minimax-m2.7:free'; // fallback
}

async function getAdaptiveHint(concept, wrongAnswer, skillState) {
  const model = await pickFreeModel();
  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: 'system', content: 'You are a Socratic C/gamedev tutor. Never give the direct answer. Ask a guiding question that leads the learner toward the fix.' },
        { role: 'user', content: `Concept: ${concept}\nLearner's wrong attempt: ${wrongAnswer}\nCurrent mastery half-life: ${skillState.h} days.` }
      ]
    })
  });
  const data = await res.json();
  return data.choices[0].message.content;
}
```

Same call pattern, different system prompt, for: generating a harder/easier follow-up question, or reviewing a checkpoint's C code style before marking it passed.

## Gamification Mechanics (backed by Part 1's research, not decoration)

- **XP per lesson**, bonus XP for first-try-correct (variable reward, per the psychology research — unpredictable bonus keeps engagement higher than flat reward)
- **Streak counter** — Duolingo's own data: 7-day-streak users are markedly more likely to keep going. Loss aversion is doing real work here, use it.
- **Crown/mastery level per unit** — visual progress made concrete (Part 1, point 4)
- **Boss battle framing** for each World's capstone checkpoint — makes the mastery-gate feel like an event, not a chore
- Skip leaderboards/leagues — meaningless at n=1 user, don't build social features nobody's using

---

# PART 6 — WHAT COULD STILL BE MISSING (checked, and why it's excluded on purpose)

- **Multiplayer/networking** — deliberately excluded from the core tree. Bolt-on after Capstone if wanted, separate skill tree entirely — mixing it in earlier multiplies debugging surface for no payoff toward the stated single-player open-world goal.
- **Audio DSP / advanced sound synthesis** — raylib's audio module (WAV/OGG/MP3/FLAC/XM/MOD playback) is enough for this scope; real signal processing (FFT, custom synthesis) is its own deep field, only pull it in if the game specifically needs procedural audio.
- **Vulkan** — raylib's OpenGL backend is enough through this entire curriculum, including the open-world scale unit. Vulkan is a real skill but a distraction from the stated goal; mention it exists as the next step after this whole tree is done, not before.
- **GPU compute for simulation (compute shaders driving NPC logic)** — genuinely advanced, genuinely relevant to "thousands of living NPCs," but only after Worlds 3–5 are solid on CPU first. Flagged here so it's not a surprise gap — it's the natural World 8 if you want to keep going past Capstone.

Everything else needed for the stated goal — FPS-style open world, DF-like dynamic living NPCs/world, taught with depth and real tools — is in Worlds 0–7 above.
