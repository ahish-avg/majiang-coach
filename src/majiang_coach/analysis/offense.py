"""进攻期望 offense_of(hand, lack, melds, view) -> Offense(Phase 3,见计划 §6.6)。

进张期望(无番):弃某牌后手牌的差张下叫 + 进张张数 + 进张未见张数。番加权 EV 留番种阶段。

score = base[shanten] + 3*len(live进张) + 1*sum(remaining[t] for t in live),clamp 0..100
  - base:下叫(0)->50 / 差1->25 / 差2->12 / 差3->5;已胡(-1)->100;更深用 5。
  - live = ukeire 中 remaining>0 的牌(死待不计,防进攻分虚高)。
is_tenpai = (shanten==0);下叫时 ukeire = 叫牌(待胡牌)。

hand 须为待摸态(13-3*melds)才能算 ukeire;刚摸态(14-3*melds)传进来时 ukeire 为空
(仅给 shanten/score 快照,详细进张见各弃牌候选)。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..hand import Hand
from ..engine.view import PlayerView
from ..shanten import shanten
from ..ukeire import ukeire
from .visible import remaining_counts

__all__ = ["UkeireWait", "Offense", "offense_of"]

_BASE = {0: 50, 1: 25, 2: 12, 3: 5}


@dataclass(frozen=True)
class UkeireWait:
    """一张进张(待胡/改善牌),含未见张数(牌墙+他家暗手)。"""

    tile_index: int
    code: str
    new_shanten: int
    remaining: int  # 未见张=4-visible(牌墙+他家暗手);0=死待

    def to_dict(self) -> dict:
        return {
            "tile_index": self.tile_index,
            "code": self.code,
            "new_shanten": self.new_shanten,
            "remaining": self.remaining,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UkeireWait":
        return cls(
            tile_index=d["tile_index"],
            code=d["code"],
            new_shanten=d["new_shanten"],
            remaining=d["remaining"],
        )


@dataclass(frozen=True)
class Offense:
    """一手牌的进攻期望快照。"""

    score: int
    shanten: int
    is_tenpai: bool
    ukeire: list[UkeireWait]
    ukeire_count: int
    ukeire_remaining_total: int

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "shanten": self.shanten,
            "is_tenpai": self.is_tenpai,
            "ukeire": [u.to_dict() for u in self.ukeire],
            "ukeire_count": self.ukeire_count,
            "ukeire_remaining_total": self.ukeire_remaining_total,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Offense":
        return cls(
            score=d["score"],
            shanten=d["shanten"],
            is_tenpai=d["is_tenpai"],
            ukeire=[UkeireWait.from_dict(u) for u in d["ukeire"]],
            ukeire_count=d["ukeire_count"],
            ukeire_remaining_total=d["ukeire_remaining_total"],
        )


def offense_of(
    resulting_hand: Hand,
    lack: int | None,
    melds: int,
    view: PlayerView,
) -> Offense:
    """计算 resulting_hand 的进攻期望。

    resulting_hand 通常为弃某牌后的待摸态暗手(13-3*melds);刚摸态也可传入(ukeire 为空)。
    """
    s = shanten(resulting_hand, lack, melds)
    is_tenpai = (s == 0)
    rem = remaining_counts(view)

    expected_wait = 13 - 3 * melds  # 待摸态(ukeire 输入要求)
    if resulting_hand.total == expected_wait:
        raw_u = ukeire(resulting_hand, lack, melds)
        u = [
            UkeireWait(t.tile_index, t.code, t.new_shanten, rem[t.tile_index])
            for t in raw_u
        ]
    else:
        u = []  # 刚摸态:无单一 ukeire,留给候选

    live = [t for t in u if t.remaining > 0]
    ukeire_remaining_total = sum(t.remaining for t in u)

    if s == -1:
        score = 100
    else:
        base = _BASE.get(s, 5)
        score = base + 3 * len(live) + ukeire_remaining_total
    score = max(0, min(100, score))

    return Offense(
        score=score,
        shanten=s,
        is_tenpai=is_tenpai,
        ukeire=list(u),
        ukeire_count=len(u),
        ukeire_remaining_total=ukeire_remaining_total,
    )
