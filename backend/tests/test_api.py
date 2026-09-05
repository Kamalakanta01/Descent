"""HTTP-level tests via FastAPI TestClient (catches tuple-vs-HTTPException bugs)."""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app as app

# TestClient runs the ASGI app in-process. The module-level `db` is constructed
# at import with the real data path; we swap it for a fresh tmp Store per test
# so the suite never touches the user's real data/state.json.


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import store
    from app.main import STATE_PATH
    import shutil

    backup = tmp_path / "state.backup"
    if STATE_PATH.exists():
        shutil.copy(STATE_PATH, backup)
    monkeypatch.setattr(main, "db", store.Store(tmp_path / "state.json"))
    with TestClient(app) as c:
        yield c
    if backup.exists():
        shutil.copy(backup, STATE_PATH)


def test_index_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "DESCENT" in r.text


def test_lesson_unknown_id_is_404(client):
    r = client.get("/api/lesson/nope")
    assert r.status_code == 404
    assert r.json()["detail"]


def test_answer_unknown_lesson_is_404(client):
    r = client.post("/api/answer", json={"lesson_id": "nope", "q_index": 0, "choice": 0})
    assert r.status_code == 404


def test_answer_bad_qindex_is_400(client):
    r = client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 99, "choice": 0})
    assert r.status_code == 400


def test_run_unknown_lesson_is_404(client):
    r = client.post("/api/checkpoint/run", json={"lesson_id": "nope", "code": "int main(void){return 0;}\n"})
    assert r.status_code == 404


def test_hint_unknown_lesson_is_404(client):
    r = client.post("/api/hint", json={"lesson_id": "nope", "wrong_answer": "x"})
    assert r.status_code == 404


def test_lesson_does_not_leak_answers(client):
    r = client.get("/api/lesson/w0u0l1")
    assert r.status_code == 200
    for q in r.json()["practice"]:
        assert "answer" not in q
        assert q["choices"]


def test_review_xp_after_pass_is_3(client):
    """Answer correctly before checkpoint passed => +5; after passed => +3."""
    r = client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 0, "choice": 0})
    assert r.status_code == 200
    assert r.json()["xp"] == 5

    # cheat-mark checkpoint passed directly in state
    s = main.db.load()
    s["passed"].append("w0u0l1c")
    main.db.save(s)

    r = client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 0, "choice": 0})
    assert r.status_code == 200
    assert r.json()["xp"] == 3