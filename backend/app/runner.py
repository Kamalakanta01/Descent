"""Compile-and-run learner C code against per-checkpoint harnesses.

Single-user local app: the sandbox is a fresh temp dir + wall-clock timeout +
POSIX rlimits, not a security boundary. Two checkpoint kinds:

- "function": harness.c (from content) does `#include "learner.c"` — the
  learner supplies functions, the harness asserts behaviour, exit 0 == pass.
- "program": learner ships a whole program (main); we run it twice and apply a
  named validator (see VALIDATORS) to the stdout — used by Boss checkpoints.
"""

from __future__ import annotations

import math
import os
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

COMPILE_TIMEOUT_S = 30
RUN_TIMEOUT_S = 6
RLIMIT_CPU_S = 5
# No RLIMIT_AS: ASan reserves ~15 TB of *virtual* address space for shadow
# memory, which trips any hard RLIMIT -v. Physical OOM is prevented because
# ASan tracks allocations itself (aborts on failure), and the CPU timeout is
# the real backstop for runaway learner programs.
# Also no RLIMIT_NPROC: it counts the UID's *total* processes (which on this
# machine is already in the hundreds), and LeakSanitizer forks a helper at
# exit — any limit tight enough to matter makes every sanctioned binary abort
# at cleanup. Fork-bomb containment is the process-group kill in _run().
RLIMIT_FSIZE_BYTES = 2 * 1024 * 1024

GCC = shutil.which("gcc") or "gcc"


def _apply_limits() -> None:  # runs in the child process (POSIX only)
    resource.setrlimit(resource.RLIMIT_CPU, (RLIMIT_CPU_S, RLIMIT_CPU_S))
    resource.setrlimit(resource.RLIMIT_FSIZE, (RLIMIT_FSIZE_BYTES, RLIMIT_FSIZE_BYTES))


def _sanitize_compiler_output(stderr: str, workdir: Path) -> str:
    return stderr.replace(str(workdir) + os.sep, "").strip()


def _compile(workdir: Path, sources: list[str]) -> tuple[str | None, str]:
    """Returns (errors, warnings); errors None on success. stderr is never
    discarded: with -Wall -Wextra on, warnings from a *successful* compile are
    pedagogically valuable (uninitialized vars, sign mismatches...)."""
    cmd = [
        GCC, "-std=c11", "-Wall", "-Wextra", "-O1", "-g",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        *sources, "-o", "prog", "-lm",
    ]
    proc = subprocess.run(
        cmd, cwd=workdir, capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S
    )
    out = _sanitize_compiler_output(proc.stderr, workdir)
    if proc.returncode != 0:
        return (out or "compilation failed"), ""
    return None, out


def _run(workdir: Path) -> dict:
    """Returns {ok, stdout, stderr, exit_code, timed_out}. Kills the whole
    process group on timeout — a stray fork(fork()) in learner code must not
    outlive the harness around it."""
    import signal

    start = time.monotonic()
    proc = subprocess.Popen(
        ["./prog"],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=_apply_limits if os.name == "posix" else None,
        start_new_session=os.name == "posix",
    )
    try:
        out, err = proc.communicate(timeout=RUN_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.communicate()
        return {"ok": False, "stdout": "", "stderr": "", "exit_code": None, "timed_out": True}
    elapsed = time.monotonic() - start
    signal_kill = proc.returncode is not None and proc.returncode < 0
    # A run approaching the wall clock counts as timed out even on clean exit
    # (the 0.1s margin covers communicate()'s own return latency); solutions
    # this slow are pathological whatever the exit code says.
    return {
        "ok": True,
        "stdout": out,
        "stderr": err,
        "exit_code": proc.returncode,
        "timed_out": signal_kill or elapsed >= RUN_TIMEOUT_S - 0.1,
    }


def validate_boss0(stdout: str) -> list[dict]:
    """Boss 0 — CLI particle sim (spring-tethered balls).

    Expected output: for tick t in 0..199, ball ids 0..2:
        T <tick> <id> <x> <y>
    Physics: each ball is tethered to the box centre (50, 50) by a Hooke
    spring F = -k·r with per-ball stiffness k in {40, 30, 35}, dt = 0.01.
    Checks: exact line shape/order, finite numbers, balls inside the box,
    balls actually move, and turning-point radius stability — later outward
    excursions (radius local maxima) must not exceed the first by more than
    0.5. Explicit Euler pumps energy into an oscillator so the amplitude
    grows every period; velocity Verlet is symplectic and the amplitude holds.
    """
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    CX = CY = 50.0
    W = H = 100.0
    lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    add("line_count", len(lines) == 600, f"got {len(lines)} lines, expected 600")

    positions: dict[int, list[tuple[int, float, float]]] = {0: [], 1: [], 2: []}
    parse_ok = True
    order_ok = True
    for idx, ln in enumerate(lines):
        parts = ln.split()
        ok = (
            len(parts) == 5
            and parts[0] == "T"
            and parts[1].lstrip("-").isdigit()
            and parts[2].lstrip("-").isdigit()
        )
        if not ok:
            parse_ok = False
            continue
        t, bid = int(parts[1]), int(parts[2])
        if t != idx // 3 or bid != idx % 3 or bid not in positions:
            order_ok = False
        try:
            x, y = float(parts[3]), float(parts[4])
        except ValueError:
            parse_ok = False
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            parse_ok = False
            continue
        positions.setdefault(bid, []).append((t, x, y))

    add("format", parse_ok, "every line must be: T <tick> <id> <x> <y>")
    add("order", order_ok, "lines must follow tick 0..199, ids 0,1,2 per tick")
    if not parse_ok:
        add("bounds", False, "could not parse output")
        add("movement", False, "could not parse output")
        add("energy", False, "could not parse output")
        return checks

    bounds_ok = True
    moved_ok = True
    for bid, traj in positions.items():
        for _, x, y in traj:
            if not (-1e-3 <= x <= W + 1e-3 and -1e-3 <= y <= H + 1e-3):
                bounds_ok = False
                break
        xs = [x for _, x, _ in traj]
        ys = [y for _, _, y in traj]
        if (max(xs) - min(xs)) + (max(ys) - min(ys)) < 1.0:
            moved_ok = False
    add("bounds", bounds_ok, "every ball must stay inside [0, 100] x [0, 100]")
    add("movement", moved_ok, "balls must actually move")

    # Turning-point radius stability: per ball, r(t) = distance to centre.
    # A correct (symplectic) integrator conserves energy, so later outward
    # excursions match the first within rounding noise. Explicit Euler pumps
    # energy into the spring and the amplitude grows by several units.
    # (Recovering velocity from successive positions is too noisy near a
    # turning point; radius maxima are a robust proxy for amplitude.)
    energy_ok = True
    for bid, traj in positions.items():
        if len(traj) < 3:
            energy_ok = False
            continue
        radii = [math.hypot(x - CX, y - CY) for _, x, y in traj]
        maxima = [
            radii[i] for i in range(1, len(radii) - 1)
            if radii[i] >= radii[i - 1] and radii[i] >= radii[i + 1]
        ]
        if len(maxima) < 2:
            continue  # not enough turning points to judge amplitude
        first = maxima[0]
        if any(m > first + 0.5 for m in maxima[1:]):
            energy_ok = False
            break

    add(
        "energy",
        energy_ok,
        "amplitude must not grow between turning points (Euler leaks energy; use Verlet)",
    )
    return checks


VALIDATORS = {"boss0": validate_boss0}


def compile_and_run(checkpoint: dict, learner_code: str) -> dict:
    """Compile learner code and evaluate the checkpoint. Returns a result dict."""
    kind = checkpoint.get("kind", "function")
    workdir = Path(tempfile.mkdtemp(prefix="descent_run_"))
    try:
        (workdir / "learner.c").write_text(learner_code, encoding="utf-8")
        if kind == "function":
            (workdir / "harness.c").write_text(checkpoint["harness"], encoding="utf-8")
            errors, warnings = _compile(workdir, ["harness.c"])
        else:
            errors, warnings = _compile(workdir, ["learner.c"])
        if errors is not None:
            return {
                "compiled": False,
                "passed": False,
                "errors": errors,
                "warnings": "",
                "stdout": "",
                "timed_out": False,
                "checks": [],
            }

        run = _run(workdir)
        if run["timed_out"]:
            return {
                "compiled": True,
                "passed": False,
                "errors": "time limit exceeded (infinite loop or very slow code?)",
                "warnings": warnings,
                "stdout": run["stdout"],
                "timed_out": True,
                "checks": [],
            }

        if kind == "function":
            passed = run["exit_code"] == 0
            return {
                "compiled": True,
                "passed": passed,
                "errors": "" if passed else "one or more tests failed",
                "warnings": warnings,
                "stdout": run["stdout"],
                "timed_out": False,
                "checks": [],
                "runtime_stderr": run["stderr"],
                "exit_code": run["exit_code"],
            }

        validator = VALIDATORS[checkpoint["validator"]]
        second = _run(workdir)
        checks = validator(run["stdout"])
        checks.insert(
            0,
            {
                "name": "deterministic",
                "ok": second["ok"] and not second["timed_out"] and run["stdout"] == second["stdout"],
                "detail": "two runs must produce byte-identical output (log your seed!)",
            },
        )
        passed = all(c["ok"] for c in checks) and run["exit_code"] == 0
        return {
            "compiled": True,
            "passed": passed,
            "errors": "",
            "warnings": warnings,
            "stdout": run["stdout"],
            "timed_out": False,
            "checks": checks,
            "runtime_stderr": run["stderr"],
            "exit_code": run["exit_code"],
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
