"""tests for POST /api/phase4/advise (Phase 4 API 端点,见计划 §7/§8.8)。"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import os  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from majiang_coach.llm import advisor  # noqa: E402

client = TestClient(app)

_CODES_14 = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"]
_CODES_13 = ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"]


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    """每个测试默认清空 LLM_* 环境变量,避免本机 .env 污染。"""
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TEMPERATURE", "LLM_TIMEOUT"):
        monkeypatch.delenv(k, raising=False)


def _rec_code():
    from majiang_coach.analysis import analyze
    from majiang_coach.engine.view import PlayerView
    from majiang_coach.hand import Hand
    h = Hand.from_codes(_CODES_14)
    v = PlayerView(seat=0, hand=h, lack_suit=2, lack_suits=(2, 2, 2, 2), wall_remaining=30)
    return analyze(v).recommend.code


def _advice_json(tile):
    import json
    return json.dumps({
        "recommended_tile": tile,
        "offense_reason": "进攻", "defense_reason": "防守",
        "teaching_point": "教学", "opponent_read": "读牌",
    }, ensure_ascii=False)


# ---- hints_on=false ----

def test_phase4_hints_off():
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p", "hints_on": False})
    assert r.status_code == 200
    body = r.json()
    assert body["hints_on"] is False
    assert body["advice"] is None
    assert body["error"] is None
    assert body["model_used"] is None
    assert body["analysis"]["hand_total"] == 14
    assert body["analysis"]["recommend"] is not None


# ---- 无配置 ----

def test_phase4_no_config_error():
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    assert r.status_code == 200
    body = r.json()
    assert body["hints_on"] is True
    assert body["advice"] is None
    assert "未配置" in body["error"]
    assert body["analysis"]["hand_total"] == 14


# ---- mock provider 成功 ----

def test_phase4_success_with_env_config(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "sk-from-env")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    rec = _rec_code()

    seen = {}

    def fake_chat(messages, config, json_mode=True):
        seen["model"] = config.model
        seen["key"] = config.api_key
        return _advice_json(rec)

    monkeypatch.setattr(advisor, "chat", fake_chat)
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    assert r.status_code == 200
    body = r.json()
    assert body["advice"] is not None
    assert body["advice"]["recommended_tile"] == rec
    assert body["error"] is None
    assert body["model_used"] == "env-model"
    assert seen["key"] == "sk-from-env"
    # key 不回显
    assert "sk-from-env" not in r.text


def test_phase4_request_override_config(monkeypatch):
    # 无 env,请求体 llm 提供完整覆盖
    rec = _rec_code()
    seen = {}

    def fake_chat(messages, config, json_mode=True):
        seen["model"] = config.model
        seen["base_url"] = config.base_url
        return _advice_json(rec)

    monkeypatch.setattr(advisor, "chat", fake_chat)
    r = client.post("/api/phase4/advise", json={
        "codes": _CODES_14, "lack_suit": "p",
        "llm": {"base_url": "https://req", "api_key": "sk-req", "model": "req-model"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["advice"] is not None
    assert body["model_used"] == "req-model"
    assert seen["model"] == "req-model"
    assert seen["base_url"] == "https://req"
    # key 不回显
    assert "sk-req" not in r.text


def test_phase4_override_partial_without_env_no_config(monkeypatch):
    # 无 env + 部分覆盖(仅 model) -> 仍无配置 -> 未配置
    monkeypatch.setattr(advisor, "chat", lambda *a, **k: pytest.fail("chat 不应被调用"))
    r = client.post("/api/phase4/advise", json={
        "codes": _CODES_14, "lack_suit": "p",
        "llm": {"model": "req-model"},
    })
    body = r.json()
    assert body["advice"] is None
    assert "未配置" in body["error"]


def test_phase4_antihallucination_intercept(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "sk-x")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(advisor, "chat", lambda *a, **k: _advice_json("9p"))
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    body = r.json()
    assert body["advice"] is None
    assert "防幻觉" in body["error"]
    assert body["analysis"]["recommend"] is not None


def test_phase4_13tile_wait(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "sk-x")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(advisor, "chat", lambda *a, **k: _advice_json("5m"))
    r = client.post("/api/phase4/advise", json={
        "codes": _CODES_13, "lack_suit": "p", "last_discard": "5m",
    })
    body = r.json()
    assert body["advice"] is not None
    assert body["advice"]["recommended_tile"] is None  # 待摸态强制 null
    assert body["analysis"]["recommend"] is None
    assert body["analysis"]["claim"]["can_ron"] is True


def test_phase4_chat_error_degrades(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "sk-x")
    monkeypatch.setenv("LLM_MODEL", "m")
    from majiang_coach.llm.provider import LLMError
    monkeypatch.setattr(advisor, "chat", lambda *a, **k: (_ for _ in ()).throw(LLMError("LLM HTTP 500")))
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    body = r.json()
    assert body["advice"] is None
    assert "500" in body["error"]
    assert body["analysis"]["hand_total"] == 14


def test_phase4_error_message_has_no_key(monkeypatch):
    secret = "sk-leak-check-12345"
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", secret)
    monkeypatch.setenv("LLM_MODEL", "m")
    from majiang_coach.llm.provider import LLMError
    monkeypatch.setattr(advisor, "chat", lambda *a, **k: (_ for _ in ()).throw(LLMError("LLM HTTP 401")))
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    assert secret not in r.text


def test_phase4_reuses_phase3_fields():
    # 复用 phase3 PlayerView 字段(weights/melds/lack_suits 等)
    r = client.post("/api/phase4/advise", json={
        "codes": _CODES_14, "lack_suit": "p", "hints_on": False,
        "weights": {"offense": 0.8, "defense": 0.2},
    })
    body = r.json()
    assert body["analysis"]["weights_used"] == {"offense": 0.8, "defense": 0.2}


def test_phase4_empty_codes_400():
    r = client.post("/api/phase4/advise", json={"codes": [], "lack_suit": "p"})
    assert r.status_code == 400


def test_phase4_invalid_codes_400():
    r = client.post("/api/phase4/advise", json={"codes": ["zz"], "lack_suit": "p"})
    assert r.status_code == 400


# ---- 可选:真实 API 集成(无 key 时 skip,仿 oracle skip 模式) ----

@pytest.mark.skipif(
    not (os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY") and os.environ.get("LLM_MODEL")),
    reason="未配置真实 LLM key(LLM_BASE_URL/API_KEY/MODEL)",
)
def test_phase4_real_integration():
    r = client.post("/api/phase4/advise", json={"codes": _CODES_14, "lack_suit": "p"})
    assert r.status_code == 200
    body = r.json()
    assert body["analysis"]["recommend"] is not None
    # 真实 LLM 应通过防幻觉(recommended_tile == recommend.code)或兜底 error
    if body["advice"] is not None:
        assert body["advice"]["recommended_tile"] == body["analysis"]["recommend"]["code"]
    else:
        assert body["error"] is not None
