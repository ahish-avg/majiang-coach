"""LLM 助手层(Phase 4):可插拔 OpenAI 兼容教练,解释 Phase 3 硬算推荐(防幻觉、不替打)。

编排入口 advise(view, hints_on, llm_config, weights) -> AdviseResult:
  - 硬算 analysis(Phase 3)始终返回。
  - hints_on=true 且配置可用时,LLM 输出结构化 Advice(强制引用注入数字,过防幻觉校验)。
  - 任何失败兜底 advice=None + error;不崩溃。

解耦:llm/ 包只消费 AnalysisResult + PlayerView 作数据,绝不调用 win/shanten/ukeire
(规则不重算,见计划 §1/§10)。
"""

from __future__ import annotations

from .config import LLMConfig, resolve_llm_config
from .context import build_context
from .prompt import SYSTEM_PROMPT, build_messages
from .provider import LLMError, chat
from .result import Advice, AdviseResult
from .advisor import advise

__all__ = [
    "LLMConfig",
    "resolve_llm_config",
    "build_context",
    "SYSTEM_PROMPT",
    "build_messages",
    "LLMError",
    "chat",
    "Advice",
    "AdviseResult",
    "advise",
]
