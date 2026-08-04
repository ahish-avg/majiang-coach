"""provider.chat:OpenAI 兼容 chat/completions POST(Phase 4,见计划 §5)。

零新依赖:仅标准库 urllib.request + json,非流式。
  - response_format:{"type":"json_object"} 优先(json_mode=True);若服务返回 400
    (不支持该字段),自动回退一次纯文本重试。advisor 端再用正则兜底提取 JSON。
  - 错误统一抛 LLMError:网络/超时/HTTP 非法/响应结构异常。
  - 安全:异常信息只含 HTTP 状态/网络描述,绝不包含 api_key 或 Authorization 头。
"""

from __future__ import annotations

import json
import socket
import urllib.error
from urllib.request import Request, urlopen

from .config import LLMConfig

__all__ = ["LLMError", "chat"]


class LLMError(Exception):
    """LLM 调用失败(网络/鉴权/超时/HTTP/解析)。消息不含 api_key。"""


class _HTTPStatus(Exception):
    """内部信号:urlopen 抛出 HTTPError,携带状态码(用于 400 回退判定)。"""

    def __init__(self, code: int) -> None:
        super().__init__(f"HTTP {code}")
        self.code = code


def _endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _build_request(config: LLMConfig, messages: list[dict], json_mode: bool) -> Request:
    body: dict = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return Request(
        _endpoint(config.base_url),
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )


def _raw_post(config: LLMConfig, messages: list[dict], json_mode: bool) -> tuple[int, bytes]:
    """发起一次 POST,返回 (status, body_bytes);网络/超时抛 LLMError,HTTP 非法抛 _HTTPStatus。"""
    req = _build_request(config, messages, json_mode)
    try:
        with urlopen(req, timeout=config.timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raise _HTTPStatus(e.code) from None
    except urllib.error.URLError as e:
        raise LLMError(f"LLM 网络错误: {e.reason}") from None
    except (TimeoutError, socket.timeout):
        raise LLMError(f"LLM 请求超时({config.timeout}s)") from None
    return status, raw


def _extract_content(payload: dict) -> str:
    """从 OpenAI 兼容响应取 choices[0].message.content。"""
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM 响应结构异常") from e


def chat(messages: list[dict], config: LLMConfig, json_mode: bool = True) -> str:
    """POST {base_url}/chat/completions -> 返回 assistant content(str)。

    json_mode=True 时优先带 response_format;遇 HTTP 400(服务不支持)自动回退纯文本。
    任何失败抛 LLMError(信息不含 api_key)。
    """
    try:
        status, raw = _raw_post(config, messages, json_mode)
    except _HTTPStatus as e:
        if json_mode and e.code == 400:
            # 部分服务不支持 response_format -> 回退一次纯文本
            try:
                status, raw = _raw_post(config, messages, False)
            except _HTTPStatus as e2:
                raise LLMError(f"LLM HTTP {e2.code}") from None
        else:
            raise LLMError(f"LLM HTTP {e.code}") from None

    if not (200 <= status < 300):
        raise LLMError(f"LLM HTTP {status}")

    try:
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise LLMError("LLM 响应非 JSON") from e

    return _extract_content(payload)
