"""可见 / 未见张数(Phase 3 分析引擎基础)。

语义(钉死,见计划 §6.2):
  - visible[i] = 自家暗手 + 自家副露 + 全部弃牌 + 全部公开副露 中 i 的张数。
        **不含牌墙、不含他家暗手**。(全部公开副露已含自家,故不自家副露另计,避免重复。)
  - remaining[i] = 4 - visible[i] = **未见张 = 牌墙 + 他家暗手**(不是"只在牌墙")。
  - 恒等式:sum(visible) + sum(remaining) == 108(每牌 visible+remaining=4,共 27 牌)。

可见信息驱动安全度与进攻期望;未见张决定进张是否"活"(死待不计进攻分)。
"""

from __future__ import annotations

from .. import tiles
from ..engine.view import PlayerView

__all__ = ["visible_counts", "remaining_counts"]


def visible_counts(view: PlayerView) -> list[int]:
    """长度 27:各牌在可见区域(自家暗手/全部副露/全部弃牌)的张数。"""
    counts = [0] * tiles.NUM_TILES
    # 自家暗手
    hand_counts = view.hand.counts
    for i in range(tiles.NUM_TILES):
        counts[i] += hand_counts[i]
    # 全部公开副露(public_melds 已含全座,含自家,故不自家 melds 另计)
    for seat_melds in view.public_melds:
        for m in seat_melds:
            counts[m.tile] += m.tile_count
    # 全部弃牌
    for seat_discards in view.discards:
        for t in seat_discards:
            counts[t] += 1
    return counts


def remaining_counts(view: PlayerView) -> list[int]:
    """长度 27:未见张 = 4 - visible = 牌墙 + 他家暗手。

    未见张为 0 表示该牌已全壁(绝对安全);为正表示仍可能被摸/被他家持有。
    """
    vis = visible_counts(view)
    return [4 - v for v in vis]
