"""综合推荐 analyze(view, weights=None) -> AnalysisResult(Phase 3 核心,见计划 §5/§6)。

纯函数:输入一个座位视角 PlayerView,输出结构化 JSON 就绪的分析结果。
  - 刚摸态(14-3*melds,待弃):对每张合法弃牌算 offense_after + 安全度 + 综合,产出
    candidates 与 recommend(综合最高,平手按 tile 升序);并标 best_offense/best_defense。
  - 待摸态(13-3*melds,轮别人):仅输出 hand + 可选 claim(有 last_discard 时)。
  - 候选复用 engine.action.legal_discards(尊重缺门约束:有缺门牌时只列缺门牌)。
  - composite = w_off*offense + w_def*defense,默认 0.6/0.4(可调,经 weights 传入),
    weights_used 回传实际权重。
  - claim(§6.8):can_ron=win(hand+last,lack,melds);can_pon 排除缺门;pon_shanten_after
    = shanten(碰后暗手,lack,melds+1)(走刚摸态路径)。
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import tiles
from ..win import win
from ..shanten import shanten
from ..engine.melds import Meld
from ..engine.view import PlayerView
from ..engine.action import legal_discards
from ..engine.record import make_meld_dict, meld_from_dict
from .offense import Offense, UkeireWait, offense_of
from .safety import OpponentDanger, safety_of

__all__ = ["Candidate", "AnalysisResult", "analyze"]

_DEFAULT_WEIGHTS = {"offense": 0.6, "defense": 0.4}


@dataclass(frozen=True)
class Candidate:
    """一张可弃牌的综合指标。"""

    tile: int
    code: str
    shanten_after: int
    is_tenpai_after: bool
    ukeire: list[UkeireWait]
    ukeire_count: int
    ukeire_remaining_total: int
    offense_score: int
    danger: int
    defense_score: int
    composite_score: int
    safety_reasons: list[str]
    per_opponent: list[OpponentDanger]

    def to_dict(self) -> dict:
        return {
            "tile": self.tile,
            "code": self.code,
            "shanten_after": self.shanten_after,
            "is_tenpai_after": self.is_tenpai_after,
            "ukeire": [u.to_dict() for u in self.ukeire],
            "ukeire_count": self.ukeire_count,
            "ukeire_remaining_total": self.ukeire_remaining_total,
            "offense_score": self.offense_score,
            "danger": self.danger,
            "defense_score": self.defense_score,
            "composite_score": self.composite_score,
            "safety_reasons": list(self.safety_reasons),
            "per_opponent": [o.to_dict() for o in self.per_opponent],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(
            tile=d["tile"],
            code=d["code"],
            shanten_after=d["shanten_after"],
            is_tenpai_after=d["is_tenpai_after"],
            ukeire=[UkeireWait.from_dict(u) for u in d["ukeire"]],
            ukeire_count=d["ukeire_count"],
            ukeire_remaining_total=d["ukeire_remaining_total"],
            offense_score=d["offense_score"],
            danger=d["danger"],
            defense_score=d["defense_score"],
            composite_score=d["composite_score"],
            safety_reasons=list(d["safety_reasons"]),
            per_opponent=[OpponentDanger.from_dict(o) for o in d["per_opponent"]],
        )


@dataclass(frozen=True)
class AnalysisResult:
    """一次分析的结构化结果。"""

    seat: int
    hand_total: int
    lack_suit: int | None
    melds: tuple[Meld, ...]
    weights_used: dict
    hand: Offense
    candidates: list[Candidate]
    recommend: Candidate | None
    best_offense: Candidate | None
    best_defense: Candidate | None
    claim: dict | None

    def to_dict(self) -> dict:
        return {
            "seat": self.seat,
            "hand_total": self.hand_total,
            "lack_suit": self.lack_suit,
            "melds": [make_meld_dict(m) for m in self.melds],
            "weights_used": dict(self.weights_used),
            "hand": self.hand.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "recommend": self.recommend.to_dict() if self.recommend else None,
            "best_offense": self.best_offense.to_dict() if self.best_offense else None,
            "best_defense": self.best_defense.to_dict() if self.best_defense else None,
            "claim": dict(self.claim) if self.claim else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        return cls(
            seat=d["seat"],
            hand_total=d["hand_total"],
            lack_suit=d["lack_suit"],
            melds=tuple(meld_from_dict(m) for m in d["melds"]),
            weights_used=dict(d["weights_used"]),
            hand=Offense.from_dict(d["hand"]),
            candidates=[Candidate.from_dict(c) for c in d["candidates"]],
            recommend=Candidate.from_dict(d["recommend"]) if d["recommend"] else None,
            best_offense=Candidate.from_dict(d["best_offense"]) if d["best_offense"] else None,
            best_defense=Candidate.from_dict(d["best_defense"]) if d["best_defense"] else None,
            claim=dict(d["claim"]) if d["claim"] else None,
        )


def _resolve_weights(weights: dict | None) -> dict:
    w_off = _DEFAULT_WEIGHTS["offense"]
    w_def = _DEFAULT_WEIGHTS["defense"]
    if weights:
        w_off = weights.get("offense", w_off)
        w_def = weights.get("defense", w_def)
    return {"offense": w_off, "defense": w_def}


def _compute_claim(view: PlayerView, lack: int | None, melds: int) -> dict | None:
    """待摸态下针对 last_discard 的申索信息(§6.8,信息性)。"""
    if view.last_discard is None:
        return None
    last_tile = view.last_discard[1]
    # can_ron:摸入 last_tile 后 win()(win 内置缺门检查)
    try:
        ron_hand = view.hand.add(last_tile)
        can_ron = win(ron_hand, lack, melds)
    except ValueError:
        can_ron = False
    # can_pon:非缺门 且 手中 >= 2 张
    lack_ok = not (lack is not None and tiles.suit_of(last_tile) == lack)
    cnt = view.hand.count(last_tile)
    can_pon = lack_ok and cnt >= 2
    # pon_shanten_after:碰后暗手去 2 张该牌 -> 刚摸态(melds+1),走弃一张取最优
    pon_shanten_after: int | None = None
    if can_pon:
        try:
            pon_hand = view.hand.remove(last_tile).remove(last_tile)
            pon_shanten_after = shanten(pon_hand, lack, melds + 1)
        except ValueError:
            pon_shanten_after = None
    return {
        "tile_index": last_tile,
        "code": tiles.index_to_code(last_tile),
        "can_ron": can_ron,
        "can_pon": can_pon,
        "pon_shanten_after": pon_shanten_after,
    }


def analyze(view: PlayerView, weights: dict | None = None) -> AnalysisResult:
    """纯函数:同一 view 必产出同一结果。"""
    w = _resolve_weights(weights)
    melds_count = view.meld_count
    lack = view.lack_suit

    expected_draw = 14 - 3 * melds_count  # 刚摸态(待弃)
    expected_wait = 13 - 3 * melds_count  # 待摸态(轮别人)

    hand_offense = offense_of(view.hand, lack, melds_count, view)

    candidates: list[Candidate] = []
    recommend: Candidate | None = None
    best_offense: Candidate | None = None
    best_defense: Candidate | None = None
    claim: dict | None = None

    if view.hand.total == expected_draw:
        # 刚摸态(待弃):逐合法弃牌分析
        for d in legal_discards(view):
            resulting = view.hand.remove(d)
            off = offense_of(resulting, lack, melds_count, view)
            saf = safety_of(d, view)
            composite = w["offense"] * off.score + w["defense"] * saf.defense_score
            candidates.append(Candidate(
                tile=d,
                code=tiles.index_to_code(d),
                shanten_after=off.shanten,
                is_tenpai_after=off.is_tenpai,
                ukeire=off.ukeire,
                ukeire_count=off.ukeire_count,
                ukeire_remaining_total=off.ukeire_remaining_total,
                offense_score=off.score,
                danger=saf.danger,
                defense_score=saf.defense_score,
                composite_score=round(composite),
                safety_reasons=saf.reasons,
                per_opponent=saf.per_opponent,
            ))
        # 综合降序,平手按 tile 升序(确定性)
        candidates.sort(key=lambda c: (-c.composite_score, c.tile))
        if candidates:
            recommend = candidates[0]
            best_offense = max(candidates, key=lambda c: (c.offense_score, -c.tile))
            best_defense = max(candidates, key=lambda c: (c.defense_score, -c.tile))
    elif view.hand.total == expected_wait:
        # 待摸态(轮别人):仅 hand + 可选 claim
        claim = _compute_claim(view, lack, melds_count)

    return AnalysisResult(
        seat=view.seat,
        hand_total=view.hand.total,
        lack_suit=lack,
        melds=view.melds,
        weights_used=w,
        hand=hand_offense,
        candidates=candidates,
        recommend=recommend,
        best_offense=best_offense,
        best_defense=best_defense,
        claim=claim,
    )
