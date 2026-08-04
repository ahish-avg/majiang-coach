"""advise():Phase 4 编排入口(见计划 §3/§5/§6)。

编排:
  1. result = analyze(view, weights)(Phase 3 纯函数);analysis = result.to_dict()(硬算,始终有)。
  2. hints_on=false -> advice=None, error=None。
  3. config 不可用 -> advice=None, error="未配置 LLM(...)"。
  4. provider.chat 失败 -> advice=None, error=str(e)。
  5. 解析失败 -> advice=None, error="LLM 输出非 JSON"。
  6. 防幻觉校验(14 张弃牌态):recommended_tile 规范化后须 == recommend.code;不符拦截。
  7. 成功 -> Advice(13 张待摸态强制 recommended_tile=None)。

analysis(硬算)任何分支都返回;hints_on/model_used/error 回传。
"""

from __future__ import annotations

import json
import re
from dataclasses import replace

from ..analysis import analyze
from ..engine.view import PlayerView
from .config import LLMConfig
from .context import build_context
from .prompt import build_messages
from .provider import LLMError, chat
from .result import Advice, AdviseResult

__all__ = ["advise"]

# 兜底 JSON 提取:json.loads 失败时,正则抓首个 {...} 块再解析(响应可能为纯文本包裹 JSON)。
_JSON_RE = re.compile(r"\{.*\}", re.S)

_NO_CONFIG_MSG = "未配置 LLM(base_url/api_key/model)"
_PARSE_FAIL_MSG = "LLM 输出非 JSON"
_HALLUCINATION_MSG = "推荐牌与硬算不符(防幻觉拦截)"


def _normalize(code: str) -> str:
    return code.strip().lower()


def _parse_advice(content: str) -> Advice | None:
    """content -> Advice(经 JSON 解析 + 字段校验);失败返 None。"""
    data: object = None
    try:
        data = json.loads(content)
    except (ValueError, json.JSONDecodeError):
        match = _JSON_RE.search(content)
        if match is None:
            return None
        try:
            data = json.loads(match.group(0))
        except (ValueError, json.JSONDecodeError):
            return None

    if not isinstance(data, dict):
        return None

    try:
        recommended_tile = data["recommended_tile"]
        offense_reason = data["offense_reason"]
        defense_reason = data["defense_reason"]
        teaching_point = data["teaching_point"]
        opponent_read = data["opponent_read"]
    except KeyError:
        return None

    if recommended_tile is not None and not isinstance(recommended_tile, str):
        return None
    if not all(
        isinstance(x, str) for x in (offense_reason, defense_reason, teaching_point, opponent_read)
    ):
        return None

    return Advice(
        recommended_tile=recommended_tile,
        offense_reason=offense_reason,
        defense_reason=defense_reason,
        teaching_point=teaching_point,
        opponent_read=opponent_read,
    )


def advise(
    view: PlayerView,
    hints_on: bool = True,
    llm_config: LLMConfig | None = None,
    weights: dict | None = None,
) -> AdviseResult:
    """编排硬算 + LLM 解释 + 防幻觉校验 + 兜底。

    llm_config 为已解析的 LLMConfig(由调用方经 resolve_llm_config 解析 env+请求覆盖);
    为 None 视为未配置(不影响硬算 analysis 返回)。
    """
    result = analyze(view, weights)
    analysis = result.to_dict()

    if not hints_on:
        return AdviseResult(
            analysis=analysis, advice=None, hints_on=False, error=None, model_used=None
        )

    if llm_config is None:
        return AdviseResult(
            analysis=analysis, advice=None, hints_on=True, error=_NO_CONFIG_MSG, model_used=None
        )

    model_used = getattr(llm_config, "model", None)

    try:
        context = build_context(result, view)
        messages = build_messages(context)
        content = chat(messages, llm_config, json_mode=True)
    except LLMError as e:
        return AdviseResult(
            analysis=analysis, advice=None, hints_on=True, error=str(e), model_used=model_used
        )

    advice = _parse_advice(content)
    if advice is None:
        return AdviseResult(
            analysis=analysis, advice=None, hints_on=True, error=_PARSE_FAIL_MSG, model_used=model_used
        )

    # 防幻觉校验(14 张弃牌态):recommended_tile 须 == 硬算 recommend.code。
    if result.recommend is not None:
        expected = _normalize(result.recommend.code)
        given = advice.recommended_tile
        if given is None or _normalize(given) != expected:
            return AdviseResult(
                analysis=analysis, advice=None, hints_on=True,
                error=_HALLUCINATION_MSG, model_used=model_used,
            )
    else:
        # 13 张待摸态:无 recommend 可比对,强制 recommended_tile=None(契约要求)。
        advice = replace(advice, recommended_tile=None)

    return AdviseResult(
        analysis=analysis, advice=advice, hints_on=True, error=None, model_used=model_used
    )
