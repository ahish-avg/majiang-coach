"""练习模式(Phase 5):人类(座0)+ 3 启发式 AI 对手,REST 轮次制。

PracticeSession 为传输无关的可步进状态机:5 类人类决策点暂停、AI 座自动推进。
SessionStore 为内存会话存储 + idle TTL 清理(无 DB,Phase 7/8 再持久化)。
"""

from __future__ import annotations

from .prompt import (
    PendingDecision, action_to_dict, action_from_dict, view_to_dict,
    build_prompt, summarize_record,
)
from .session import PracticeSession, IllegalActionError
from .store import SessionStore

__all__ = [
    "PracticeSession",
    "IllegalActionError",
    "PendingDecision",
    "SessionStore",
    "action_to_dict",
    "action_from_dict",
    "view_to_dict",
    "build_prompt",
    "summarize_record",
]
