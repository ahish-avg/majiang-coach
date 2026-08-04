"""tests for llm/config.py(Phase 4,见计划 §5/§8.1)。"""

from __future__ import annotations

import pytest

from majiang_coach.llm.config import LLMConfig, resolve_llm_config


_FULL_ENV = {
    "LLM_BASE_URL": "https://api.example.com",
    "LLM_API_KEY": "sk-secret",
    "LLM_MODEL": "gpt-demo",
}


def _set_env(monkeypatch, env: dict):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TEMPERATURE", "LLM_TIMEOUT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_from_env_all_set_defaults(monkeypatch):
    _set_env(monkeypatch, _FULL_ENV)
    cfg = LLMConfig.from_env()
    assert cfg is not None
    assert cfg.base_url == "https://api.example.com"
    assert cfg.api_key == "sk-secret"
    assert cfg.model == "gpt-demo"
    assert cfg.temperature == 0.3
    assert cfg.timeout == 30.0


@pytest.mark.parametrize("missing", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"])
def test_from_env_missing_one_returns_none(monkeypatch, missing):
    env = dict(_FULL_ENV)
    env.pop(missing)
    _set_env(monkeypatch, env)
    assert LLMConfig.from_env() is None


def test_from_env_blank_treated_as_missing(monkeypatch):
    env = dict(_FULL_ENV)
    env["LLM_API_KEY"] = "   "
    _set_env(monkeypatch, env)
    assert LLMConfig.from_env() is None


def test_from_env_temperature_timeout(monkeypatch):
    _set_env(monkeypatch, {**_FULL_ENV, "LLM_TEMPERATURE": "0.1", "LLM_TIMEOUT": "10.5"})
    cfg = LLMConfig.from_env()
    assert cfg.temperature == 0.1
    assert cfg.timeout == 10.5


def test_from_env_bad_float_falls_back(monkeypatch):
    _set_env(monkeypatch, {**_FULL_ENV, "LLM_TEMPERATURE": "abc", "LLM_TIMEOUT": ""})
    cfg = LLMConfig.from_env()
    assert cfg.temperature == 0.3
    assert cfg.timeout == 30.0


def _base_cfg() -> LLMConfig:
    return LLMConfig("https://env.example.com", "env-key", "env-model", 0.2, 15.0)


def test_merged_none_unchanged():
    cfg = _base_cfg()
    assert cfg.merged(None) == cfg
    assert cfg.merged({}) == cfg


def test_merged_partial_override():
    cfg = _base_cfg()
    m = cfg.merged({"model": "req-model"})
    assert m.model == "req-model"
    assert m.base_url == "https://env.example.com"
    assert m.api_key == "env-key"
    # temperature/timeout 不受请求覆盖影响
    assert m.temperature == 0.2
    assert m.timeout == 15.0


def test_merged_all_override():
    cfg = _base_cfg()
    m = cfg.merged({"base_url": "https://req.example.com", "api_key": "req-key", "model": "req-model"})
    assert m.base_url == "https://req.example.com"
    assert m.api_key == "req-key"
    assert m.model == "req-model"


def test_merged_blank_keeps_env():
    cfg = _base_cfg()
    m = cfg.merged({"api_key": "", "model": "  "})
    assert m.api_key == "env-key"
    assert m.model == "env-model"


def test_merged_returns_new_instance():
    cfg = _base_cfg()
    m = cfg.merged({"model": "req-model"})
    assert m is not cfg
    assert cfg.model == "env-model"  # 原对象不变


def test_resolve_env_only(monkeypatch):
    _set_env(monkeypatch, _FULL_ENV)
    cfg = resolve_llm_config(None)
    assert cfg is not None and cfg.model == "gpt-demo"


def test_resolve_env_plus_override_merge(monkeypatch):
    _set_env(monkeypatch, _FULL_ENV)
    cfg = resolve_llm_config({"model": "req-model"})
    assert cfg.model == "req-model"
    assert cfg.api_key == "sk-secret"  # env 补全


def test_resolve_override_only_complete(monkeypatch):
    _set_env(monkeypatch, {})
    cfg = resolve_llm_config({"base_url": "https://x", "api_key": "k", "model": "m"})
    assert cfg is not None
    assert cfg.base_url == "https://x"
    assert cfg.temperature == 0.3  # 无 env -> 默认


def test_resolve_override_partial_without_env_returns_none(monkeypatch):
    _set_env(monkeypatch, {})
    assert resolve_llm_config({"model": "m"}) is None


def test_resolve_nothing_returns_none(monkeypatch):
    _set_env(monkeypatch, {})
    assert resolve_llm_config(None) is None
