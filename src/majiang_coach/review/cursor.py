"""review/cursor.py:牌谱逐步回放光标(Phase 6,见计划 §6.1)。

ReviewCursor 按事件流增量重建局内状态(counts[4][27]/melds/discards/lack/winners),
事件处理逻辑与 engine/record.replay() 一致(deal/swap/lack/draw/discard/pon/kan/
kan_draw/tsumo/ron/ryuukyoku;一炮多响 claimed 只扣一次弃牌)。额外追踪:
  - wall_remaining:初始 108,每个 deal 事件扣 len(tiles)(发牌 4*13 后余 56),每个
    draw/kan_draw 减 1(每步张数守恒 108)。
  - turn:巡目(discard 计数)。
  - last_discard:(src_seat, tile),discard 事件后置位,draw/kan_draw/申索后清空。

view(seat) 镜像 GameState.make_view,构造信息隔离的 PlayerView(不含他家暗手)。
final_state() 与 engine/record.replay(record) 结果一致(测试锚点)。
"""

from __future__ import annotations

from .. import tiles
from ..engine.melds import Meld
from ..engine.record import GameRecord, FinalState
from ..engine.view import PlayerView
from ..hand import Hand

__all__ = ["ReviewCursor"]

_TOTAL_TILES = 108
_WALL_AFTER_DEAL = 56  # 108 - 4*13


def _idx(code: str) -> int:
    return tiles.code_to_index(code)


def _counts_to_indices(counts: list[int]) -> list[int]:
    out: list[int] = []
    for i, c in enumerate(counts):
        if c:
            out.extend([i] * c)
    return out


class ReviewCursor:
    """GameRecord 事件流的增量回放光标。"""

    def __init__(self, record: GameRecord | dict) -> None:
        self._record = (
            record if isinstance(record, GameRecord) else GameRecord.from_dict(record)
        )
        self.events = self._record.events
        self.reset()

    # ------------------------------------------------------------------
    # 状态重置 / 推进
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """回到发牌前(全空状态;牌墙 108 张)。"""
        self.pos = 0
        self.counts: list[list[int]] = [[0] * tiles.NUM_TILES for _ in range(4)]
        self.melds: list[list[Meld]] = [[] for _ in range(4)]
        self.discards: list[list[int]] = [[] for _ in range(4)]
        self.lack: list[int | None] = [None] * 4
        self.winners: list[int] = []
        self.active: list[bool] = [True, True, True, True]
        self.wall_remaining = _TOTAL_TILES  # 发牌前全部在墙
        self.turn = 0
        self.last_discard: tuple[int, int] | None = None
        self.win_details: list[dict] = []
        self.drawn = False
        self._claimed = False  # 当前弃牌是否已被申索(一炮多响仅扣一次)

    def advance_one(self) -> dict | None:
        """处理下一个事件;无更多事件返回 None。"""
        if self.pos >= len(self.events):
            return None
        ev = self.events[self.pos]
        self._process(ev)
        self.pos += 1
        return ev

    def advance_to(self, event_index: int) -> None:
        """推进状态到 event_index(含)。"""
        while self.pos <= event_index and self.pos < len(self.events):
            self.advance_one()

    def assert_total(self) -> int:
        """张数守恒:暗手+副露+弃牌+牌墙 == 108(调试断言)。"""
        total = self.wall_remaining
        for s in range(4):
            total += sum(self.counts[s])
            for m in self.melds[s]:
                total += m.tile_count
            total += len(self.discards[s])
        assert total == _TOTAL_TILES, f"张数不守恒:{total} != {_TOTAL_TILES}"
        return total

    # ------------------------------------------------------------------
    # 事件处理(镜像 engine/record.replay(),+ active/wall/turn/last_discard)
    # ------------------------------------------------------------------

    def _process(self, ev: dict) -> None:
        t = ev["t"]
        if t == "deal":
            s = ev["seat"]
            for code in ev["tiles"]:
                self.counts[s][_idx(code)] += 1
            self.wall_remaining -= len(ev["tiles"])

        elif t == "swap":
            given = ev["given"]
            received = ev["received"]
            for s in range(4):
                for code in given[str(s)]:
                    self.counts[s][_idx(code)] -= 1
                for code in received[str(s)]:
                    self.counts[s][_idx(code)] += 1

        elif t == "lack":
            self.lack[ev["seat"]] = ev["suit"]

        elif t == "draw":
            s = ev["seat"]
            self.counts[s][_idx(ev["tile"])] += 1
            self.wall_remaining -= 1
            self.last_discard = None
            self._claimed = False

        elif t == "discard":
            s = ev["seat"]
            idx = _idx(ev["tile"])
            self.counts[s][idx] -= 1
            self.discards[s].append(idx)
            self.last_discard = (s, idx)
            self.turn += 1
            self._claimed = False

        elif t == "pon":
            s = ev["seat"]
            frm = ev["from"]
            idx = _idx(ev["tile"])
            if not self._claimed:
                self.discards[frm].pop()
                self._claimed = True
            self.counts[s][idx] -= 2
            self.melds[s].append(Meld("pon", idx, frm))
            self.last_discard = None

        elif t == "kan":
            s = ev["seat"]
            kind = ev["kind"]
            idx = _idx(ev["tile"])
            frm = ev.get("from")
            if kind == "ankan":
                self.counts[s][idx] -= 4
                self.melds[s].append(Meld("ankan", idx, None))
            elif kind == "daiminkan":
                if not self._claimed:
                    self.discards[frm].pop()
                    self._claimed = True
                self.counts[s][idx] -= 3
                self.melds[s].append(Meld("daiminkan", idx, frm))
            elif kind == "shouminkan":
                self.counts[s][idx] -= 1
                for i, m in enumerate(self.melds[s]):
                    if m.kind == "pon" and m.tile == idx:
                        self.melds[s][i] = Meld("shouminkan", idx, None)
                        break
            self.last_discard = None

        elif t == "kan_draw":
            s = ev["seat"]
            self.counts[s][_idx(ev["tile"])] += 1
            self.wall_remaining -= 1
            self.last_discard = None
            self._claimed = False

        elif t == "tsumo":
            s = ev["seat"]
            self.active[s] = False
            self.winners.append(s)
            self.win_details.append({
                "seat": s, "by": "tsumo", "tile": _idx(ev["tile"]),
                "from": None, "robbery": False,
                "hand": ev.get("hand", []), "melds": ev.get("melds", []),
                "lack": ev.get("lack"),
            })
            self.last_discard = None

        elif t == "ron":
            s = ev["seat"]
            frm = ev["from"]
            idx = _idx(ev["tile"])
            if ev.get("robbery"):
                # 抢杠:从声明者暗手移除(非弃牌堆)
                self.counts[frm][idx] -= 1
            else:
                if not self._claimed:
                    self.discards[frm].pop()
                    self._claimed = True
            self.counts[s][idx] += 1
            self.active[s] = False
            self.winners.append(s)
            self.win_details.append({
                "seat": s, "by": "ron", "tile": idx,
                "from": frm, "robbery": ev.get("robbery", False),
                "hand": ev.get("hand", []), "melds": ev.get("melds", []),
                "lack": ev.get("lack"),
            })
            self.last_discard = None

        elif t == "ryuukyoku":
            self.drawn = True
            self.last_discard = None

    # ------------------------------------------------------------------
    # 视角构造
    # ------------------------------------------------------------------

    def active_seats(self) -> list[int]:
        return [s for s in range(4) if self.active[s]]

    def view(self, seat: int, *, last_discard: tuple[int, int] | None = None) -> PlayerView:
        """构造 seat 的可见 PlayerView(信息隔离,镜像 GameState.make_view)。

        last_discard 缺省取当前光标状态(discard 后置位);也可显式覆盖(申索点)。
        """
        ld = self.last_discard if last_discard is None else last_discard
        return PlayerView(
            seat=seat,
            hand=Hand.from_counts(self.counts[seat]),
            melds=tuple(self.melds[seat]),
            lack_suit=self.lack[seat],
            lack_suits=tuple(self.lack),
            discards=tuple(tuple(d) for d in self.discards),
            public_melds=tuple(tuple(m) for m in self.melds),
            wall_remaining=self.wall_remaining,
            turn=self.turn,
            last_discard=ld,
            active_seats=tuple(self.active_seats()),
            winners=tuple(self.winners),
        )

    # ------------------------------------------------------------------
    # 迭代器
    # ------------------------------------------------------------------

    def iter_draw_events(self):
        """迭代每个 draw/kan_draw 决策点:(event_index, seat, drawn_tile_idx)。

        产出时状态已推进到该 draw 之后(该座 14 张刚摸态)。
        """
        self.reset()
        for i, ev in enumerate(self.events):
            self.advance_one()
            if ev["t"] in ("draw", "kan_draw"):
                yield i, ev["seat"], _idx(ev["tile"])

    # ------------------------------------------------------------------
    # 终局快照(与 engine/record.replay() 一致)
    # ------------------------------------------------------------------

    def final_state(self) -> FinalState:
        """复现终局状态(等价于 replay(record),测试锚点)。"""
        while self.advance_one() is not None:
            pass
        return FinalState(
            hands=[_counts_to_indices(c) for c in self.counts],
            melds=list(self.melds),
            discards=list(self.discards),
            lack=list(self.lack),
            winners=list(self.winners),
            win_details=list(self.win_details),
            drawn=self.drawn,
        )
