"""Game 主循环 + Actor 协议 + RandomActor。

血战到底完整一局:发牌→换三张→定缺→摸打→碰/杠/胡→血战续打→终局。

Actor 协议为可插拔决策入口(Phase 5 启发式、Phase 4 LLM、人类座复用同一接口)。
RandomActor:均匀随机合法选择;唯一非随机例外——能胡(自摸/点炮)必胡,
保证产生赢家、触发血战续打分支。

座次逆时针(0→1→2→3→0)。庄=座 0。胡牌者移出轮转,继续至 3 家胡或牌墙摸完。
"""

from __future__ import annotations

import random
from typing import Protocol, runtime_checkable

from ..hand import Hand
from .action import (
    Action, legal_self_actions, legal_claims,
)
from .apply import (
    apply_discard, apply_pon, apply_ankan, apply_daiminkan,
    apply_tsumo, apply_ron, apply_shouminkan, code_of, codes_of,
)
from .record import GameRecord
from .rules import resolve_claims
from .settlement import build_result
from .state import GameState
from .view import PlayerView

__all__ = ["Actor", "RandomActor", "Game"]


def _code(idx: int) -> str:
    return code_of(idx)


def _codes(idxs) -> list[str]:
    return codes_of(idxs)


# ---- Actor 协议 ----

@runtime_checkable
class Actor(Protocol):
    """可插拔决策接口。"""

    def choose_swap(self, view: PlayerView) -> tuple[int, int, int]:
        """换三张:选 3 张同门牌给出。"""
        ...

    def choose_lack(self, view: PlayerView) -> int:
        """定缺:选一门缺(0=万 1=条 2=筒)。"""
        ...

    def choose_turn_action(self, view: PlayerView, drawn: int | None) -> Action:
        """自家摸牌后(或碰后)的动作。drawn=None 表示碰后仅可弃牌。"""
        ...

    def choose_claim(self, view: PlayerView, claimable: list[Action]) -> Action:
        """他人弃牌后的申索。claimable 含 pass。"""
        ...


# ---- RandomActor ----

class RandomActor:
    """均匀随机合法 Actor;能胡必胡(自摸/点炮必取)。"""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def choose_swap(self, view: PlayerView) -> tuple[int, int, int]:
        hand = view.hand
        candidates: list[int] = []
        for suit in range(3):
            base = suit * 9
            total = sum(hand.count(i) for i in range(base, base + 9))
            if total >= 3:
                candidates.append(suit)
        suit = self.rng.choice(candidates)
        base = suit * 9
        pool: list[int] = []
        for i in range(base, base + 9):
            pool.extend([i] * hand.count(i))
        chosen = self.rng.sample(pool, 3)
        return tuple(chosen)  # type: ignore[return-value]

    def choose_lack(self, view: PlayerView) -> int:
        return self.rng.choice([0, 1, 2])

    def choose_turn_action(self, view: PlayerView, drawn: int | None) -> Action:
        acts = legal_self_actions(view, drawn)
        for a in acts:
            if a.kind == "tsumo":
                return a  # 能胡必胡
        return self.rng.choice(acts)

    def choose_claim(self, view: PlayerView, claimable: list[Action]) -> Action:
        for a in claimable:
            if a.kind == "ron":
                return a  # 能胡必胡
        return self.rng.choice(claimable)


# ---- Game ----

class Game:
    """血战到底一局主循环。"""

    def __init__(self, actors: list[Actor], seed: int) -> None:
        if len(actors) != 4:
            raise ValueError(f"需要 4 个 Actor,得到 {len(actors)}")
        self.actors = actors
        self.seed = seed
        self._meta_rng = random.Random(seed ^ 0x5F12)

    def run(self) -> GameRecord:
        state = GameState.new(self.seed)
        record = GameRecord(meta={
            "version": 1,
            "ruleset": "sichuan-xuezhan",
            "seats": 4,
            "dealer": 0,
            "direction": "ccw",
            "seed": self.seed,
            "swap_direction": None,
            "lack": [None, None, None, None],
        })

        # 1. 发牌
        dealt = state.wall.deal()
        for s in range(4):
            state.hands[s] = Hand.from_indices(dealt[s])
            record.events.append({"t": "deal", "seat": s, "tiles": _codes(dealt[s])})

        # 2. 换三张
        self._do_swap(state, record)

        # 3. 定缺
        self._do_lack(state, record)

        # 4-5. 主循环(庄家先摸 → 回合循环 → 终局)
        self._run_loop(state, record)

        # 6. 结算桩
        drawn = len(state.winners) < 3
        result = build_result(state, drawn)
        record.result = result.to_dict()
        record.meta["lack"] = list(state.lack)
        return record

    def _run_loop(self, state: GameState, record: GameRecord) -> None:
        """主循环:庄家先摸 → 回合循环 → 终局(3 胡或流局)。

        可独立调用以测试特定状态机分支(跳过发牌/换三张/定缺)。
        """
        # 庄家先摸
        seat = 0
        drawn_tile = state.wall.draw()
        state.hands[seat] = state.hands[seat].add(drawn_tile)
        state.turn = seat
        record.events.append({"t": "draw", "seat": seat, "tile": _code(drawn_tile), "src": "wall"})

        mode = "act"
        while not state.is_over():
            if mode == "act":
                view = state.make_view(seat)
                acts = legal_self_actions(view, drawn_tile)
                act = self.actors[seat].choose_turn_action(view, drawn_tile)
                if act not in acts:
                    raise ValueError(f"座 {seat} 非法动作 {act};合法={acts}")

                if act.kind == "tsumo":
                    self._handle_tsumo(state, record, seat, act.tile)
                    if state.is_over():
                        break
                    mode = "draw"
                    seat = state.next_active(seat)

                elif act.kind == "ankan":
                    self._handle_ankan(state, record, seat, act.tile)
                    drawn_tile = state.wall.draw_rinshan()
                    state.hands[seat] = state.hands[seat].add(drawn_tile)
                    record.events.append({"t": "kan_draw", "seat": seat,
                                          "tile": _code(drawn_tile), "src": "rinshan"})

                elif act.kind == "shouminkan":
                    robbed = self._handle_shouminkan(state, record, seat, act.tile)
                    if robbed:
                        if state.is_over():
                            break
                        mode = "draw"
                        seat = state.next_active(seat)
                    else:
                        drawn_tile = state.wall.draw_rinshan()
                        state.hands[seat] = state.hands[seat].add(drawn_tile)
                        record.events.append({"t": "kan_draw", "seat": seat,
                                              "tile": _code(drawn_tile), "src": "rinshan"})

                elif act.kind == "discard":
                    self._handle_discard(state, record, seat, act.tile)
                    mode = "claim"

                else:
                    raise ValueError(f"不支持的回合动作 {act}")

            elif mode == "claim":
                discarder = seat
                tile = state.last_discard[1]  # type: ignore[index]
                signal = self._claim_phase(state, record, discarder, tile)

                if signal[0] == "ron":
                    if state.is_over():
                        break
                    mode = "draw"
                    seat = state.next_active(discarder)
                elif signal[0] == "act":
                    seat = signal[1]  # type: ignore[assignment]
                    drawn_tile = signal[2]
                    mode = "act"
                else:  # pass
                    mode = "draw"
                    seat = state.next_active(discarder)

            elif mode == "draw":
                state.last_discard = None
                if state.wall.exhausted():
                    record.events.append({"t": "ryuukyoku"})
                    break
                drawn_tile = state.wall.draw()
                state.hands[seat] = state.hands[seat].add(drawn_tile)
                state.turn = seat
                record.events.append({"t": "draw", "seat": seat,
                                      "tile": _code(drawn_tile), "src": "wall"})
                mode = "act"

    # ---- 阶段:换三张 ----

    def _do_swap(self, state: GameState, record: GameRecord) -> None:
        direction = self._meta_rng.choice(["cw", "ccw", "across"])
        state.swap_direction = direction
        record.meta["swap_direction"] = direction

        given: list[list[int]] = []
        for s in range(4):
            view = state.make_view(s)
            t3 = self.actors[s].choose_swap(view)
            given.append(list(t3))

        received: list[list[int]] = [[] for _ in range(4)]
        for src in range(4):
            dest = self._swap_dest(src, direction)
            received[dest] = list(given[src])

        for s in range(4):
            for t in given[s]:
                state.hands[s] = state.hands[s].remove(t)
            for t in received[s]:
                state.hands[s] = state.hands[s].add(t)

        record.events.append({
            "t": "swap", "direction": direction,
            "given": {str(s): _codes(given[s]) for s in range(4)},
            "received": {str(s): _codes(received[s]) for s in range(4)},
        })

    @staticmethod
    def _swap_dest(src: int, direction: str) -> int:
        if direction == "cw":
            return (src + 1) % 4
        if direction == "ccw":
            return (src + 3) % 4
        return (src + 2) % 4  # across

    # ---- 阶段:定缺 ----

    def _do_lack(self, state: GameState, record: GameRecord) -> None:
        for s in range(4):
            view = state.make_view(s)
            lack = self.actors[s].choose_lack(view)
            state.lack[s] = lack
            record.events.append({"t": "lack", "seat": s, "suit": lack})

    # ---- 申索阶段 ----

    def _claim_phase(
        self, state: GameState, record: GameRecord, discarder: int, tile: int
    ) -> tuple[str, ...]:
        choices: list[tuple[int, Action]] = []
        for offset in range(1, 4):
            s = (discarder + offset) % 4
            if not state.active[s]:
                continue
            view = state.make_view(s)
            claimable = legal_claims(view, tile)
            if not claimable:
                choices.append((s, Action("pass")))
                continue
            claimable.append(Action("pass"))
            choice = self.actors[s].choose_claim(view, claimable)
            choices.append((s, choice))

        result = resolve_claims(discarder, choices)

        if result[0] == "ron":
            winners = result[1]  # type: ignore[index]
            state.discards[discarder].pop()
            state.last_discard = None
            for w in winners:  # type: ignore[union-attr]
                self._handle_ron(state, record, w, discarder, tile, robbery=False)
            return ("ron",)

        if result[0] == "claim":
            claimer = result[1]  # type: ignore[index]
            act = result[2]  # type: ignore[index]
            state.discards[discarder].pop()
            state.last_discard = None
            if act.kind == "pon":
                self._handle_pon(state, record, claimer, discarder, tile)
                return ("act", claimer, None)
            if act.kind == "daiminkan":
                self._handle_daiminkan(state, record, claimer, discarder, tile)
                rinshan = state.wall.draw_rinshan()
                state.hands[claimer] = state.hands[claimer].add(rinshan)
                record.events.append({"t": "kan_draw", "seat": claimer,
                                      "tile": _code(rinshan), "src": "rinshan"})
                return ("act", claimer, rinshan)

        return ("pass",)

    # ---- 动作处理器(委托 engine.apply 纯函数;行为不变,见计划 §3)----

    def _handle_tsumo(self, state: GameState, record: GameRecord,
                      seat: int, tile: int) -> None:
        apply_tsumo(state, record, seat, tile)

    def _handle_ron(self, state: GameState, record: GameRecord,
                    seat: int, from_seat: int, tile: int, robbery: bool) -> None:
        apply_ron(state, record, seat, from_seat, tile, robbery)

    def _handle_discard(self, state: GameState, record: GameRecord,
                        seat: int, tile: int) -> None:
        apply_discard(state, record, seat, tile)

    def _handle_ankan(self, state: GameState, record: GameRecord,
                      seat: int, tile: int) -> None:
        apply_ankan(state, record, seat, tile)

    def _handle_pon(self, state: GameState, record: GameRecord,
                    seat: int, from_seat: int, tile: int) -> None:
        apply_pon(state, record, seat, from_seat, tile)

    def _handle_daiminkan(self, state: GameState, record: GameRecord,
                          seat: int, from_seat: int, tile: int) -> None:
        apply_daiminkan(state, record, seat, from_seat, tile)

    def _handle_shouminkan(self, state: GameState, record: GameRecord,
                           seat: int, tile: int) -> bool:
        """补杠:委托 apply_shouminkan(被抢返回 True,杠取消)。"""
        return apply_shouminkan(state, record, seat, tile)
