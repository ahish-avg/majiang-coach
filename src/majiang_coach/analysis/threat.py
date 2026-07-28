"""对手威胁度 v0(Phase 3,见计划 §6.4)。

opponent_threat(view, opp) -> 0..1:听牌概率粗估(软权重,仅作危险度调节)。

v0 模型(钉死为 v0,测试只要求单调趋势,不要求绝对准):
  - 副露数:+0.15/副,贡献上限 0.6(副露多≈更接近下叫,但不等于已下叫)。
  - 缺门已清:+0.2。检测:opp 缺门已公开(lack_suits[opp] 非 None)且其最近一次弃牌
        非缺门牌。依据血战"缺门优先"规则(有缺门牌时只能弃缺门牌),最近弃牌非缺门
        => 缺门已打完 => 已清。
  - 晚巡:+0.2。wall_remaining <= 20 视为晚巡。
  - clamp 0..1。

说明:副露多≠已下叫(可能很烂),故仅作软权重,经 0.5+0.5*threat 调节危险度(见 safety)。
"""

from __future__ import annotations

from .. import tiles
from ..engine.view import PlayerView

__all__ = ["opponent_threat", "opp_lack"]

# 晚巡阈值:牌墙剩余 drawable <= 此值视为晚巡
_LATE_WALL_THRESHOLD = 20


def opp_lack(view: PlayerView, opp: int) -> int | None:
    """opp 的公开缺门(无则 None)。"""
    if 0 <= opp < len(view.lack_suits):
        return view.lack_suits[opp]
    return None


def _lack_cleared(view: PlayerView, opp: int) -> bool:
    """opp 是否已清缺门(最近弃牌非缺门牌 => 缺门已打完)。"""
    L = opp_lack(view, opp)
    if L is None:
        return False
    d = view.discards[opp] if opp < len(view.discards) else ()
    if not d:
        return False
    return tiles.suit_of(d[-1]) != L


def opponent_threat(view: PlayerView, opp: int) -> float:
    """opp 的听牌概率粗估 v0(0..1)。"""
    threat = 0.0
    # 副露数(他座公开副露)
    seat_melds = view.public_melds[opp] if opp < len(view.public_melds) else ()
    threat += min(0.15 * len(seat_melds), 0.6)
    # 缺门已清
    if _lack_cleared(view, opp):
        threat += 0.2
    # 晚巡
    if view.wall_remaining <= _LATE_WALL_THRESHOLD:
        threat += 0.2
    return max(0.0, min(1.0, threat))
