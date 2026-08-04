"""事件应用纯函数(Phase 5 抽取,见计划 §3)。

将 Game 的 `_handle_*` 处理器抽为模块级纯函数,操作 (GameState, GameRecord, ...)
推进状态并追加事件。Game 委托调用(行为不变,Phase 2 牌谱逐事件一致);
PracticeSession 复用这些函数 + GameState,只重写循环控制(何时为人类暂停)。

纯函数 = 不持有可变外部状态、不调用 Actor;仅依据入参推进 state/record。
apply_shouminkan 需先查抢杠(robbery_targets),被抢返回 True(ron 成立,杠取消)。
"""

from __future__ import annotations

from .. import tiles
from .melds import Meld
from .record import GameRecord, make_meld_dict
from .rules import robbery_targets
from .state import GameState

__all__ = [
    "apply_discard",
    "apply_pon",
    "apply_ankan",
    "apply_daiminkan",
    "apply_tsumo",
    "apply_ron",
    "apply_shouminkan",
    "code_of",
    "codes_of",
]


def code_of(idx: int) -> str:
    return tiles.index_to_code(idx)


def codes_of(idxs) -> list[str]:
    return [tiles.index_to_code(i) for i in idxs]


def apply_discard(state: GameState, record: GameRecord, seat: int, tile: int) -> None:
    state.hands[seat] = state.hands[seat].remove(tile)
    state.discards[seat].append(tile)
    state.last_discard = (seat, tile)
    record.events.append({"t": "discard", "seat": seat, "tile": code_of(tile)})


def apply_pon(state: GameState, record: GameRecord,
              seat: int, from_seat: int, tile: int) -> None:
    for _ in range(2):
        state.hands[seat] = state.hands[seat].remove(tile)
    state.melds[seat].append(Meld("pon", tile, from_seat))
    record.events.append({"t": "pon", "seat": seat, "from": from_seat, "tile": code_of(tile)})


def apply_ankan(state: GameState, record: GameRecord, seat: int, tile: int) -> None:
    for _ in range(4):
        state.hands[seat] = state.hands[seat].remove(tile)
    state.melds[seat].append(Meld("ankan", tile, None))
    record.events.append({"t": "kan", "seat": seat, "kind": "ankan", "tile": code_of(tile)})


def apply_daiminkan(state: GameState, record: GameRecord,
                    seat: int, from_seat: int, tile: int) -> None:
    for _ in range(3):
        state.hands[seat] = state.hands[seat].remove(tile)
    state.melds[seat].append(Meld("daiminkan", tile, from_seat))
    record.events.append({"t": "kan", "seat": seat, "kind": "daiminkan",
                          "tile": code_of(tile), "from": from_seat})


def apply_tsumo(state: GameState, record: GameRecord, seat: int, tile: int) -> None:
    state.active[seat] = False
    state.winners.append(seat)
    hand_idx = state.hands[seat].to_indices()
    melds_list = list(state.melds[seat])
    lack = state.lack[seat]
    state.win_details.append({
        "seat": seat, "by": "tsumo", "tile": tile, "from": None,
        "robbery": False, "hand": hand_idx, "melds": melds_list, "lack": lack,
    })
    record.events.append({
        "t": "tsumo", "seat": seat, "tile": code_of(tile),
        "hand": codes_of(hand_idx),
        "melds": [make_meld_dict(m) for m in melds_list],
        "lack": lack,
    })


def apply_ron(state: GameState, record: GameRecord,
              seat: int, from_seat: int, tile: int, robbery: bool) -> None:
    state.hands[seat] = state.hands[seat].add(tile)
    state.active[seat] = False
    state.winners.append(seat)
    hand_idx = state.hands[seat].to_indices()
    melds_list = list(state.melds[seat])
    lack = state.lack[seat]
    state.win_details.append({
        "seat": seat, "by": "ron", "tile": tile, "from": from_seat,
        "robbery": robbery, "hand": hand_idx, "melds": melds_list, "lack": lack,
    })
    record.events.append({
        "t": "ron", "seat": seat, "from": from_seat, "tile": code_of(tile),
        "hand": codes_of(hand_idx),
        "melds": [make_meld_dict(m) for m in melds_list],
        "lack": lack, "robbery": robbery,
    })


def apply_shouminkan(state: GameState, record: GameRecord, seat: int, tile: int) -> bool:
    """补杠:先查抢杠。被抢返回 True(ron 成立,杠取消);否则杠成立返回 False。

    行为与 Game._handle_shouminkan 完全一致(抽取源)。
    """
    others = [
        (s, state.hands[s], state.lack[s], len(state.melds[s]))
        for s in range(4) if s != seat and state.active[s]
    ]
    robbers = robbery_targets(others, tile)

    if robbers:
        # 杠取消:声明者暗手移除补杠牌(被抢者取走)
        state.hands[seat] = state.hands[seat].remove(tile)
        state.last_discard = None
        for r in robbers:
            apply_ron(state, record, r, seat, tile, robbery=True)
        return True

    # 杠成立:暗手移除 1 张,碰 -> 补杠
    state.hands[seat] = state.hands[seat].remove(tile)
    for i, m in enumerate(state.melds[seat]):
        if m.kind == "pon" and m.tile == tile:
            state.melds[seat][i] = Meld("shouminkan", tile, None)
            break
    record.events.append({"t": "kan", "seat": seat, "kind": "shouminkan", "tile": code_of(tile)})
    return False
