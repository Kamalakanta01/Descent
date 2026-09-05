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
RLIMIT_FSIZE_BYTES = 2 * 1024 * 1024

GCC = shutil.which("gcc") or "gcc"


def _apply_limits() -> None:  # runs in the child process (POSIX only)
    resource.setrlimit(resource.RLIMIT_CPU, (RLIMIT_CPU_S, RLIMIT_CPU_S))
    resource.setrlimit(resource.RLIMIT_FSIZE, (RLIMIT_FSIZE_BYTES, RLIMIT_FSIZE_BYTES))


def _sanitize_compiler_output(stderr: str, workdir: Path) -> str:
    return stderr.replace(str(workdir) + os.sep, "").strip()


def _compile(workdir: Path, sources: list[str]) -> dict | None:
    """Returns None on success, else an error result dict."""
    cmd = [
        GCC, "-std=c11", "-Wall", "-Wextra", "-O1", "-g",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        *sources, "-o", "prog", "-lm",
    ]
    proc = subprocess.run(
        cmd, cwd=workdir, capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S
    )
    if proc.returncode != 0:
        return {
            "compiled": False,
            "passed": False,
            "errors": _sanitize_compiler_output(proc.stderr, workdir) or "compilation failed",
            "stdout": "",
            "timed_out": False,
            "checks": [],
        }
    return None


def _run(workdir: Path) -> dict:
    """Returns {ok, stdout, timed_out, exit_code}."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["./prog"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_S,
            preexec_fn=_apply_limits if os.name == "posix" else None,
        )
        elapsed = time.monotonic() - start
        # Killed by signal (negative returncode) means a limit kicked in.
        signal_kill = proc.returncode is not None and proc.returncode < 0
        result = {
            "ok": True,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "timed_out": signal_kill or elapsed >= RUN_TIMEOUT_S - 0.1,
        }
        return result
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "", "exit_code": None, "timed_out": True}


def validate_boss0(stdout: str) -> list[dict]:
    """Boss 0 — CLI particle sim.

    Expected output: for tick t in 0..199, ball ids 0..2:
        T <tick> <id> <x> <y>
    Constants: box 100x100, ball radius 1.0, gravity 9.8 (downward, y up).
    Checks: exact line shape/order, finite numbers, balls inside the box,
    total energy per ball never grows (E = y + 0.5*v²/g where v is recovered
    from successive positions; Euler leaks energy, Verlet does not).
    """
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    W = H = 100.0
    R = 1.0
    G_MAG = 9.8
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
        add("energy", False, "could not parse output")
        add("movement", False, "could not parse output")
        return checks

    bounds_ok = True
    moved_ok = True
    for bid, traj in positions.items():
        for _, x, y in traj:
            if not (R - 1e-3 <= x <= W - R + 1e-3 and R - 1e-3 <= y <= H - R + 1e-3):
                bounds_ok = False
                break
        xs = [x for _, x, _ in traj]
        ys = [y for _, _, y in traj]
        if (max(xs) - min(xs)) + (max(ys) - min(ys)) < 1.0:
            moved_ok = False
    add("bounds", bounds_ok, "every ball must stay inside [1, 99] x [1, 99]")
    add("movement", moved_ok, "balls must actually move")

    # Energy check: per ball, compute total energy E = y + 0.5*v^2 / g at every
    # tick (recovering v from successive y). With restitution 0.8, E should
    # never grow; small positive drift is rounding noise. A bad integrator
    # (Euler) will pump energy into the system and the ceiling check fails.
    energy_ok = True
    for bid, traj in positions.items():
        if len(traj) < 2:
            energy_ok = False
            continue
        emax = -1e30
        for i in range(1, len(traj)):
            y_prev = traj[i - 1][2]
            y_curr = traj[i][2]
            dt = 0.01
            vy = (y_curr - y_prev) / dt
            E = y_curr + 0.5 * vy * vy / G_MAG
            if E > emax:
                emax = E
        # Find the earliest peak (the initial release energy).
        e_peak_initial = -1e30
        for i in range(min(40, len(traj))):
            y_prev = traj[i - 1][2] if i > 0 else traj[0][2]
            y_curr = traj[i][2]
            dt = 0.01
            vy = (y_curr - y_prev) / dt
            E = y_curr + 0.5 * vy * vy / G_MAG
            if E > e_peak_initial:
                e_peak_initial = E
        if emax > e_peak_initial + 0.5:
            energy_ok = False
            break

    add("energy", energy_ok, "total energy must not grow (Euler leaks energy; use Verlet)")
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
            err = _compile(workdir, ["harness.c"])
        else:
            err = _compile(workdir, ["learner.c"])
        if err:
            return err

        run = _run(workdir)
        if run["timed_out"]:
            return {
                "compiled": True,
                "passed": False,
                "errors": "time limit exceeded (infinite loop or very slow code?)",
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
            "stdout": run["stdout"],
            "timed_out": False,
            "checks": checks,
            "runtime_stderr": run["stderr"],
            "exit_code": run["exit_code"],
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
