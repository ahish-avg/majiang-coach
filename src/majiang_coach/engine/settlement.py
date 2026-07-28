"""结算桩:记录胡牌事件与算番所需事实(不算番数/分数)。

Phase 2 只记录 result(winners/losers/hand/melds/lack/花猪标志);
番种识别/番数累加/分数结算推迟到后续"番种结算"阶段。

花猪(huazhu)= 未胡且终局仍持三门牌(缺门未清)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import tiles
from .melds import Meld
from .record import make_meld_dict
from .state import GameState

__all__ = ["build_result", "WinnerInfo", "LoserInfo", "GameResult"]


@dataclass
class WinnerInfo:
    seat: int
    by: str  # "tsumo" | "ron"
    tile: int
    from_seat: int | None
    robbery: bool
    hand: list[int]
    melds: list[Meld]
    lack: int | None


@dataclass
class LoserInfo:
    seat: int
    hand: list[int]
    melds: list[Meld]
    lack: int | None
    huazhu: bool


@dataclass
class GameResult:
    winners: list[dict] = field(default_factory=list)
    losers: list[dict] = field(default_factory=list)
    drawn: bool = False

    def to_dict(self) -> dict:
        return {
            "winners": self.winners,
            "losers": self.losers,
            "drawn": self.drawn,
        }


def build_result(state: GameState, drawn: bool) -> GameResult:
    """从终局状态构建结算结果(不算番)。"""
    result = GameResult(drawn=drawn)

    # 赢家(按胡牌顺序)
    for wd in state.win_details:
        hand_idx = wd["hand"]
        melds_list: list[Meld] = wd["melds"]
        result.winners.append({
            "seat": wd["seat"],
            "by": wd["by"],
            "tile": tiles.index_to_code(wd["tile"]),
            "from": wd["from"],
            "hand": [tiles.index_to_code(i) for i in hand_idx],
            "melds": [make_meld_dict(m) for m in melds_list],
            "lack": wd["lack"],
            "robbery": wd["robbery"],
        })

    # 输家(未胡者)
    for s in range(4):
        if s in state.winners:
            continue
        hand = state.hands[s]
        melds_s = state.melds[s]
        lack = state.lack[s]
        huazhu = len(hand.suits_present()) >= 3
        result.losers.append({
            "seat": s,
            "hand": hand.to_codes(),
            "melds": [make_meld_dict(m) for m in melds_s],
            "lack": lack,
            "huazhu": huazhu,
        })

    return result
