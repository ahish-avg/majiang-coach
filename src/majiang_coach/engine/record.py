"""GameRecord:结构化 JSON 事件流牌谱 + replay() 复现终局。

牌谱为语言无关 JSON 事件流(机器可读,Phase 6 复盘依赖)。事件用牌字符串码
(如 "5m")便于人读;内部状态用索引,在序列化边界统一转换。

终局事件(tsumo/ron)记录全暗手(复盘需知对手牌);过程事件不泄露他家暗手。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import tiles
from .melds import Meld

__all__ = ["GameRecord", "FinalState", "replay", "make_meld_dict", "meld_from_dict"]


# ---- 副露序列化 ----

def make_meld_dict(meld: Meld) -> dict:
    """Meld -> JSON dict(牌用字符串码)。"""
    return {
        "kind": meld.kind,
        "tile": tiles.index_to_code(meld.tile),
        "from": meld.src_seat,
    }


def meld_from_dict(d: dict) -> Meld:
    """JSON dict -> Meld。"""
    return Meld(
        kind=d["kind"],
        tile=tiles.code_to_index(d["tile"]),
        src_seat=d.get("from"),
    )


def _codes(idxs) -> list[str]:
    return [tiles.index_to_code(i) for i in idxs]


def _idx(code: str) -> int:
    return tiles.code_to_index(code)


@dataclass
class FinalState:
    """replay() 复现的终局状态。"""

    hands: list[list[int]]  # 4 座终局暗手(索引;赢家含胡牌张)
    melds: list[list[Meld]]
    discards: list[list[int]]
    lack: list[int | None]
    winners: list[int]
    win_details: list[dict]
    drawn: bool


@dataclass
class GameRecord:
    """一局牌谱:meta + 事件流 + 结果。"""

    meta: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    result: dict | None = None

    def to_dict(self) -> dict:
        return {"meta": self.meta, "events": self.events, "result": self.result}

    @classmethod
    def from_dict(cls, d: dict) -> "GameRecord":
        return cls(meta=d.get("meta", {}), events=d.get("events", []), result=d.get("result"))


def replay(record: GameRecord | dict) -> FinalState:
    """按事件流复现终局状态。

    逐事件重建各座暗手/副露/弃牌/缺门/赢家,验证牌谱自洽。
    """
    events = record["events"] if isinstance(record, dict) else record.events

    counts: list[list[int]] = [[0] * tiles.NUM_TILES for _ in range(4)]
    melds: list[list[Meld]] = [[] for _ in range(4)]
    discards: list[list[int]] = [[] for _ in range(4)]
    lack: list[int | None] = [None] * 4
    winners: list[int] = []
    win_details: list[dict] = []
    drawn = False
    claimed = False  # 当前弃牌是否已被申索(一炮多响时仅扣一次)

    for ev in events:
        t = ev["t"]
        if t == "deal":
            s = ev["seat"]
            for code in ev["tiles"]:
                counts[s][_idx(code)] += 1

        elif t == "swap":
            given = ev["given"]
            received = ev["received"]
            for s in range(4):
                for code in given[str(s)]:
                    counts[s][_idx(code)] -= 1
                for code in received[str(s)]:
                    counts[s][_idx(code)] += 1

        elif t == "lack":
            lack[ev["seat"]] = ev["suit"]

        elif t == "draw":
            s = ev["seat"]
            counts[s][_idx(ev["tile"])] += 1
            claimed = False

        elif t == "discard":
            s = ev["seat"]
            idx = _idx(ev["tile"])
            counts[s][idx] -= 1
            discards[s].append(idx)
            claimed = False

        elif t == "pon":
            s = ev["seat"]
            frm = ev["from"]
            idx = _idx(ev["tile"])
            if not claimed:
                discards[frm].pop()
                claimed = True
            counts[s][idx] -= 2
            melds[s].append(Meld("pon", idx, frm))

        elif t == "kan":
            s = ev["seat"]
            kind = ev["kind"]
            idx = _idx(ev["tile"])
            frm = ev.get("from")
            if kind == "ankan":
                counts[s][idx] -= 4
                melds[s].append(Meld("ankan", idx, None))
            elif kind == "daiminkan":
                if not claimed:
                    discards[frm].pop()
                    claimed = True
                counts[s][idx] -= 3
                melds[s].append(Meld("daiminkan", idx, frm))
            elif kind == "shouminkan":
                counts[s][idx] -= 1
                for i, m in enumerate(melds[s]):
                    if m.kind == "pon" and m.tile == idx:
                        melds[s][i] = Meld("shouminkan", idx, None)
                        break

        elif t == "kan_draw":
            s = ev["seat"]
            counts[s][_idx(ev["tile"])] += 1
            claimed = False

        elif t == "tsumo":
            s = ev["seat"]
            winners.append(s)
            win_details.append({
                "seat": s, "by": "tsumo", "tile": _idx(ev["tile"]),
                "from": None, "robbery": False,
                "hand": ev.get("hand", []), "melds": ev.get("melds", []),
                "lack": ev.get("lack"),
            })

        elif t == "ron":
            s = ev["seat"]
            frm = ev["from"]
            idx = _idx(ev["tile"])
            if ev.get("robbery"):
                # 抢杠:从声明者暗手移除(非弃牌堆)
                counts[frm][idx] -= 1
            else:
                if not claimed:
                    discards[frm].pop()
                    claimed = True
            counts[s][idx] += 1
            winners.append(s)
            win_details.append({
                "seat": s, "by": "ron", "tile": idx,
                "from": frm, "robbery": ev.get("robbery", False),
                "hand": ev.get("hand", []), "melds": ev.get("melds", []),
                "lack": ev.get("lack"),
            })

        elif t == "ryuukyoku":
            drawn = True

    hands = [_counts_to_indices(c) for c in counts]
    return FinalState(
        hands=hands, melds=melds, discards=discards, lack=lack,
        winners=winners, win_details=win_details, drawn=drawn,
    )


def _counts_to_indices(counts: list[int]) -> list[int]:
    out: list[int] = []
    for i, c in enumerate(counts):
        if c:
            out.extend([i] * c)
    return out
