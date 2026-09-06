"""HTTP-level tests via FastAPI TestClient (catches tuple-vs-HTTPException bugs)."""

import json
import time

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


class _StubLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, *a, **kw):
        return (self.reply, "stub/model") if self.reply else (None, None)


FOLLOWUP_JSON = json.dumps({
    "q": "Simpler: what does a += b do to a?",
    "choices": ["Adds b into a", "Copies a into b", "Clears a"],
    "answer": 0,
    "explanation": "a += b updates a in place.",
})


def _wrong(client):
    return client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 0, "choice": 1})


def test_wrong_answer_offers_followup_and_scores_it(client, monkeypatch):
    monkeypatch.setattr(main, "llm_client", _StubLLM(FOLLOWUP_JSON))
    r = _wrong(client)
    body = r.json()
    assert body["correct"] is False
    fu = body["followup"]
    assert "answer" not in fu and fu["choices"] and fu["token"]

    r = client.post("/api/followup/answer", json={"token": fu["token"], "choice": 0})
    assert r.json()["correct"] is True
    assert r.json()["explanation"]

    # token is one-shot
    r = client.post("/api/followup/answer", json={"token": fu["token"], "choice": 0})
    assert r.status_code == 404


def test_followup_rejects_unknown_token(client):
    r = client.post("/api/followup/answer", json={"token": "nope", "choice": 0})
    assert r.status_code == 404


def test_no_followup_when_llm_silent_or_wrong_is_right(client, monkeypatch):
    monkeypatch.setattr(main, "llm_client", _StubLLM(None))
    assert "followup" not in _wrong(client).json()
    monkeypatch.setattr(main, "llm_client", _StubLLM(FOLLOWUP_JSON))
    r = client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 0, "choice": 0})
    assert "followup" not in r.json()


def test_followup_tolerates_markdown_fences(client, monkeypatch):
    monkeypatch.setattr(main, "llm_client", _StubLLM("```json\n" + FOLLOWUP_JSON + "\n```"))
    assert "followup" in _wrong(client).json()


def test_followup_absent_on_garbage_llm_json(client, monkeypatch):
    monkeypatch.setattr(main, "llm_client", _StubLLM("not json at all"))
    assert "followup" not in _wrong(client).json()


W0L1_INTEGRATE = """typedef struct { float x, y, vx, vy; } Particle;

void integrate(Particle *ps, int n, float dt) {
    for (int i = 0; i < n; i++) {
        ps[i].vy -= 9.8f * dt;
        ps[i].x  += ps[i].vx * dt;
        ps[i].y  += ps[i].vy * dt;
    }
}
"""


def test_answer_returns_correct_index_for_highlight(client):
    r = client.post("/api/answer", json={"lesson_id": "w0u0l1", "q_index": 0, "choice": 0})
    assert r.json()["answer_index"] == 0


def test_checkpoint_repass_pays_review_xp_only_when_due(client):
    # First pass: full XP
    r = client.post("/api/checkpoint/run", json={"lesson_id": "w0u0l1", "code": W0L1_INTEGRATE})
    assert r.json()["passed"] is True and r.json()["xp"] == 20 + 10

    # Immediate re-pass: not due -> 0 XP
    r = client.post("/api/checkpoint/run", json={"lesson_id": "w0u0l1", "code": W0L1_INTEGRATE})
    assert r.json()["passed"] is True and r.json()["xp"] == 0

    # Force the skill due (tiny half-life, practiced long ago)
    s = main.db.load()
    sk = s["skills"]["w0u0l1"]
    sk["h_days"] = 0.001
    sk["last_practiced"] = time.time() - 3 * 86400
    main.db.save(s)

    r = client.post("/api/checkpoint/run", json={"lesson_id": "w0u0l1", "code": W0L1_INTEGRATE})
    assert r.json()["passed"] is True and r.json()["xp"] == 3  # XP_REVIEW


def test_review_queue_includes_generated_question_with_llm(client, monkeypatch):
    monkeypatch.setattr(main, "llm_client", _StubLLM(FOLLOWUP_JSON))
    s = main.db.load()
    s["skills"]["w0u0l1"] = {"h_days": 0.001, "last_practiced": time.time() - 3 * 86400,
                             "correct": 1, "incorrect": 0}
    main.db.save(s)
    r = client.get("/api/review-queue")
    entry = next(d for d in r.json()["due"] if d["lesson_id"] == "w0u0l1")
    assert entry["generated"]["q"] == "Simpler: what does a += b do to a?"
    r = client.post("/api/followup/answer",
                    json={"token": entry["generated"]["token"], "choice": 0})
    assert r.json()["correct"] is True