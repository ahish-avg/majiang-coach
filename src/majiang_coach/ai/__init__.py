"""启发式 AI 对手层(Phase 5)。

HeuristicActor 实现 engine.game.Actor 协议,弱/中/强三档;能胡必胡、弃牌走
Phase 3 analyze 综合排序、碰/杠按 v0 策略。不调 LLM(LLM 仅给人类教练)。
"""

from __future__ import annotations

from .heuristic import HeuristicActor, STRENGTHS

__all__ = ["HeuristicActor", "STRENGTHS"]
