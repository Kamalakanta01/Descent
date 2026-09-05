"""Runner checks across both checkpoint kinds."""

import pytest

from app import runner


SOLUTION = r"""
typedef struct { float x, y, vx, vy; } Particle;
void integrate(Particle *ps, int n, float dt) {
    const float G = 9.8f;
    for (int i = 0; i < n; i++) {
        ps[i].vy -= G * dt;
        ps[i].x  += ps[i].vx * dt;
        ps[i].y  += ps[i].vy * dt;
    }
}
"""

HARNESS = r"""
#include <stdio.h>
#include <math.h>
#include "learner.c"
static int fails = 0;
#define CLOSE(a,b) (fabsf((a)-(b)) < 1e-3f)
static void chk(const char *n, int cond, double got, double exp) {
    if (!cond) { printf("FAIL %s got=%f exp=%f\n", n, got, exp); fails++; }
}
int main(void) {
    Particle ps[3] = {
        {0, 10,  1,  0},
        {5, 20, -2,  3},
        {-4, 0,  0,  0},
    };
    integrate(ps, 3, 0.5f);
    chk("p0.vy", CLOSE(ps[0].vy, -4.9f), ps[0].vy, -4.9f);
    chk("p0.x",  CLOSE(ps[0].x,   0.5f), ps[0].x, 0.5f);
    chk("p0.y",  CLOSE(ps[0].y,  10 + -4.9f * 0.5f), ps[0].y, 10 + -4.9f * 0.5f);
    chk("p1.x",  CLOSE(ps[1].x,  4.0f), ps[1].x, 4.0f);
    chk("p2.vy", CLOSE(ps[2].vy, -4.9f), ps[2].vy, -4.9f);
    if (!fails) printf("ALL PASS\n");
    return fails ? 1 : 0;
}
"""


def test_function_checkpoint_passes_on_correct_solution():
    cp = {"kind": "function", "harness": HARNESS}
    res = runner.compile_and_run(cp, SOLUTION)
    assert res["compiled"] is True
    assert res["passed"] is True
    assert "ALL PASS" in res["stdout"]


def test_function_checkpoint_fails_on_wrong_solution():
    bad = SOLUTION.replace("ps[i].vy -= G * dt;", "ps[i].vy += G * dt;")
    res = runner.compile_and_run({"kind": "function", "harness": HARNESS}, bad)
    assert res["compiled"] is True
    assert res["passed"] is False


def test_compile_error_reported_cleanly():
    res = runner.compile_and_run({"kind": "function", "harness": HARNESS}, SOLUTION + "\nTHIS IS NOT C ;\n")
    assert res["compiled"] is False
    assert res["passed"] is False
    assert res["errors"]


INFINITE_HARNESS = r"""
#include <stdio.h>
#include "learner.c"
int main(void) {
    int v = infinite_int(3);
    printf("%d\n", v);
    return 0;
}
"""


def test_infinite_loop_is_timed_out():
    res = runner.compile_and_run(
        {"kind": "function", "harness": INFINITE_HARNESS},
        "int infinite_int(int x) { while (1) { x++; } return x; }\n",
    )
    assert res["compiled"] is True
    assert res["timed_out"] is True
    assert res["passed"] is False


BOSS0_REFERENCE = r"""
#include <stdio.h>
#include <math.h>
typedef struct { float x, y, vx, vy, px, py; } Ball;
static const float G = -9.8f;
static const float W = 100, H = 100, R = 1, REST = 0.8f, DT = 0.01f;

static void verlet_step(Ball *b) {
    b->x  += b->vx * DT + 0.5f * 0 * DT * DT;
    b->y  += b->vy * DT + 0.5f * G * DT * DT;
    b->vx += 0;
    b->vy += G * DT;
    if (b->x < R)        { b->x = R;       b->vx = -b->vx * REST; }
    if (b->x > W - R)    { b->x = W - R;   b->vx = -b->vx * REST; }
    if (b->y < R)        { b->y = R;       b->vy = -b->vy * REST; }
    if (b->y > H - R)    { b->y = H - R;   b->vy = -b->vy * REST; }
}

int main(void) {
    Ball balls[3] = {
        {10, 90, 15,  0,  10, 90},
        {50, 70, -8, 20,  50, 70},
        {90, 95, -20, -5, 90, 95},
    };
    const int TICKS = 200;
    for (int t = 0; t < TICKS; t++) {
        for (int i = 0; i < 3; i++) verlet_step(&balls[i]);
        for (int i = 0; i < 3; i++) printf("T %d %d %.4f %.4f\n", t, i, balls[i].x, balls[i].y);
    }
    return 0;
}
"""


def test_boss0_reference_passes_validator():
    cp = {"kind": "program", "validator": "boss0"}
    res = runner.compile_and_run(cp, BOSS0_REFERENCE)
    assert res["compiled"] is True
    assert res["passed"] is True, [c for c in res["checks"]]
    assert any(c["name"] == "deterministic" and c["ok"] for c in res["checks"])
