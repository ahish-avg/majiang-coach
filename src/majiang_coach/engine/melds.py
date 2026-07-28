"""Meld:副露(碰/杠)数据类与助手。

血战到底 Phase 2 副露只含碰与杠(无吃):
  - pon(碰):3 张同牌(手中 2 + 弃牌 1),src_seat=弃牌者。
  - ankan(暗杠):4 张同牌(手中 4),src_seat=None。
  - daiminkan(大明杠):4 张同牌(手中 3 + 弃牌 1),src_seat=弃牌者。
  - shouminkan(补杠/加杠):已有碰,摸到第 4 张加入,src_seat=None。

每副露计 1 个 meld(杠虽 4 张仍计 1)。杠后杠尾补摸,暗手张数恒为 14-3*melds。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .. import tiles

__all__ = ["Meld", "MELD_KINDS", "is_kan", "meld_tile_count"]

MeldKind = Literal["pon", "ankan", "daiminkan", "shouminkan"]
MELD_KINDS = ("pon", "ankan", "daiminkan", "shouminkan")


@dataclass(frozen=True)
class Meld:
    """一副固定副露。

    Attributes:
        kind: pon/ankan/daiminkan/shouminkan。
        tile: 该副露的牌索引(碰/杠均为同牌)。
        src_seat: 碰/大明杠来源座;暗杠/补杠为 None。
    """

    kind: MeldKind
    tile: int
    src_seat: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in MELD_KINDS:
            raise ValueError(f"Invalid meld kind: {self.kind!r}")
        if not isinstance(self.tile, int) or not (0 <= self.tile < tiles.NUM_TILES):
            raise ValueError(f"Invalid meld tile: {self.tile!r}")
        if self.src_seat is not None and self.src_seat not in (0, 1, 2, 3):
            raise ValueError(f"Invalid src_seat: {self.src_seat!r}")
        # 暗杠/补杠无来源座
        if self.kind in ("ankan", "shouminkan") and self.src_seat is not None:
            raise ValueError(f"{self.kind} meld must have src_seat=None")

    @property
    def is_kan(self) -> bool:
        return self.kind in ("ankan", "daiminkan", "shouminkan")

    @property
    def tile_count(self) -> int:
        """该副露占用牌张数(碰=3,杠=4)。"""
        return 4 if self.is_kan else 3


def is_kan(meld: Meld) -> bool:
    return meld.is_kan


def meld_tile_count(meld: Meld) -> int:
    return meld.tile_count
