"""tests for llm/provider.py(Phase 4,见计划 §5/§8.4)。

monkeypatch provider.urlopen(urllib.request.urlopen 的模块内引用):
  - 正常返 content;请求体含 response_format/Authorization/model/temperature。
  - HTTP 401/500 -> LLMError(信息不含 key)。
  - 超时 -> LLMError。
  - json_mode 遇 400 -> 自动回退纯文本重试。
  - 非 JSON 响应体 / 结构异常 -> LLMError。
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from majiang_coach.llm import provider
from majiang_coach.llm.config import LLMConfig
from majiang_coach.llm.provider import LLMError, chat

API_KEY = "sk-super-secret-key-xyz"


def _cfg(json_mode_kwargs=None) -> LLMConfig:
    return LLMConfig("https://api.example.com/v1", API_KEY, "demo-model", 0.2, 12.0)


class FakeResp:
    def __init__(self, status=200, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_body(content="hello"):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def _set_urlopen(monkeypatch, fn):
    monkeypatch.setattr(provider, "urlopen", fn)


def _captured_requests(monkeypatch, responses):
    """responses: list of either ('ok', bytes) / ('http', code) / ('timeout',) / ('urlerror', reason)。
    记录每次请求的 Request 对象,返回 captured list。"""
    captured = []
    it = iter(responses)

    def fake(req, timeout=None):
        captured.append(req)
        kind, val = next(it)
        if kind == "ok":
            return FakeResp(200, val)
        if kind == "http":
            raise urllib.error.HTTPError(req.full_url, val, "err", {}, None)
        if kind == "timeout":
            raise TimeoutError("timed out")
        if kind == "urlerror":
            raise urllib.error.URLError(val)
        raise AssertionError(f"unknown {kind}")

    _set_urlopen(monkeypatch, fake)
    return captured


# ---- 正常路径 ----

def test_chat_returns_content(monkeypatch):
    cap = _captured_requests(monkeypatch, [("ok", _ok_body("建议内容"))])
    out = chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    assert out == "建议内容"
    assert len(cap) == 1


def test_chat_request_body_contains_fields(monkeypatch):
    cap = _captured_requests(monkeypatch, [("ok", _ok_body("x"))])
    chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    req = cap[0]
    body = json.loads(req.data.decode())
    assert body["model"] == "demo-model"
    assert body["temperature"] == 0.2
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["response_format"] == {"type": "json_object"}


def test_chat_request_url_and_auth(monkeypatch):
    cap = _captured_requests(monkeypatch, [("ok", _ok_body("x"))])
    chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    req = cap[0]
    assert req.full_url == "https://api.example.com/v1/chat/completions"
    assert req.get_header("Authorization") == f"Bearer {API_KEY}"
    assert req.get_header("Content-type") == "application/json"


def test_chat_json_mode_false_omits_response_format(monkeypatch):
    cap = _captured_requests(monkeypatch, [("ok", _ok_body("x"))])
    chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=False)
    body = json.loads(cap[0].data.decode())
    assert "response_format" not in body


# ---- 错误路径:信息不含 key ----

@pytest.mark.parametrize("code", [400, 401, 403, 500, 502])
def test_chat_http_error_raises_llmerror_no_key(monkeypatch, code):
    # 400 在 json_mode=True 下会触发回退重试;此处用 json_mode=False 避免回退,直接断言状态码错误。
    _captured_requests(monkeypatch, [("http", code)])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=False)
    assert str(code) in str(ei.value)
    assert API_KEY not in str(ei.value)


def test_chat_timeout_raises_llmerror_no_key(monkeypatch):
    _captured_requests(monkeypatch, [("timeout", None)])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg())
    assert "超时" in str(ei.value)
    assert API_KEY not in str(ei.value)


def test_chat_urlerror_raises_llmerror_no_key(monkeypatch):
    _captured_requests(monkeypatch, [("urlerror", "connection refused")])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg())
    assert "网络错误" in str(ei.value)
    assert API_KEY not in str(ei.value)


def test_chat_non_json_response(monkeypatch):
    _captured_requests(monkeypatch, [("ok", b"not json at all")])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg())
    assert "响应非 JSON" in str(ei.value)


def test_chat_bad_structure(monkeypatch):
    _captured_requests(monkeypatch, [("ok", json.dumps({"foo": "bar"}).encode())])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg())
    assert "结构异常" in str(ei.value)


# ---- json_object 不支持 -> 400 回退 ----

def test_chat_json_mode_400_falls_back_to_plain(monkeypatch):
    # 第一次(json_mode=True)400,第二次(回退纯文本)200
    cap = _captured_requests(monkeypatch, [
        ("http", 400),
        ("ok", _ok_body("纯文本里的结果")),
    ])
    out = chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    assert out == "纯文本里的结果"
    assert len(cap) == 2
    # 第一次带 response_format,回退不带
    assert "response_format" in json.loads(cap[0].data.decode())
    assert "response_format" not in json.loads(cap[1].data.decode())


def test_chat_json_mode_400_fallback_also_fails(monkeypatch):
    _captured_requests(monkeypatch, [("http", 400), ("http", 500)])
    with pytest.raises(LLMError) as ei:
        chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    assert "500" in str(ei.value)


def test_chat_non_400_http_no_fallback(monkeypatch):
    # 非 400(如 401)不应触发回退,只请求一次
    cap = _captured_requests(monkeypatch, [("http", 401)])
    with pytest.raises(LLMError):
        chat([{"role": "user", "content": "hi"}], _cfg(), json_mode=True)
    assert len(cap) == 1
