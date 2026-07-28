"""PlayerView:某座可见信息(信息隐藏,不含他家暗手)。

PlayerView 是 Actor 决策的唯一信息入口。它包含:
  - 自家暗手 hand(完整可见)。
  - 各座弃牌堆 discards(公开)、各座副露 public_melds(公开)。
  - 公共状态:wall_remaining、turn、last_discard(当前可申索的弃牌)、active_seats、winners。

不含任何他座暗手,确保信息隔离(为后续教练/LLM 视角奠定基础)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..hand import Hand
from .melds import Meld

__all__ = ["PlayerView"]


@dataclass(frozen=True)
class PlayerView:
    """某座可见的游戏视角快照。"""

    seat: int
    hand: Hand
    melds: tuple[Meld, ...] = ()
    lack_suit: int | None = None
    lack_suits: tuple[int | None, ...] = ()  # 4 座公开缺门(Phase 3);默认 () 向后兼容
    discards: tuple[tuple[int, ...], ...] = ((), (), (), ())
    public_melds: tuple[tuple[Meld, ...], ...] = ((), (), (), ())
    wall_remaining: int = 0
    turn: int = 0
    last_discard: tuple[int, int] | None = None  # (src_seat, tile)
    active_seats: tuple[int, ...] = (0, 1, 2, 3)
    winners: tuple[int, ...] = ()

    @property
    def meld_count(self) -> int:
        """自家副露数(碰/杠各计 1)。"""
        return len(self.melds)

    @property
    def hand_total(self) -> int:
        return self.hand.total
