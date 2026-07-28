"""Analysis Engine(Phase 3):硬计算结构化输出。

纯函数 analyze(view, weights=None) -> AnalysisResult,输入一个座位视角 PlayerView,
输出结构化 JSON 就绪结果:手牌差张下叫/进张(含副露)、每张可弃牌的进攻期望 + 安全度
+ 综合排序推荐。供 Phase 4 LLM 引用防幻觉、Phase 5 启发式 AI 消费、Phase 6 复盘复用。

核心零第三方依赖(仅 API 层依赖 fastapi)。
"""

from __future__ import annotations

from .visible import visible_counts, remaining_counts
from .threat import opponent_threat, opp_lack
from .safety import OpponentDanger, Safety, safety_of, seat_relative_name
from .offense import UkeireWait, Offense, offense_of
from .recommend import Candidate, AnalysisResult, analyze
from .result import analysis_result_to_dict, analysis_result_from_dict

__all__ = [
    "visible_counts",
    "remaining_counts",
    "opponent_threat",
    "opp_lack",
    "OpponentDanger",
    "Safety",
    "safety_of",
    "seat_relative_name",
    "UkeireWait",
    "Offense",
    "offense_of",
    "Candidate",
    "AnalysisResult",
    "analyze",
    "analysis_result_to_dict",
    "analysis_result_from_dict",
]
