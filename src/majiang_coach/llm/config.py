"""LLMConfig:OpenAI 兼容 LLM 接入配置(Phase 4,见计划 §5)。

配置来源优先级:请求覆盖 > .env 环境变量。
  - from_env():读 os.environ 的 LLM_BASE_URL/API_KEY/MODEL;三项缺一返 None。
  - merged(override):请求覆盖(仅 base_url/api_key/model)合并进当前配置,优先级 请求>.env。
  - resolve_llm_config(override):整体解析(env + 请求覆盖),供 API/demo 复用。

temperature/timeout 仅来自环境(LLM_TEMPERATURE/LLM_TIMEOUT),请求覆盖不含(见 §7)。
api_key 视为敏感:不得出现在日志/异常/响应中(由 provider/advisor 保证)。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

__all__ = ["LLMConfig", "resolve_llm_config"]

# 缺门/花色无关:仅 base_url/api_key/model 三项可被请求覆盖。
_OVERRIDE_FIELDS = ("base_url", "api_key", "model")


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class LLMConfig:
    """OpenAI 兼容 chat completions 接入配置。"""

    base_url: str
    api_key: str
    model: str
    temperature: float = 0.3
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        """读 os.environ;base_url/api_key/model 三项缺一返 None。"""
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        api_key = os.environ.get("LLM_API_KEY", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        if not (base_url and api_key and model):
            return None
        temperature = _parse_float(os.environ.get("LLM_TEMPERATURE"), 0.3)
        timeout = _parse_float(os.environ.get("LLM_TIMEOUT"), 30.0)
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            timeout=timeout,
        )

    def merged(self, override: dict | None) -> "LLMConfig":
        """请求覆盖(优先级 请求>.env);仅 base_url/api_key/model 受覆盖。

        override 中某字段为空/缺失时保留原值(空串视为不覆盖)。
        """
        if not override:
            return self
        changes: dict = {}
        for field in _OVERRIDE_FIELDS:
            val = override.get(field)
            if val is None:
                continue
            val = val.strip() if isinstance(val, str) else val
            if val:
                changes[field] = val
        if not changes:
            return self
        return replace(self, **changes)


def resolve_llm_config(override: dict | None = None) -> LLMConfig | None:
    """整体解析配置:.env 为基线,请求覆盖优先;无任何可用配置返 None。

    - 有 .env:合并 override(override 填充提供的字段)。
    - 无 .env:仅当 override 三项齐全时构造配置;否则 None。
    """
    env = LLMConfig.from_env()
    if env is not None:
        return env.merged(override)
    if not override:
        return None
    base_url = (override.get("base_url") or "").strip() if isinstance(override.get("base_url"), str) else override.get("base_url")
    api_key = (override.get("api_key") or "").strip() if isinstance(override.get("api_key"), str) else override.get("api_key")
    model = (override.get("model") or "").strip() if isinstance(override.get("model"), str) else override.get("model")
    if base_url and api_key and model:
        return LLMConfig(base_url=base_url, api_key=api_key, model=model)
    return None
