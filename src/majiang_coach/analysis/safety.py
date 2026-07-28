"""安全度 safety_of(tile, view) -> Safety(Phase 3,见计划 §6.3 / §6.5)。

输出 0-100 危险度 + 川麻理由 + 逐对手明细。0=安全 100=极险。

硬规则:
  - 未见张(remaining)==0 -> 绝对安全(danger 0)。
  - 对手缺门牌对该对手绝对安全(d_o=0)。
  - 壁(绝张墙,§6.3):候选弃牌 X 的待胡形状伙伴牌全壁/半壁 -> 削弱危险度。
软信号(弱,均不构成硬安全):
  - 筋(1-4-7/2-5-8/3-6-9 关联)×0.7。
  - 现物(曾打出未放炮)×0.8。**川麻无振听,现物非硬安全**(remaining>0 时 danger 仍 >0)。
  - 早/晚巡:早×0.7 / 晚×1.2。
逐对手 o(在局、非己)危险度:
  d_o = base(15*remaining) × kabe系数 × 筋系数 × 现物系数 × 巡目系数 × (0.5+0.5*threat_o)
  (tile 属 o 缺门时 d_o=0)
danger = max_o d_o(取最危险对手,保守);defense_score = 100 - danger。
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import tiles
from ..engine.view import PlayerView
from .threat import opp_lack, opponent_threat
from .visible import visible_counts, remaining_counts

__all__ = ["OpponentDanger", "Safety", "safety_of", "seat_relative_name"]

_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}

# 巡目系数阈值
_EARLY_WALL = 40   # wall_remaining >= 此值 -> 早巡(×0.7)
_LATE_WALL = 20    # wall_remaining <= 此值 -> 晚巡(×1.2)


@dataclass(frozen=True)
class OpponentDanger:
    """单个对手对该弃牌的危险度明细。"""

    seat: int
    danger: int
    lack: int | None
    threat: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "seat": self.seat,
            "danger": self.danger,
            "lack": self.lack,
            "threat": self.threat,
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OpponentDanger":
        return cls(
            seat=d["seat"],
            danger=d["danger"],
            lack=d["lack"],
            threat=d["threat"],
            reasons=list(d["reasons"]),
        )


@dataclass(frozen=True)
class Safety:
    """一张弃牌的安全度评估。danger=0 安全,100 极险。"""

    danger: int
    defense_score: int
    reasons: list[str]
    per_opponent: list[OpponentDanger]


def seat_relative_name(self_seat: int, opp: int) -> str:
    """对手相对自家称谓(川麻口语):1=下家 2=对家 3=上家。"""
    diff = (opp - self_seat) % 4
    return {1: "下家", 2: "对家", 3: "上家"}.get(diff, f"座{opp}")


def _base_danger(remaining: int) -> float:
    """未见张 -> 基础危险度:4->60 / 3->45 / 2->30 / 1->15(=15*remaining)。"""
    return 15.0 * remaining


def _kabe_shapes(tile: int) -> list[tuple[int, int]]:
    """tile 作为叫牌(待胡)的非单吊待胡形状的伙伴对。

    返回 [(p1, p2), ...] 仅含 1-9 边界内合法形状:
      [X-2,X-1](待 X 与 X-3) / [X+1,X+2](待 X 与 X+3) / [X-1,X+1](卡张待 X)
    """
    suit = tiles.suit_of(tile)
    n = tiles.number_of(tile)  # 1..9
    base = suit * 9
    shapes: list[tuple[int, int]] = []
    if n >= 3:  # X-2, X-1
        shapes.append((tile - 2, tile - 1))
    if n <= 7:  # X+1, X+2
        shapes.append((tile + 1, tile + 2))
    if 2 <= n <= 8:  # X-1, X+1(卡张)
        shapes.append((tile - 1, tile + 1))
    return shapes


def _kabe_coef(tile: int, vis: list[int]) -> float:
    """壁系数(§6.3):死亡形状越多,弃该牌越安全(系数越小)。

    死亡形状数 = 各非单吊形状按(全壁=1.0 / 半壁=0.5 / 否则0)计和。
    kabe = 1 - 0.5 * (死亡形状数 / 非单吊形状数);无形状时 = 1(避免除零)。
    """
    shapes = _kabe_shapes(tile)
    n = len(shapes)
    if n == 0:
        return 1.0
    death = 0.0
    for p1, p2 in shapes:
        if vis[p1] == 4 or vis[p2] == 4:
            death += 1.0
        elif vis[p1] == 3 or vis[p2] == 3:
            death += 0.5
    return 1.0 - 0.5 * (death / n)


def _suji_coef(tile: int, opp_discards: tuple[int, ...]) -> float:
    """筋系数(弱软信号):tile 为某筋组的边牌且对手弃过该组中张 -> ×0.7。

    筋组:1-4-7(中张4) / 2-5-8(中张5) / 3-6-9(中张6)。边牌 1,7/2,8/3,9 适用;
    中张 4,5,6 本身无筋削弱(v0)。
    """
    n = tiles.number_of(tile)
    center_number = {1: 4, 7: 4, 2: 5, 8: 5, 3: 6, 9: 6}.get(n)
    if center_number is None:
        return 1.0
    center_idx = tiles.suit_of(tile) * 9 + (center_number - 1)
    if center_idx in opp_discards:
        return 0.7
    return 1.0


def _turn_coef(wall_remaining: int) -> float:
    """巡目系数:早巡×0.7 / 晚巡×1.2 / 中巡×1.0。"""
    if wall_remaining >= _EARLY_WALL:
        return 0.7
    if wall_remaining <= _LATE_WALL:
        return 1.2
    return 1.0


def _opponents(view: PlayerView) -> list[int]:
    """在局、非己的对手座列表。"""
    return [s for s in view.active_seats if s != view.seat]


def safety_of(tile: int, view: PlayerView) -> Safety:
    """评估弃 tile 的安全度。"""
    vis = visible_counts(view)
    rem = remaining_counts(view)
    remaining = rem[tile]

    # 绝对安全:未见张为0(全壁,他家不可能持/摸该牌)
    if remaining <= 0:
        return Safety(
            danger=0,
            defense_score=100,
            reasons=["未见张为0,绝对安全(全壁)"],
            per_opponent=[],
        )

    base = _base_danger(remaining)
    kabe = _kabe_coef(tile, vis)
    turn = _turn_coef(view.wall_remaining)

    per: list[OpponentDanger] = []
    max_d = 0.0
    reasons: list[str] = []
    for opp in _opponents(view):
        L = opp_lack(view, opp)
        name = seat_relative_name(view.seat, opp)
        th = opponent_threat(view, opp)
        if L is not None and tiles.suit_of(tile) == L:
            d_o = 0.0
            r = [f"{name}缺{_SUIT_NAME[L]},对其绝对安全"]
        else:
            suji = _suji_coef(tile, view.discards[opp])
            gen = 0.8 if tile in view.discards[opp] else 1.0
            d_o = base * kabe * suji * gen * turn * (0.5 + 0.5 * th)
            r = []
            if gen < 1.0:
                r.append(f"{name}曾打出此牌(现物),稍安全(非硬安全)")
            else:
                r.append(f"{name}未打过此牌")
            if suji < 1.0:
                r.append("筋牌,稍安全")
            if kabe < 1.0:
                r.append("有壁(绝张墙),削弱待胡形状")
        per.append(OpponentDanger(opp, round(d_o), L, round(th, 3), r))
        if d_o > max_d:
            max_d = d_o

    danger = round(max_d)
    if remaining == 4:
        reasons.append("未见张4(满),无任何削弱")
    if kabe < 1.0:
        reasons.append("存在壁(绝张墙),危险度下调")
    if danger == 0:
        reasons.append("对所有在局对手均绝对安全(缺门/全壁)")

    return Safety(
        danger=danger,
        defense_score=100 - danger,
        reasons=reasons,
        per_opponent=per,
    )
