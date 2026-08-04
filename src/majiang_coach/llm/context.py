"""build_context(result, view) -> 聚焦 dict(Phase 4,见计划 §5)。

把 AnalysisResult + PlayerView 压缩成 LLM 必须强制引用的「分析数据」(控 token):
  - phase:弃牌态(14 张,有 recommend)/ 待摸态(13 张,无 recommend)。
  - hand/recommend/top5/best_*/claim:复用硬算数字(LLM 不得自创)。
  - opponents:仅可见信息(座/缺门/威胁/副露数),不含他家暗手。

解耦:本模块只消费 AnalysisResult + PlayerView 作数据(经 analysis 软权重 opponent_threat
取对手威胁,不重算 win/shanten/ukeire)。
"""

from __future__ import annotations

from ..analysis import opponent_threat, opp_lack
from ..analysis.recommend import AnalysisResult
from ..engine.view import PlayerView

__all__ = ["build_context"]

_LACK_INT_TO_LETTER = {0: "m", 1: "s", 2: "p"}


def _lack_letter(lack: int | None) -> str | None:
    return _LACK_INT_TO_LETTER.get(lack) if lack is not None else None


def _candidate_brief(c) -> dict:
    """候选 -> 精简字段(供 LLM 引用)。"""
    return {
        "code": c.code,
        "offense": c.offense_score,
        "danger": c.danger,
        "defense": c.defense_score,
        "composite": c.composite_score,
    }


def _recommend_brief(c) -> dict:
    """推荐候选 -> 精简字段(含叫牌形状/进张与安全理由)。"""
    brief = _candidate_brief(c)
    brief["shanten_after"] = c.shanten_after
    brief["ukeire_count"] = c.ukeire_count
    brief["ukeire_remaining_total"] = c.ukeire_remaining_total
    brief["safety_reasons"] = list(c.safety_reasons)
    return brief


def _opponents(view: PlayerView) -> list[dict]:
    """在局、非己对手的可见信息(座/缺门/威胁/副露数)。"""
    out: list[dict] = []
    for opp in view.active_seats:
        if opp == view.seat:
            continue
        meld_count = len(view.public_melds[opp]) if opp < len(view.public_melds) else 0
        out.append({
            "seat": opp,
            "lack": _lack_letter(opp_lack(view, opp)),
            "threat": round(opponent_threat(view, opp), 3),
            "meld_count": meld_count,
        })
    return out


def build_context(result: AnalysisResult, view: PlayerView) -> dict:
    """AnalysisResult + PlayerView -> 聚焦 dict(14 张 vs 13 张 分支)。"""
    is_discard = result.recommend is not None  # 14 张刚摸态

    context: dict = {
        "phase": "discard" if is_discard else "wait",
        "lack_suit": _lack_letter(result.lack_suit),
        "wall_remaining": view.wall_remaining,
        "weights_used": dict(result.weights_used),
        "hand": {
            "shanten": result.hand.shanten,
            "is_tenpai": result.hand.is_tenpai,
            "ukeire_count": result.hand.ukeire_count,
            "ukeire_remaining_total": result.hand.ukeire_remaining_total,
            "score": result.hand.score,
        },
        "recommend": _recommend_brief(result.recommend) if result.recommend else None,
        "top5": [_candidate_brief(c) for c in result.candidates[:5]],
        "best_offense": result.best_offense.code if result.best_offense else None,
        "best_defense": result.best_defense.code if result.best_defense else None,
        "claim": _claim_brief(result.claim) if result.claim else None,
        "opponents": _opponents(view),
    }
    return context


def _claim_brief(claim: dict) -> dict:
    """claim -> 精简字段。"""
    return {
        "code": claim.get("code"),
        "can_ron": claim.get("can_ron"),
        "can_pon": claim.get("can_pon"),
        "pon_shanten_after": claim.get("pon_shanten_after"),
    }
