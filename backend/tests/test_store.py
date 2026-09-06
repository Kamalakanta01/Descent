import json
import time

from app import store


def test_default_state_created_on_first_use(tmp_path):
    s = store.Store(tmp_path / "state.json")
    state = s.load()
    assert state["xp"] == 0
    assert state["streak"] == 0
    assert state["skills"] == {}


def test_roundtrip_and_atomic_write(tmp_path):
    p = tmp_path / "state.json"
    s = store.Store(p)
    st = s.load()
    st["xp"] = 42
    s.save(st)
    assert json.loads(p.read_text())["xp"] == 42
    assert not (tmp_path / "state.tmp").exists()
    assert store.Store(p).load()["xp"] == 42


def test_update_runs_mutation_under_one_lock(tmp_path):
    s = store.Store(tmp_path / "state.json")
    n = s.update(lambda st: st.__setitem__("xp", st["xp"] + 7) or st["xp"])
    assert n == 7  # update returns fn's result…
    assert s.load()["xp"] == 7  # …and persists the mutation


def test_streak_starts_continues_and_breaks():
    st = store.default_state()
    day0 = time.mktime((2026, 9, 1, 10, 0, 0, 0, 0, -1))
    day1 = day0 + 86400
    day5 = day0 + 5 * 86400
    store.touch_activity(st, day0)
    assert st["streak"] == 1
    store.touch_activity(st, day0 + 3600)  # same day: no double count
    assert st["streak"] == 1
    store.touch_activity(st, day1)
    assert st["streak"] == 2
    store.touch_activity(st, day5)  # gap -> reset
    assert st["streak"] == 1


def test_record_result_updates_hlr_and_counts():
    st = store.default_state()
    now = 1_700_000_000.0
    sk = store.record_result(st, "l1", correct=True, now=now)
    assert sk["correct"] == 1 and sk["last_practiced"] == now
    h1 = sk["h_days"]
    sk = store.record_result(st, "l1", correct=False, now=now)
    assert sk["incorrect"] == 1 and sk["h_days"] < h1
    # initial half-life is the syllabus default
    assert store.get_skill(store.default_state(), "x")["h_days"] == 1.0
