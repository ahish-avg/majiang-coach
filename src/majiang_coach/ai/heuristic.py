"""启发式 AI 对手(Phase 5,见计划 §5/§7)。

HeuristicActor 实现 engine.game.Actor 协议,弱/中/强三档强度可配:
  - 能胡必胡(自摸/点炮,所有强度)。
  - 弃牌走 Phase 3 analyze().recommend(综合最高);弱=top-3 随机。
  - 碰:pon_shanten_after < 当前 shanten 才碰(严格改善);弱=改善且 50% 随机;
    强=改善或保持下叫。
  - 杠:ankan/shouminkan 仅 tenpai 时(mid/strong,岭上不致变差);daiminkan 仅 strong+下叫。
  - 定缺/换三张:张数最少的门(平手取结构最弱);换三张给最弱门的 3 张(倾倒弱门)。

AI 弃牌/申索判定全部走 analyze(view)(Phase 3 纯函数),不调 win/shanten/ukeire 直接。
LLM 仅给人类教练(Phase 4),AI 不调 LLM。
"""

from __future__ import annotations

import random

from .. import tiles
from ..analysis import analyze
from ..engine.action import (
    Action, legal_self_actions, legal_claims, pass_action,
)
from ..engine.view import PlayerView
from ..shanten import shanten

__all__ = ["HeuristicActor", "STRENGTHS"]

STRENGTHS = ("weak", "mid", "strong")

# 各强度自身决策权重(用于碰/杠的向读与中档弃牌综合排序)。
_STRENGTH_WEIGHTS = {
    "weak": {"offense": 0.6, "defense": 0.4},
    "mid": {"offense": 0.6, "defense": 0.4},
    "strong": {"offense": 0.6, "defense": 0.4},
}


class HeuristicActor:
    """启发式 AI 对手(弱/中/强)。"""

    def __init__(self, strength: str = "mid", seed: int = 0) -> None:
        if strength not in STRENGTHS:
            raise ValueError(f"strength 须为 {STRENGTHS},得到 {strength!r}")
        self.strength = strength
        self.rng = random.Random(seed)

    def _weights(self) -> dict:
        return _STRENGTH_WEIGHTS[self.strength]

    # ---- 换三张:倾倒最弱门 ----

    def choose_swap(self, view: PlayerView) -> tuple[int, int, int]:
        hand = view.hand
        suit = self._dumpable_weakest_suit(hand, view.meld_count)
        base = suit * 9
        # 给该门的 3 张:优先单张(保留对子/刻子),按 (count, index) 取前 3
        pool: list[tuple[int, int]] = []  # (count, idx)
        for i in range(base, base + 9):
            c = hand.count(i)
            if c > 0:
                pool.extend([(c, i)] * c)
        pool.sort(key=lambda p: (p[0], p[1]))
        chosen = [p[1] for p in pool[:3]]
        chosen = chosen[:3]
        return (chosen[0], chosen[1], chosen[2])  # type: ignore[return-value]

    def _dumpable_weakest_suit(self, hand, melds: int) -> int:
        """换三张:在 >=3 张的门中取最弱(张数最少,平手取结构最弱)。

        13 张分 3 门必有 >=3 张的门(鸽巢);倾倒该门以利随后定缺。
        """
        counts = []
        for suit in range(3):
            base = suit * 9
            total = sum(hand.count(i) for i in range(base, base + 9))
            counts.append((suit, total))
        candidates = [c for c in counts if c[1] >= 3]
        if not candidates:  # 理论不达(鸽巢);兜底取张数最多者
            candidates = [max(counts, key=lambda c: c[1])]
        min_count = min(c[1] for c in candidates)
        tied = [c[0] for c in candidates if c[1] == min_count]
        if len(tied) == 1:
            return tied[0]
        best_suit = tied[0]
        best_shanten = 99
        for suit in tied:
            s = shanten(hand, suit, melds)
            if s < best_shanten:
                best_shanten = s
                best_suit = suit
        return best_suit

    # ---- 定缺:张数最少的门 ----

    def choose_lack(self, view: PlayerView) -> int:
        return self._weakest_suit(view.hand, view.meld_count)

    # ---- 自家摸牌后 ----

    def choose_turn_action(self, view: PlayerView, drawn: int | None) -> Action:
        acts = legal_self_actions(view, drawn)
        # 能胡必胡
        for a in acts:
            if a.kind == "tsumo":
                return a

        result = analyze(view, weights=self._weights())
        cur_shanten = result.hand.shanten

        # 杠(暗杠/补杠):仅 tenpai 时(mid/strong,保守 v0);优先暗杠(无抢杠风险)
        if self.strength in ("mid", "strong") and cur_shanten == 0:
            for a in acts:
                if a.kind == "ankan":
                    return a
            for a in acts:
                if a.kind == "shouminkan":
                    return a

        # 弃牌
        discards = [a for a in acts if a.kind == "discard"]
        if discards:
            return self._choose_discard(discards, result)

        # 兜底(理论不达):返回首个合法
        return acts[0]

    # ---- 他人弃牌后申索 ----

    def choose_claim(self, view: PlayerView, claimable: list[Action]) -> Action:
        # 能胡必胡
        for a in claimable:
            if a.kind == "ron":
                return a

        result = analyze(view, weights=self._weights())
        cur_shanten = result.hand.shanten
        claim = result.claim

        # 碰
        pon_act = next((a for a in claimable if a.kind == "pon"), None)
        if pon_act is not None and claim and claim.get("pon_shanten_after") is not None:
            pon_after = claim["pon_shanten_after"]  # type: ignore[index]
            if self._should_pon(cur_shanten, pon_after):
                return pon_act

        # 大明杠:仅 strong + 下叫
        dm_act = next((a for a in claimable if a.kind == "daiminkan"), None)
        if dm_act is not None and self.strength == "strong" and cur_shanten == 0:
            return dm_act

        return pass_action()

    # ---- 策略助手 ----

    def _should_pon(self, cur_shanten: int, pon_after: int) -> bool:
        """碰判定(见计划 §7):严格改善为基线;弱=改善且 50% 随机;强=改善或保持下叫。"""
        improves = pon_after < cur_shanten
        if self.strength == "weak":
            return improves and self.rng.random() < 0.5
        if self.strength == "strong":
            # 改善,或保持下叫(已 tenpai 且碰后仍 tenpai)
            return improves or (cur_shanten == 0 and pon_after == 0)
        # mid
        return improves

    def _choose_discard(self, discards: list[Action], result) -> Action:
        """弃牌:强=贪心降向听(最低 shanten_after,平手最宽叫);中=recommend;弱=top-3 随机。

        强档用贪心降向听(直接冲下叫)实测远优于综合排序--赢得多即"强";中档用
        analyze 综合推荐;弱档在 top-3 候选随机。均消费 analyze(view) 的候选,不重算规则。
        """
        cands = result.candidates  # 已按综合降序,tie 升序
        if not cands:
            return discards[0]
        if self.strength == "strong":
            # 最低 shanten_after,平手取叫牌最宽(ukeire_count 多、未见张多)
            best = min(
                cands,
                key=lambda c: (c.shanten_after, -c.ukeire_count, -c.ukeire_remaining_total, c.tile),
            )
            for a in discards:
                if a.tile == best.tile:
                    return a
            return discards[0]
        if self.strength == "weak":
            top_tiles = {c.tile for c in cands[:3]}
            choices = [a for a in discards if a.tile in top_tiles]
            if not choices:
                choices = discards
            return self.rng.choice(choices)
        # mid:recommend(综合最高)
        rec_tile = result.recommend.tile if result.recommend else cands[0].tile
        for a in discards:
            if a.tile == rec_tile:
                return a
        return discards[0]

    def _weakest_suit(self, hand, melds: int) -> int:
        """张数最少的门;平手取结构最弱(弃后向听最低 = 该门贡献最小、最该缺)。"""
        counts = []
        for suit in range(3):
            base = suit * 9
            total = sum(hand.count(i) for i in range(base, base + 9))
            counts.append((suit, total))
        min_count = min(c[1] for c in counts)
        tied = [c[0] for c in counts if c[1] == min_count]
        if len(tied) == 1:
            return tied[0]
        # 平手:取"弃后向听最低"的门(剩余两门结构最好 => 该门贡献最小、最该缺);
        # 再平手取索引最小。shanten(hand, lack=S) 把 S 视为禁门,值越低说明不靠 S 也越接近下叫。
        best_suit = tied[0]
        best_shanten = 99
        for suit in tied:
            s = shanten(hand, suit, melds)
            if s < best_shanten:
                best_shanten = s
                best_suit = suit
        return best_suit
