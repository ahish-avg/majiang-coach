"""Action 类型 + 合法动作生成(含缺门约束)。

Action 为判别联合(单 frozen dataclass + kind 判别):
  Discard(tile) | Pon(src,tile) | Ankan(tile) | Daiminkan(src,tile)
  | Shouminkan(tile) | Tsumo(tile) | Ron(src,tile) | RonKan(src,tile)
  | Pass | Swap(t1,t2,t3) | Lack(suit)

合法动作生成遵循血战规则:
  - 缺门约束:手中有缺门牌时,弃牌阶段只能打缺门牌;缺门牌不可碰/杠/胡。
  - 杠(暗杠/补杠/大明杠)需牌墙有杠尾可摸(wall_remaining >= 1)。
  - ron = 摸入弃牌后 win() 成立;缺门牌弃牌不可 ron。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .. import tiles
from ..hand import Hand
from ..win import win
from .melds import Meld
from .view import PlayerView

__all__ = [
    "Action",
    "discard",
    "pon",
    "ankan",
    "daiminkan",
    "shouminkan",
    "tsumo",
    "ron",
    "ronkan",
    "pass_action",
    "swap",
    "lack_action",
    "legal_discards",
    "legal_claims",
    "legal_self_actions",
    "DRAW_KINDS",
    "CLAIM_KINDS",
    "TURN_KINDS",
]

ActionKind = Literal[
    "discard", "pon", "ankan", "daiminkan", "shouminkan",
    "tsumo", "ron", "ronkan", "pass", "swap", "lack",
]

DRAW_KINDS = ("discard", "ankan", "shouminkan", "tsumo")
CLAIM_KINDS = ("pon", "daiminkan", "ron")
TURN_KINDS = DRAW_KINDS  # 自家摸牌后可选动作种类


@dataclass(frozen=True)
class Action:
    """一个动作(判别联合)。

    kind 决定哪些字段有效:
      discard/ankan/shouminkan/tsumo -> tile
      pon/daiminkan/ron/ronkan      -> tile + src(弃牌来源座)
      pass                           -> (无)
      swap                           -> tiles=(t1,t2,t3)
      lack                           -> suit
    """

    kind: ActionKind
    tile: int | None = None
    src: int | None = None
    tiles: tuple[int, int, int] | None = None
    suit: int | None = None


# ---- 构造助手 ----

def discard(tile: int) -> Action:
    return Action("discard", tile=tile)


def pon(src: int, tile: int) -> Action:
    return Action("pon", tile=tile, src=src)


def ankan(tile: int) -> Action:
    return Action("ankan", tile=tile)


def daiminkan(src: int, tile: int) -> Action:
    return Action("daiminkan", tile=tile, src=src)


def shouminkan(tile: int) -> Action:
    return Action("shouminkan", tile=tile)


def tsumo(tile: int) -> Action:
    return Action("tsumo", tile=tile)


def ron(src: int, tile: int) -> Action:
    return Action("ron", tile=tile, src=src)


def ronkan(src: int, tile: int) -> Action:
    return Action("ronkan", tile=tile, src=src)


def pass_action() -> Action:
    return Action("pass")


def swap(t1: int, t2: int, t3: int) -> Action:
    return Action("swap", tiles=(t1, t2, t3))


def lack_action(suit: int) -> Action:
    return Action("lack", suit=suit)


# ---- 合法动作生成 ----

def legal_discards(view: PlayerView) -> list[int]:
    """合法弃牌索引列表。

    缺门优先:手中仍有缺门牌时,只能弃缺门牌;否则可弃任意手中牌。
    """
    hand = view.hand
    lack = view.lack_suit
    if lack is not None:
        base = lack * 9
        lack_tiles = [i for i in range(base, base + 9) if hand.count(i) > 0]
        if lack_tiles:
            return lack_tiles
    return [i for i in range(tiles.NUM_TILES) if hand.count(i) > 0]


def legal_claims(view: PlayerView, last_tile: int) -> list[Action]:
    """针对 last_tile(他人弃牌)的合法申索列表。

    返回 pon/daiminkan/ron(按此顺序);无申索返回 []。
    缺门牌不可申索;大明杠需牌墙有杠尾。
    """
    lack = view.lack_suit
    # 缺门牌不可碰/杠/胡
    if lack is not None and tiles.suit_of(last_tile) == lack:
        return []

    src = view.last_discard[0] if view.last_discard is not None else None
    hand = view.hand
    cnt = hand.count(last_tile)
    actions: list[Action] = []

    # 碰:手中 >= 2 张
    if cnt >= 2:
        actions.append(pon(src, last_tile))  # type: ignore[arg-type]
    # 大明杠:手中 >= 3 张(暗刻)且牌墙有杠尾
    if cnt >= 3 and view.wall_remaining >= 1:
        actions.append(daiminkan(src, last_tile))  # type: ignore[arg-type]
    # 点炮胡:摸入 last_tile 后 win()
    if _can_ron(hand, lack, view.meld_count, last_tile):
        actions.append(ron(src, last_tile))  # type: ignore[arg-type]

    return actions


def legal_self_actions(view: PlayerView, drawn: int | None) -> list[Action]:
    """自家摸牌后(或碰后)的合法动作列表。

    drawn 为摸到的牌索引(碰后为 None -> 仅可弃牌)。
    返回顺序:tsumo, ankan, shouminkan, discard...。
    """
    hand = view.hand
    lack = view.lack_suit
    meld_count = view.meld_count
    actions: list[Action] = []

    if drawn is not None:
        # 自摸:暗手(含 drawn)win()
        if win(hand, lack, meld_count):
            actions.append(tsumo(drawn))
        # 暗杠:手中 4 张同牌(非缺门)且牌墙有杠尾
        if view.wall_remaining >= 1:
            for idx in range(tiles.NUM_TILES):
                if hand.count(idx) == 4:
                    if lack is not None and tiles.suit_of(idx) == lack:
                        continue
                    actions.append(ankan(idx))
            # 补杠:已有碰 + 手中有该牌(摸到第 4 张)且牌墙有杠尾
            for m in view.melds:
                if m.kind == "pon" and hand.count(m.tile) >= 1:
                    actions.append(shouminkan(m.tile))

    # 弃牌(始终可选,除非自摸——但自摸时也可选择不胡而弃牌?血战能胡必胡,
    # 此处仍列出弃牌供 Actor;RandomActor 会优先 tsumo)
    for idx in legal_discards(view):
        actions.append(discard(idx))

    return actions


def _can_ron(hand: Hand, lack: int | None, meld_count: int, tile: int) -> bool:
    """摸入 tile 后是否胡牌(点炮)。"""
    try:
        new_hand = hand.add(tile)
    except ValueError:
        return False
    return win(new_hand, lack, meld_count)
