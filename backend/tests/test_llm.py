from app import llm


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def fake_models(free_ids):
    return {"data": [{"id": i, "pricing": {"prompt": "0", "completion": "0"}} for i in free_ids]}


def test_preference_ordering_puts_known_strong_first():
    ranking = sorted(
        ["meta-llama/llama-3.3-70b-instruct:free",
         "deepseek/deepseek-chat-v3-0324:free",
         "z-ai/glm-5.2:free",
         "qwen/qwen3-coder:free",
         "minimax/minimax-m3:free"],
        key=lambda i: llm._rank(i),
    )
    assert "deepseek" in ranking[0]
    assert "qwen3-coder" in ranking[1]
    assert "llama" in ranking[-1]


def test_candidate_models_uses_live_when_available():
    client = llm.LLMClient(api_key="x", get_fn=lambda *a, **kw: fake_models([
        "minimax/minimax-m3:free", "deepseek/deepseek-chat-v3-0324:free",
        "z-ai/glm-5.2:free"]), sleep_fn=lambda *a, **k: None)
    cands = client.candidate_models()
    assert cands[0].startswith("deepseek")
    assert any("minimax" in c for c in cands)


def test_candidate_models_falls_back_when_offline():
    def boom(*a, **kw): raise RuntimeError("offline")
    client = llm.LLMClient(api_key=None, get_fn=boom)
    cands = client.candidate_models()
    assert cands  # non-empty hardcoded fallback
    assert "minimax/minimax-m2.7:free" in cands


def test_chat_returns_content_and_model_on_200():
    client = llm.LLMClient(
        api_key="x",
        get_fn=lambda *a, **kw: fake_models(["deepseek/deepseek-x:free"]),
        post_fn=lambda *a, **kw: (200, {"choices": [{"message": {"content": "Try again?"}}]}),
        sleep_fn=lambda *a, **k: None,
    )
    content, model = client.chat("system", "user")
    assert content == "Try again?" and model is not None


def test_chat_falls_through_to_next_model_on_429():
    posts = []
    sleeps = []
    def post(url, headers, payload, timeout):
        posts.append(payload["model"])
        return 429, {"error": "rate limited"}
    client = llm.LLMClient(
        api_key="x",
        get_fn=lambda *a, **kw: fake_models(["deepseek/a:free", "qwen/b:free", "z-ai/c:free"]),
        post_fn=post, sleep_fn=lambda s, *a, **k: sleeps.append(s),
    )
    content, model = client.chat("system", "user", max_models=3)
    assert content is None and model is None
    assert len(posts) == 3
    assert sleeps == [llm.BACKOFF_RATE_LIMIT_S] * 3


def test_chat_backs_off_short_on_generic_failure():
    sleeps = []
    def post(url, headers, payload, timeout):
        return 500, {"error": "boom"}
    client = llm.LLMClient(
        api_key="x",
        get_fn=lambda *a, **kw: fake_models(["deepseek/a:free", "qwen/b:free"]),
        post_fn=post, sleep_fn=lambda s, *a, **k: sleeps.append(s),
    )
    client.chat("system", "user", max_models=2)
    assert sleeps == [llm.BACKOFF_S] * 2


def test_chat_skips_null_content_and_uses_next_model():
    posts = []
    def post(url, headers, payload, timeout):
        posts.append(payload["model"])
        return (200, {"choices": [{"message": {"content": None}}]}) if len(posts) == 1 \
            else (200, {"choices": [{"message": {"content": "Got it"}}]})
    client = llm.LLMClient(
        api_key="x",
        get_fn=lambda *a, **kw: fake_models(["deepseek/a:free", "qwen/b:free"]),
        post_fn=post, sleep_fn=lambda s, *a, **k: None,
    )
    content, model = client.chat("system", "user", max_models=2)
    assert content == "Got it"
    assert len(posts) == 2


def test_chat_without_key_returns_none():
    client = llm.LLMClient(api_key=None)
    assert client.chat("s", "u") == (None, None)
