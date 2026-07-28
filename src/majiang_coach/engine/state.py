"""GameState:完整可回放状态(4 座暗手/副露/弃牌/缺门/在局/牌墙/回合)。

可变 dataclass(暗手 Hand 本身不可变,状态机通过替换 Hand 实例推进)。
make_view() 构造信息隔离的 PlayerView(不含他家暗手)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..hand import Hand
from .melds import Meld
from .view import PlayerView
from .wall import TileWall

__all__ = ["GameState"]


@dataclass
class GameState:
    """一局血战到底的完整运行时状态。"""

    seed: int
    wall: TileWall
    hands: list[Hand] = field(default_factory=lambda: [Hand.empty() for _ in range(4)])
    melds: list[list[Meld]] = field(default_factory=lambda: [[] for _ in range(4)])
    discards: list[list[int]] = field(default_factory=lambda: [[] for _ in range(4)])
    lack: list[int | None] = field(default_factory=lambda: [None, None, None, None])
    active: list[bool] = field(default_factory=lambda: [True, True, True, True])
    turn: int = 0
    dealer: int = 0
    swap_direction: str | None = None
    last_discard: tuple[int, int] | None = None  # (src_seat, tile)
    winners: list[int] = field(default_factory=list)
    # 每位赢家详情:{seat, by, tile, from_seat, hand_codes, melds, lack, robbery}
    win_details: list[dict] = field(default_factory=list)

    @classmethod
    def new(cls, seed: int) -> "GameState":
        return cls(seed=seed, wall=TileWall(seed), turn=0, dealer=0)

    # ---- 座次 / 终局 ----

    def next_active(self, seat: int) -> int:
        """从 seat 起逆时针(递增)的下一个在局座。"""
        for offset in range(1, 5):
            s = (seat + offset) % 4
            if self.active[s]:
                return s
        return seat

    def active_seats(self) -> list[int]:
        return [s for s in range(4) if self.active[s]]

    def is_over(self) -> bool:
        """3 家胡 -> 终局。"""
        return len(self.winners) >= 3

    # ---- 信息隔离视图 ----

    def make_view(self, seat: int) -> PlayerView:
        """构造 seat 的可见视图(不含他家暗手)。"""
        return PlayerView(
            seat=seat,
            hand=self.hands[seat],
            melds=tuple(self.melds[seat]),
            lack_suit=self.lack[seat],
            lack_suits=tuple(self.lack),  # 4 座公开缺门(标准血战缺门公开)
            discards=tuple(tuple(d) for d in self.discards),
            public_melds=tuple(tuple(m) for m in self.melds),
            wall_remaining=self.wall.remaining(),
            turn=self.turn,
            last_discard=self.last_discard,
            active_seats=tuple(self.active_seats()),
            winners=tuple(self.winners),
        )

    # ---- 张数守恒(调试/断言用)----

    def total_tiles(self) -> int:
        """场上所有牌张数(应恒为 108)。"""
        total = self.wall.remaining()
        for s in range(4):
            total += self.hands[s].total
            for m in self.melds[s]:
                total += m.tile_count
            total += len(self.discards[s])
        return total
