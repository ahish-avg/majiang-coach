"""动作优先级裁定:ron>碰/杠、一炮多响、碰/杠座次冲突、抢杠时机。

纯函数,不持有状态。由 Game 主循环在申索阶段调用。

座次逆时针(0→1→2→3→0);"离出牌者最近逆时针"即从 discarder 起递增取首个申索者。
"""

from __future__ import annotations

from typing import Literal

from .. import tiles
from ..hand import Hand
from ..win import win
from .action import Action

__all__ = ["nearest_claimer", "resolve_claims", "robbery_targets", "ClaimResult"]

ClaimResult = Literal["ron", "claim", "pass"]


def nearest_claimer(discarder: int, claimer_seats: list[int]) -> int:
    """离 discarder 最近(逆时针/递增)的申索者座号。"""
    for offset in range(1, 5):
        seat = (discarder + offset) % 4
        if seat in claimer_seats:
            return seat
    raise ValueError(f"no claimer among {claimer_seats} from discarder {discarder}")


def resolve_claims(
    discarder: int, choices: list[tuple[int, Action]]
) -> tuple[str, object]:
    """裁定申索结果。

    Args:
        discarder: 弃牌者座号。
        choices: 各座的选择 (seat, Action),含 pass。

    Returns:
        ("ron", [winner_seats])  — 一炮多响:所有 ron 者都胡。
        ("claim", seat, Action)  — 单一碰/大明杠申索者(最近座)。
        ("pass",)                — 无人申索。
    """
    rons = [(s, a) for s, a in choices if a.kind == "ron"]
    if rons:
        return ("ron", [s for s, _ in rons])
    claims = [(s, a) for s, a in choices if a.kind in ("pon", "daiminkan")]
    if claims:
        seats = [s for s, _ in claims]
        near = nearest_claimer(discarder, seats)
        act = next(a for s, a in claims if s == near)
        return ("claim", near, act)
    return ("pass",)


def robbery_targets(
    others: list[tuple[int, Hand, int | None, int]],
    tile: int,
) -> list[int]:
    """抢杠胡目标:补杠(shouminkan)时,哪些他家可 ron 该补杠牌。

    Args:
        others: list of (seat, hand, lack_suit, meld_count) for active non-declarer players。
        tile: 被补杠的牌索引。

    Returns:
        可抢杠的座号列表(均 ron,一炮多响)。
    """
    targets: list[int] = []
    for seat, hand, lack, meld_count in others:
        if lack is not None and tiles.suit_of(tile) == lack:
            continue  # 缺门牌不可胡
        try:
            if win(hand.add(tile), lack, meld_count):
                targets.append(seat)
        except ValueError:
            continue
    return targets
