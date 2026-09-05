import math

from app import hlr


def test_p_recall_at_zero_dt_is_one():
    assert hlr.p_recall(1.0, 0.0) == 1.0


def test_p_recall_after_one_half_life_is_half():
    assert math.isclose(hlr.p_recall(2.0, 2.0), 0.5, abs_tol=1e-9)


def test_p_recall_after_two_half_lives_is_quarter():
    assert math.isclose(hlr.p_recall(0.5, 1.0), 0.25, abs_tol=1e-9)


def test_correct_grows_half_life():
    assert math.isclose(hlr.on_correct(1.0), 1.7)


def test_wrong_shrinks_half_life_but_respects_floor():
    assert math.isclose(hlr.on_wrong(1.0), 0.4)
    floor = hlr.on_wrong(0.01)
    assert floor == hlr.H_MIN_DAYS


def test_days_until_due_matches_threshold_definition():
    h = 2.0
    t = hlr.days_until_due(h)
    assert math.isclose(hlr.p_recall(h, t), hlr.DUE_THRESHOLD, rel_tol=1e-9)


def test_is_due_boundary():
    now = 1_700_000_000.0
    # practiced 10 half-lives ago -> p ~ 0.001 -> definitely due
    assert hlr.is_due(0.1, now - 10 * 0.1 * hlr.SECONDS_PER_DAY, now)
    # just practiced -> not due
    assert not hlr.is_due(1.0, now, now)
