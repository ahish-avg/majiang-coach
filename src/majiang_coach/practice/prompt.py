"""practice/prompt.py:提示构建 + PendingDecision + 序列化(Phase 5,见计划 §5/§8)。

PendingDecision:人类当前须决策的点(5 类:swap/lack/turn_action/claim/robbery),
携带人类视角 PlayerView + 合法动作 + advise(Phase 4 LLM,开提示)+ hint(Phase 3 硬算)。

build_prompt:组装传输用 JSON dict {session_id, phase, game_over, view, legal_actions,
advise, hint};game_over 时附 record + summary。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .. import tiles
from ..engine.action import Action
from ..engine.melds import Meld
from ..engine.record import GameRecord, make_meld_dict
from ..engine.view import PlayerView
from ..hand import Hand

__all__ = [
    "PendingDecision",
    "action_to_dict",
    "action_from_dict",
    "view_to_dict",
    "build_prompt",
    "summarize_record",
]

_SUIT_LETTER = {0: "m", 1: "s", 2: "p"}
_SUIT_INT = {"m": 0, "s": 1, "p": 2}


@dataclass
class PendingDecision:
    """人类当前须决策的点。"""

    kind: Literal["swap", "lack", "turn_action", "claim", "robbery"]
    view: PlayerView
    legal_actions: list[Action]
    advise: dict | None = None       # AdviseResult.to_dict()(开提示且配置可用);纯实战 None
    hint: dict | None = None         # Phase 3 硬算提示
    drawn: int | None = None         # turn_action:本回合摸到的牌索引(碰后 None)
    # claim 恢复上下文:discarder/tile/已收 AI 选择
    claim_ctx: dict | None = None
    # robbery 恢复上下文:declarer/tile/已自动抢杠的 AI 座
    robbery_ctx: dict | None = None


# ---- Action 序列化 ----

def action_to_dict(a: Action) -> dict:
    """Action -> JSON dict(牌用字符串码,缺门用 m/s/p)。"""
    d: dict = {"kind": a.kind}
    if a.tile is not None:
        d["tile"] = tiles.index_to_code(a.tile)
    if a.src is not None:
        d["src"] = a.src
    if a.tiles is not None:
        d["tiles"] = [tiles.index_to_code(t) for t in a.tiles]
    if a.suit is not None:
        d["suit"] = _SUIT_LETTER[a.suit]
    return d


def action_from_dict(d: dict) -> Action:
    """JSON dict -> Action(牌码转索引)。"""
    kind = d["kind"]
    tile = tiles.code_to_index(d["tile"]) if d.get("tile") is not None else None
    src = d.get("src")
    tiles_t = None
    if d.get("tiles") is not None:
        tiles_t = tuple(tiles.code_to_index(t) for t in d["tiles"])
    suit = _SUIT_INT[d["suit"]] if d.get("suit") is not None else None
    return Action(kind=kind, tile=tile, src=src, tiles=tiles_t, suit=suit)


# ---- PlayerView 序列化 ----

def view_to_dict(view: PlayerView) -> dict:
    """PlayerView -> JSON dict(信息隔离:不含他家暗手)。"""
    return {
        "seat": view.seat,
        "hand": view.hand.to_codes(),
        "melds": [make_meld_dict(m) for m in view.melds],
        "lack_suit": _SUIT_LETTER[view.lack_suit] if view.lack_suit is not None else None,
        "lack_suits": [_SUIT_LETTER[l] if l is not None else None for l in view.lack_suits],
        "discards": [[tiles.index_to_code(t) for t in d] for d in view.discards],
        "public_melds": [[make_meld_dict(m) for m in seat] for seat in view.public_melds],
        "wall_remaining": view.wall_remaining,
        "turn": view.turn,
        "last_discard": (
            {"src": view.last_discard[0], "tile": tiles.index_to_code(view.last_discard[1])}
            if view.last_discard is not None else None
        ),
        "active_seats": list(view.active_seats),
        "winners": list(view.winners),
        "hand_total": view.hand_total,
        "meld_count": view.meld_count,
    }


# ---- 牌谱摘要 ----

def summarize_record(record: GameRecord) -> dict:
    """GameRecord -> 人类可读摘要(胡家/输家/流局)。"""
    result = record.result or {}
    return {
        "seed": record.meta.get("seed"),
        "swap_direction": record.meta.get("swap_direction"),
        "lack": [_SUIT_LETTER.get(l) for l in record.meta.get("lack", [])],
        "num_events": len(record.events),
        "winners": [
            {"seat": w["seat"], "by": w["by"], "tile": w["tile"],
             "from": w.get("from"), "robbery": w.get("robbery", False),
             "melds": len(w.get("melds", []))}
            for w in result.get("winners", [])
        ],
        "losers": [
            {"seat": l["seat"], "huazhu": l.get("huazhu", False),
             "melds": len(l.get("melds", []))}
            for l in result.get("losers", [])
        ],
        "drawn": result.get("drawn", False),
    }


# ---- prompt 组装 ----

def build_prompt(
    session_id: str,
    pending: PendingDecision | None,
    game_over: bool,
    record: GameRecord | None = None,
    summary: dict | None = None,
) -> dict:
    """组装传输用 prompt dict(见计划 §8)。"""
    if game_over or pending is None:
        prompt: dict = {
            "session_id": session_id,
            "phase": "game_over",
            "game_over": True,
            "view": None,
            "legal_actions": [],
            "advise": None,
            "hint": None,
        }
        if record is not None:
            prompt["record"] = record.to_dict()
        if summary is not None:
            prompt["summary"] = summary
        return prompt

    prompt = {
        "session_id": session_id,
        "phase": pending.kind,
        "game_over": False,
        "view": view_to_dict(pending.view),
        "legal_actions": [action_to_dict(a) for a in pending.legal_actions],
        "advise": pending.advise,
        "hint": pending.hint,
    }
    if pending.drawn is not None:
        prompt["drawn"] = tiles.index_to_code(pending.drawn)
    return prompt
