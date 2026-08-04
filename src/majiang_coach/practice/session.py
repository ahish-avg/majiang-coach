"""practice/session.py:PracticeSession 可步进状态机(Phase 5,见计划 §5/§6)。

人类=座0(庄,先摸);3 个启发式 AI=座1-3(各自强度)。完整血战到底。
传输无关:REST 轮次制只调 current_prompt()/submit();WS 后续接入不改会话逻辑。

5 类人类决策点到达即暂停并存 pending:
  1. swap 换三张  2. lack 定缺  3. turn_action 自摸后  4. claim 他人弃牌申索  5. robbery 抢杠
AI 座的 draw/turn_action/claim/抢杠全由 HeuristicActor 即时执行;advance() 跑到下一
人类决策点或终局(3 胡或流局)。非法动作->拒绝(state 不变)+ 重发当前 prompt。

复用 engine.apply 纯函数 + GameState + Phase 3 analyze + Phase 4 advise;只重写循环控制。
"""

from __future__ import annotations

import random
import uuid
from collections import Counter

from .. import tiles
from ..ai import HeuristicActor
from ..analysis import analyze
from ..engine.action import (
    Action, legal_self_actions, legal_claims, lack_action,
)
from ..engine.apply import (
    apply_discard, apply_pon, apply_ankan, apply_daiminkan,
    apply_tsumo, apply_ron, code_of,
)
from ..engine.melds import Meld
from ..engine.record import GameRecord
from ..engine.rules import resolve_claims, robbery_targets
from ..engine.settlement import build_result
from ..engine.state import GameState
from ..engine.view import PlayerView
from ..hand import Hand
from ..llm import LLMConfig, advise
from .prompt import PendingDecision, build_prompt, summarize_record

__all__ = ["PracticeSession", "IllegalActionError"]

_SUIT_LETTER = {0: "m", 1: "s", 2: "p"}


class IllegalActionError(ValueError):
    """人类提交了非法动作(state 不变)。"""


class PracticeSession:
    """练习模式会话:人类(座0)+ 3 启发式 AI(座1-3),可步进状态机。"""

    def __init__(
        self,
        ai_strengths: list[str] | None = None,
        hints_on: bool = False,
        llm_config: LLMConfig | None = None,
        weights: dict | None = None,
        seed: int = 0,
        session_id: str | None = None,
    ) -> None:
        if ai_strengths is None:
            ai_strengths = ["mid", "mid", "mid"]
        if len(ai_strengths) != 3:
            raise ValueError(f"ai_strengths 须 3 个(座1-3),得到 {len(ai_strengths)}")
        self.human_seat = 0
        self.hints_on = hints_on
        self.llm_config = llm_config
        self.weights = weights
        self.seed = seed
        self.session_id = session_id or uuid.uuid4().hex[:12]

        # AI 座1-3(座0 为人类,置 None 占位)
        self.ai: list = [None, HeuristicActor(ai_strengths[0], seed * 4 + 1),
                         HeuristicActor(ai_strengths[1], seed * 4 + 2),
                         HeuristicActor(ai_strengths[2], seed * 4 + 3)]
        self.ai_strengths = list(ai_strengths)

        self.state = GameState.new(seed)
        self._record = GameRecord(meta={
            "version": 1, "ruleset": "sichuan-xuezhan", "seats": 4, "dealer": 0,
            "direction": "ccw", "seed": seed, "swap_direction": None,
            "lack": [None, None, None, None],
        })
        self._meta_rng = random.Random(seed ^ 0x5F12)

        # 循环控制
        self._mode: str = "swap"   # swap|lack|act|claim|draw|over
        self._seat: int = 0
        self._drawn: int | None = None
        self.pending: PendingDecision | None = None
        self._finalized = False

        # 1. 发牌
        dealt = self.state.wall.deal()
        for s in range(4):
            self.state.hands[s] = Hand.from_indices(dealt[s])
            self._record.events.append({"t": "deal", "seat": s,
                                       "tiles": [code_of(t) for t in dealt[s]]})
        # 2. 换三张:暂停等人类
        self._start_swap()

    # =====================================================================
    # 公共 API
    # =====================================================================

    def is_over(self) -> bool:
        return self._mode == "over" or self._finalized

    def current_prompt(self) -> dict:
        """当前提示(决策点或 game_over);无 pending 且未结束则先 advance。"""
        if self.pending is None and not self.is_over():
            self._advance()
        if self.is_over():
            self._finalize()
            return build_prompt(self.session_id, None, True, self._record,
                                summarize_record(self._record))
        return build_prompt(self.session_id, self.pending, False)

    def submit(self, action: Action) -> dict:
        """校验合法->应用->advance 到下一人类点或终局;非法->拒绝(state 不变)。"""
        if self.pending is None:
            raise IllegalActionError("无待决策点(会话可能已结束)")
        kind = self.pending.kind
        if kind == "swap":
            self._submit_swap(action)
        elif kind == "lack":
            self._submit_lack(action)
        elif kind == "turn_action":
            self._submit_turn_action(action)
        elif kind == "claim":
            self._submit_claim(action)
        elif kind == "robbery":
            self._submit_robbery(action)
        else:
            raise IllegalActionError(f"未知决策点 {kind}")
        return self.current_prompt()

    def advise_on_demand(self, weights: dict | None = None) -> dict:
        """on-demand 问教练(Phase 4 advise);无 llm 配置则 advice=null+error。"""
        if self.pending is None:
            raise IllegalActionError("无待决策点,无法问教练")
        view = self.pending.view
        w = weights if weights is not None else self.weights
        res = advise(view, hints_on=True, llm_config=self.llm_config, weights=w)
        return res.to_dict()

    def record(self) -> GameRecord:
        """牌谱(终局或中段)。"""
        if self.is_over():
            self._finalize()
        return self._record

    # =====================================================================
    # 换三张
    # =====================================================================

    def _start_swap(self) -> None:
        view = self.state.make_view(self.human_seat)
        self.pending = PendingDecision(
            kind="swap", view=view, legal_actions=[],
            advise=None, hint=self._swap_hint(view),
        )

    def _submit_swap(self, action: Action) -> None:
        t3 = action.tiles
        if t3 is None or len(t3) != 3:
            raise IllegalActionError("换三张须给 3 张")
        if len({tiles.suit_of(t) for t in t3}) != 1:
            raise IllegalActionError("换三张须同门")
        hand = self.state.hands[self.human_seat]
        cnt = Counter(t3)
        for t, c in cnt.items():
            if hand.count(t) < c:
                raise IllegalActionError(f"手中无足够 {code_of(t)}")
        self.pending = None

        given = [list(t3)]
        for s in range(1, 4):
            given.append(list(self.ai[s].choose_swap(self.state.make_view(s))))

        direction = self._meta_rng.choice(["cw", "ccw", "across"])
        self.state.swap_direction = direction
        self._record.meta["swap_direction"] = direction
        received = [[] for _ in range(4)]
        for src in range(4):
            received[self._swap_dest(src, direction)] = list(given[src])
        for s in range(4):
            for t in given[s]:
                self.state.hands[s] = self.state.hands[s].remove(t)
            for t in received[s]:
                self.state.hands[s] = self.state.hands[s].add(t)
        self._record.events.append({
            "t": "swap", "direction": direction,
            "given": {str(s): [code_of(t) for t in given[s]] for s in range(4)},
            "received": {str(s): [code_of(t) for t in received[s]] for s in range(4)},
        })
        self._start_lack()

    @staticmethod
    def _swap_dest(src: int, direction: str) -> int:
        if direction == "cw":
            return (src + 1) % 4
        if direction == "ccw":
            return (src + 3) % 4
        return (src + 2) % 4  # across

    # =====================================================================
    # 定缺
    # =====================================================================

    def _start_lack(self) -> None:
        view = self.state.make_view(self.human_seat)
        self.pending = PendingDecision(
            kind="lack", view=view,
            legal_actions=[lack_action(0), lack_action(1), lack_action(2)],
            advise=None, hint=self._lack_hint(view),
        )

    def _submit_lack(self, action: Action) -> None:
        if action.suit not in (0, 1, 2):
            raise IllegalActionError("缺门须 0/1/2")
        self.pending = None
        self.state.lack[self.human_seat] = action.suit
        self._record.events.append({"t": "lack", "seat": 0, "suit": action.suit})
        for s in range(1, 4):
            ls = self.ai[s].choose_lack(self.state.make_view(s))
            self.state.lack[s] = ls
            self._record.events.append({"t": "lack", "seat": s, "suit": ls})
        self._enter_main_loop()

    def _enter_main_loop(self) -> None:
        # 庄家(座0=人类)先摸
        drawn = self.state.wall.draw()
        self.state.hands[0] = self.state.hands[0].add(drawn)
        self.state.turn = 0
        self._record.events.append({"t": "draw", "seat": 0, "tile": code_of(drawn), "src": "wall"})
        self._mode = "act"
        self._seat = 0
        self._drawn = drawn
        self._advance()

    # =====================================================================
    # 主循环 advance
    # =====================================================================

    def _advance(self) -> None:
        """跑 AI 步骤,直到下一人类决策点或终局。"""
        while self._mode != "over":
            if self._mode == "act":
                if self._seat == self.human_seat and self.state.active[self.human_seat]:
                    self._set_turn_action_pending()
                    return
                self._ai_act()
                if self.pending is not None:  # 抢杠暂停
                    return
            elif self._mode == "claim":
                self._do_claim_phase()
                if self.pending is not None:
                    return
            elif self._mode == "draw":
                self._do_draw()
        self._finalize()

    def _set_turn_action_pending(self) -> None:
        view = self.state.make_view(self.human_seat)
        acts = legal_self_actions(view, self._drawn)
        advise_dict = self._build_advise(view) if self.hints_on else None
        hint = analyze(view, self.weights).to_dict()
        self.pending = PendingDecision(
            kind="turn_action", view=view, legal_actions=acts,
            advise=advise_dict, hint=hint, drawn=self._drawn,
        )

    def _ai_act(self) -> None:
        seat = self._seat
        view = self.state.make_view(seat)
        acts = legal_self_actions(view, self._drawn)
        act = self.ai[seat].choose_turn_action(view, self._drawn)
        if act not in acts:
            act = self._fallback_action(acts)
        self._apply_turn_action(act)

    @staticmethod
    def _fallback_action(acts: list[Action]) -> Action:
        for a in acts:
            if a.kind == "tsumo":
                return a
        for a in acts:
            if a.kind == "discard":
                return a
        return acts[0]

    def _apply_turn_action(self, act: Action) -> None:
        seat = self._seat
        if act.kind == "tsumo":
            apply_tsumo(self.state, self._record, seat, act.tile)
            if self.state.is_over():
                self._mode = "over"; return
            self._mode = "draw"; self._seat = self.state.next_active(seat)
        elif act.kind == "ankan":
            apply_ankan(self.state, self._record, seat, act.tile)
            self._rinshan_and_continue(seat)
        elif act.kind == "shouminkan":
            res = self._declare_shouminkan(seat, act.tile)
            if res == "paused":
                return  # pending 已设,mode 不变
            if res == "robbed":
                if self.state.is_over():
                    self._mode = "over"; return
                self._mode = "draw"; self._seat = self.state.next_active(seat)
            else:  # completed
                self._rinshan_and_continue(seat)
        elif act.kind == "discard":
            apply_discard(self.state, self._record, seat, act.tile)
            self._mode = "claim"
        else:
            raise ValueError(f"不支持的回合动作 {act}")

    def _rinshan_and_continue(self, seat: int) -> None:
        drawn = self.state.wall.draw_rinshan()
        self.state.hands[seat] = self.state.hands[seat].add(drawn)
        self._record.events.append({"t": "kan_draw", "seat": seat,
                                   "tile": code_of(drawn), "src": "rinshan"})
        self._mode = "act"; self._seat = seat; self._drawn = drawn

    # =====================================================================
    # 申索阶段
    # =====================================================================

    def _do_claim_phase(self) -> None:
        discarder = self._seat
        tile = self.state.last_discard[1]
        choices: list[tuple[int, Action]] = []
        human_can_claim = False
        human_claimable: list[Action] = []
        for offset in range(1, 4):
            s = (discarder + offset) % 4
            if not self.state.active[s]:
                continue
            view = self.state.make_view(s)
            claimable = legal_claims(view, tile)
            if s == self.human_seat:
                if claimable:
                    human_can_claim = True
                    human_claimable = claimable
                else:
                    choices.append((s, Action("pass")))
                continue
            if not claimable:
                choices.append((s, Action("pass")))
                continue
            choice = self.ai[s].choose_claim(view, claimable + [Action("pass")])
            choices.append((s, choice))

        if human_can_claim:
            view = self.state.make_view(self.human_seat)
            hint = analyze(view, self.weights).to_dict()
            self.pending = PendingDecision(
                kind="claim", view=view,
                legal_actions=human_claimable + [Action("pass")],
                advise=None, hint=hint,
                claim_ctx={"discarder": discarder, "tile": tile, "ai_choices": choices},
            )
            return
        self._resolve_claim(discarder, tile, choices)

    def _resolve_claim(self, discarder: int, tile: int,
                       choices: list[tuple[int, Action]]) -> None:
        result = resolve_claims(discarder, choices)
        if result[0] == "ron":
            self._pop_discard_once(discarder)
            self.state.last_discard = None
            for w in result[1]:  # type: ignore[index]
                apply_ron(self.state, self._record, w, discarder, tile, robbery=False)
            if self.state.is_over():
                self._mode = "over"; return
            self._mode = "draw"; self._seat = self.state.next_active(discarder)
        elif result[0] == "claim":
            claimer = result[1]  # type: ignore[index]
            act = result[2]  # type: ignore[index]
            self._pop_discard_once(discarder)
            self.state.last_discard = None
            if act.kind == "pon":
                apply_pon(self.state, self._record, claimer, discarder, tile)
                self._mode = "act"; self._seat = claimer; self._drawn = None
            elif act.kind == "daiminkan":
                apply_daiminkan(self.state, self._record, claimer, discarder, tile)
                rinshan = self.state.wall.draw_rinshan()
                self.state.hands[claimer] = self.state.hands[claimer].add(rinshan)
                self._record.events.append({"t": "kan_draw", "seat": claimer,
                                           "tile": code_of(rinshan), "src": "rinshan"})
                self._mode = "act"; self._seat = claimer; self._drawn = rinshan
        else:  # pass
            self._mode = "draw"; self._seat = self.state.next_active(discarder)

    def _pop_discard_once(self, discarder: int) -> None:
        if self.state.last_discard is not None and self.state.discards[discarder]:
            self.state.discards[discarder].pop()

    def _submit_claim(self, action: Action) -> None:
        matched = self._match_legal(action)
        if matched is None:
            raise IllegalActionError("非法申索")
        ctx = self.pending.claim_ctx  # type: ignore[union-attr]
        choices = list(ctx["ai_choices"]) + [(self.human_seat, matched)]
        self.pending = None
        self._resolve_claim(ctx["discarder"], ctx["tile"], choices)
        if self._mode != "over":
            self._advance()

    # =====================================================================
    # 抢杠
    # =====================================================================

    def _declare_shouminkan(self, seat: int, tile: int) -> str:
        """补杠:查抢杠。返回 paused/robbed/completed。"""
        others = [(s, self.state.hands[s], self.state.lack[s], len(self.state.melds[s]))
                  for s in range(4) if s != seat and self.state.active[s]]
        robbers = robbery_targets(others, tile)
        ai_robbers = [r for r in robbers if r != self.human_seat]
        human_can_rob = self.human_seat in robbers

        if not robbers:
            self._complete_shouminkan(seat, tile)
            return "completed"
        if human_can_rob:
            view = self.state.make_view(self.human_seat)
            self.pending = PendingDecision(
                kind="robbery", view=view,
                legal_actions=[Action("ron", tile=tile, src=seat), Action("pass")],
                advise=None,
                hint={"declarer": seat, "tile": code_of(tile), "can_rob": True},
                robbery_ctx={"declarer": seat, "tile": tile, "ai_robbers": ai_robbers},
            )
            return "paused"
        # 仅 AI 可抢:能胡必胡,自动抢
        self._apply_robbery(seat, tile, ai_robbers)
        return "robbed"

    def _complete_shouminkan(self, seat: int, tile: int) -> None:
        self.state.hands[seat] = self.state.hands[seat].remove(tile)
        for i, m in enumerate(self.state.melds[seat]):
            if m.kind == "pon" and m.tile == tile:
                self.state.melds[seat][i] = Meld("shouminkan", tile, None)
                break
        self._record.events.append({"t": "kan", "seat": seat, "kind": "shouminkan",
                                   "tile": code_of(tile)})

    def _apply_robbery(self, declarer: int, tile: int, robbers: list[int]) -> None:
        self.state.hands[declarer] = self.state.hands[declarer].remove(tile)
        self.state.last_discard = None
        for r in sorted(robbers):
            apply_ron(self.state, self._record, r, declarer, tile, robbery=True)

    def _submit_robbery(self, action: Action) -> None:
        matched = self._match_legal(action)
        if matched is None:
            raise IllegalActionError("非法抢杠选择")
        ctx = self.pending.robbery_ctx  # type: ignore[union-attr]
        declarer, tile, ai_robbers = ctx["declarer"], ctx["tile"], ctx["ai_robbers"]
        self.pending = None
        if matched.kind == "ron":
            self._apply_robbery(declarer, tile, ai_robbers + [self.human_seat])
            if self.state.is_over():
                self._mode = "over"
            else:
                self._mode = "draw"; self._seat = self.state.next_active(declarer)
        else:  # pass
            if ai_robbers:
                self._apply_robbery(declarer, tile, ai_robbers)
                if self.state.is_over():
                    self._mode = "over"
                else:
                    self._mode = "draw"; self._seat = self.state.next_active(declarer)
            else:
                self._complete_shouminkan(declarer, tile)
                self._rinshan_and_continue(declarer)
        if self._mode != "over":
            self._advance()

    # =====================================================================
    # 摸牌
    # =====================================================================

    def _do_draw(self) -> None:
        self.state.last_discard = None
        if self.state.wall.exhausted():
            self._record.events.append({"t": "ryuukyoku"})
            self._mode = "over"; return
        drawn = self.state.wall.draw()
        self.state.hands[self._seat] = self.state.hands[self._seat].add(drawn)
        self.state.turn = self._seat
        self._record.events.append({"t": "draw", "seat": self._seat,
                                   "tile": code_of(drawn), "src": "wall"})
        self._mode = "act"; self._drawn = drawn

    # =====================================================================
    # 终局
    # =====================================================================

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True
        self.pending = None
        self._mode = "over"
        drawn = len(self.state.winners) < 3
        result = build_result(self.state, drawn)
        self._record.result = result.to_dict()
        self._record.meta["lack"] = list(self.state.lack)

    # =====================================================================
    # turn_action 提交 + 合法性匹配
    # =====================================================================

    def _submit_turn_action(self, action: Action) -> None:
        matched = self._match_legal(action)
        if matched is None:
            raise IllegalActionError("非法回合动作")
        self.pending = None
        self._apply_turn_action(matched)
        if self._mode != "over" and self.pending is None:
            self._advance()

    def _match_legal(self, action: Action) -> Action | None:
        for la in self.pending.legal_actions:  # type: ignore[union-attr]
            if self._actions_match(action, la):
                return la
        return None

    @staticmethod
    def _actions_match(a: Action, la: Action) -> bool:
        if a.kind != la.kind:
            return False
        if a.kind in ("discard", "tsumo", "ankan", "shouminkan"):
            return a.tile == la.tile
        if a.kind in ("pon", "daiminkan", "ron", "ronkan"):
            return a.tile == la.tile
        if a.kind == "swap":
            return a.tiles == la.tiles
        if a.kind == "lack":
            return a.suit == la.suit
        if a.kind == "pass":
            return True
        return False

    # =====================================================================
    # 提示构建助手
    # =====================================================================

    def _build_advise(self, view: PlayerView) -> dict | None:
        try:
            res = advise(view, hints_on=True, llm_config=self.llm_config, weights=self.weights)
            return res.to_dict()
        except Exception:
            return None

    def _swap_hint(self, view: PlayerView) -> dict | None:
        try:
            t3 = HeuristicActor("mid", 0).choose_swap(view)
            suit = tiles.suit_of(t3[0])
            return {"suggest_suit": _SUIT_LETTER[suit],
                    "suggest_tiles": [code_of(t) for t in t3],
                    "reason": "倾倒张数最少且 >=3 的门"}
        except Exception:
            return None

    def _lack_hint(self, view: PlayerView) -> dict | None:
        try:
            suit = HeuristicActor("mid", 0).choose_lack(view)
        except Exception:
            return None
        counts = []
        for s in range(3):
            base = s * 9
            counts.append({"suit": _SUIT_LETTER[s],
                           "count": sum(view.hand.count(i) for i in range(base, base + 9))})
        return {"suggest_suit": _SUIT_LETTER[suit], "suit_counts": counts,
                "reason": "张数最少的门"}
