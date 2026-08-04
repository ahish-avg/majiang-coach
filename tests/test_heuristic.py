"""tests for ai/heuristic.py: 启发式 AI 对手。

覆盖:能胡必胡、只出合法动作、强度单调(strong>weak vs Random)、碰/杠策略、
定缺/换三张、弃牌策略(强=贪心降向听)。
"""

from __future__ import annotations

import pytest

from majiang_coach import tiles
from majiang_coach.ai import HeuristicActor
from majiang_coach.engine.action import (
    Action, legal_self_actions, legal_claims, pass_action,
)
from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand
from majiang_coach.shanten import shanten

_S5 = 13  # 5s


def _view(hand_codes, lack=2, melds=None, last_discard=None, wall=30,
          discards=((), (), (), ()), public_melds=None, active=(0, 1, 2, 3)) -> PlayerView:
    hand = Hand.from_codes(hand_codes)
    ml = tuple(melds or [])
    pm = public_melds if public_melds is not None else (ml, (), (), ())
    ld = None
    if last_discard is not None:
        ld = (1, last_discard)
    lack_suits = (lack, lack, lack, lack) if lack is not None else ()
    return PlayerView(
        seat=0, hand=hand, melds=ml, lack_suit=lack, lack_suits=lack_suits,
        public_melds=pm, discards=tuple(discards), wall_remaining=wall,
        last_discard=ld, active_seats=tuple(active),
    )


# ===== 能胡必胡 =====

def test_must_win_tsumo_all_strengths():
    """14 张已胡:所有强度必取 tsumo。"""
    hand = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"]  # 14 张,胡
    for st in ("weak", "mid", "strong"):
        actor = HeuristicActor(st, 0)
        view = _view(hand, lack=2)
        acts = legal_self_actions(view, _S5)
        act = actor.choose_turn_action(view, _S5)
        assert act.kind == "tsumo", f"{st} 未必胡(自摸)"
        assert act in acts


def test_must_win_ron_all_strengths():
    """他人弃牌可胡:所有强度必取 ron。"""
    hand = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]  # 13 张听 5s
    for st in ("weak", "mid", "strong"):
        actor = HeuristicActor(st, 0)
        view = _view(hand, lack=2, last_discard=_S5)
        claimable = legal_claims(view, _S5)
        assert any(a.kind == "ron" for a in claimable)
        act = actor.choose_claim(view, claimable + [pass_action()])
        assert act.kind == "ron", f"{st} 未必胡(点炮)"


# ===== 只出合法动作(全启发式跑局无非法)=====

@pytest.mark.parametrize("strength", ("weak", "mid", "strong"))
def test_only_legal_actions_full_game(strength):
    """4 个同强度启发式跑一局,Game 内部校验合法(不抛异常即全合法)。"""
    for s in (0, 1, 2, 3):
        actors = [HeuristicActor(strength, s * 4 + i) for i in range(4)]
        Game(actors, s).run()  # 不抛 ValueError 即合法


@pytest.mark.parametrize("strength", ("weak", "mid", "strong"))
def test_only_legal_actions_mixed(strength):
    """混合强度跑局无非法动作。"""
    for s in (0, 5, 11):
        actors = [
            HeuristicActor("weak", s + 1), HeuristicActor("mid", s + 2),
            HeuristicActor("strong", s + 3), RandomActor(s + 4),
        ]
        Game(actors, s).run()


# ===== 强度单调:strong 胜率 > weak(vs RandomActor 种子赛)=====

def test_strength_monotonic_strong_beats_weak():
    """strong 在 seat0 vs 3 RandomActor 的胜局数显著多于 weak(同对手种子)。"""
    N = 80

    def wins_for(strength):
        w = 0
        for s in range(N):
            actors = [HeuristicActor(strength, s * 4) if i == 0
                      else RandomActor(s * 4 + i + 700) for i in range(4)]
            r = Game(actors, s).run()
            if 0 in [x["seat"] for x in r.result["winners"]]:
                w += 1
        return w

    weak_w = wins_for("weak")
    strong_w = wins_for("strong")
    assert strong_w > weak_w, f"非单调: strong={strong_w} <= weak={weak_w}"


# ===== 弃牌策略:强=贪心降向听 =====

def test_strong_discard_reduces_shanten():
    """强档弃牌应取最低 shanten_after(贪心降向听)。"""
    # 14 张,差一张下叫的手牌:弃某张能降向听
    hand = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "4s5s"]  # 14 张
    actor = HeuristicActor("strong", 0)
    view = _view(hand, lack=2)
    acts = legal_self_actions(view, tiles.code_to_index("4s"))
    discards = [a for a in acts if a.kind == "discard"]
    act = actor.choose_turn_action(view, tiles.code_to_index("4s"))
    assert act.kind == "discard"
    # 强档选的牌应使弃后 shanten 不高于任意其他弃牌
    from majiang_coach.analysis import analyze
    res = analyze(view)
    chosen = next(c for c in res.candidates if c.tile == act.tile)
    min_sh = min(c.shanten_after for c in res.candidates)
    assert chosen.shanten_after == min_sh


def test_weak_discard_among_top3():
    """弱档弃牌应在 top-3 候选内(多次抽样)。"""
    hand = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "4s5s"]
    from majiang_coach.analysis import analyze
    view = _view(hand, lack=2)
    res = analyze(view)
    top3 = {c.tile for c in res.candidates[:3]}
    actor = HeuristicActor("weak", 123)
    for _ in range(20):
        act = actor.choose_turn_action(view, tiles.code_to_index("4s"))
        assert act.kind == "discard"
        assert act.tile in top3


# ===== 碰策略 =====

def test_pon_when_improves():
    """碰后向读严格下降且非胡:mid/strong 必碰。

    手牌(向读1)碰 5s 后下叫(向读0),但摸入 5s 不胡(非 ron)--隔离能胡必胡干扰。
    """
    codes = ["2s", "5m", "4s", "2m", "3m", "9s", "4m", "3s", "2m", "8s", "7m", "5s", "5s"]
    view = _view(codes, lack=2, last_discard=_S5)
    claimable = legal_claims(view, _S5)
    assert any(a.kind == "pon" for a in claimable)
    from majiang_coach.analysis import analyze
    res = analyze(view)
    assert not res.claim["can_ron"]  # 非 ron,避免能胡必胡抢先
    assert res.claim["pon_shanten_after"] < res.hand.shanten  # 确实改善
    for st in ("mid", "strong"):
        actor = HeuristicActor(st, 0)
        act = actor.choose_claim(view, claimable + [pass_action()])
        assert act.kind == "pon", f"{st} 应碰(改善)"


def test_no_pon_when_not_improves():
    """碰后向读不降(打散将对):mid 过(不碰)。

    手牌 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s(已下叫,5s5s 为将);碰 5s 失将 -> 向读升。
    """
    hand = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"]  # 13 张,缺筒,已下叫
    view = _view(hand, lack=2, last_discard=_S5)
    claimable = legal_claims(view, _S5)
    from majiang_coach.analysis import analyze
    res = analyze(view)
    pon_after = res.claim["pon_shanten_after"] if res.claim else None
    cur = res.hand.shanten
    if pon_after is None or not claimable or pon_after >= cur:
        # 碰不改善:mid/strong 均应过(强档"保持下叫"要求 pon_after==0,此处不满足)
        actor = HeuristicActor("mid", 0)
        act = actor.choose_claim(view, claimable + [pass_action()])
        assert act.kind == "pass", "mid 不应在碰后不改善时碰"
        actor2 = HeuristicActor("strong", 0)
        act2 = actor2.choose_claim(view, claimable + [pass_action()])
        assert act2.kind == "pass", "strong 不应在碰后失去下叫时碰"


# ===== 杠策略:仅 tenpai 时 =====

def test_ankan_only_when_tenpai():
    """暗杠仅 tenpai 时(mid/strong);非 tenpai 不杠。"""
    # tenpai + 4 张同牌
    hand_tenpai = ["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m"]  # 13 张(4+3+3+3),缺筒 -> 听? 4张5s作2对+面子...
    # 用更明确的 tenpai:1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s5s5s = 3+3+3+3+4=16 太多
    # 14 张刚摸态 tenpai 含暗刻:1m2m3m 4m5m6m 7m8m9m 5s5s5s5s = 3+3+3+4=13, +摸=14
    hand14 = ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s5s5s"]  # 13 张
    view = _view(hand14, lack=2)
    drawn = _S5  # 摸第4张5s? 已4张. 改用别的
    # 重新构造:14 张 tenpai,暗刻 5m(4张)
    hand14 = ["5m5m5m5m", "1s2s3s", "4s5s6s", "7s8s9s", "1s"]  # 4+3+3+3+1=14,缺筒
    view = _view(hand14, lack=2)
    acts = legal_self_actions(view, tiles.code_to_index("1s"))
    assert any(a.kind == "ankan" for a in acts), "应可暗杠5m"
    assert shanten(view.hand, 2, 0) == 0, "应已 tenpai"
    for st in ("mid", "strong"):
        actor = HeuristicActor(st, 0)
        act = actor.choose_turn_action(view, tiles.code_to_index("1s"))
        assert act.kind == "ankan", f"{st} tenpai 应暗杠"

    # 非 tenpai:不杠
    hand_notp = ["5m5m5m5m", "1s2s", "4s5s", "7s8s", "1m2m"]  # 4+2+2+2+2=12? 需14
    hand_notp = ["5m5m5m5m", "1s2s3s", "4s5s", "7s8s", "1m2m", "4m"]  # 4+3+2+2+2+1=14,缺筒,非tenpai
    view2 = _view(hand_notp, lack=2)
    assert shanten(view2.hand, 2, 0) > 0, "应非 tenpai"
    acts2 = legal_self_actions(view2, tiles.code_to_index("4m"))
    assert any(a.kind == "ankan" for a in acts2)
    for st in ("mid", "strong"):
        actor = HeuristicActor(st, 0)
        act = actor.choose_turn_action(view2, tiles.code_to_index("4m"))
        assert act.kind != "ankan", f"{st} 非 tenpai 不应暗杠"


def test_weak_never_kan():
    """弱档永不杠(最保守)。"""
    hand14 = ["5m5m5m5m", "1s2s3s", "4s5s6s", "7s8s9s", "1s"]  # tenpai
    view = _view(hand14, lack=2)
    actor = HeuristicActor("weak", 0)
    act = actor.choose_turn_action(view, tiles.code_to_index("1s"))
    assert act.kind != "ankan"


# ===== 定缺 / 换三张 =====

def test_choose_lack_fewest_suit():
    """定缺取张数最少的门。"""
    # 万 5、条 4、筒 3 -> 缺筒(2)
    hand = ["1m2m3m4m5m", "1s2s3s4s", "1p2p3p"]  # 5+4+3=12? 需13
    hand = ["1m2m3m4m5m6m", "1s2s3s4s", "1p2p3p"]  # 6+4+3=13
    view = _view(hand, lack=None)
    actor = HeuristicActor("mid", 0)
    lack = actor.choose_lack(view)
    assert lack == 2, f"应缺筒(最少),得到 {lack}"


def test_choose_swap_same_suit_three():
    """换三张给同门 3 张。"""
    hand = ["1m2m3m4m5m6m", "1s2s3s4s", "1p2p3p"]  # 万6 条4 筒3
    view = _view(hand, lack=None)
    for st in ("weak", "mid", "strong"):
        actor = HeuristicActor(st, 0)
        t3 = actor.choose_swap(view)
        assert len(t3) == 3
        suits = {tiles.suit_of(t) for t in t3}
        assert len(suits) == 1, f"{st} 换三张须同门"
        # 给出的 3 张手中须真有
        for t in t3:
            assert view.hand.count(t) >= 1


def test_choose_swap_dumps_weakest_dumpable():
    """换三张倾倒最弱可倾倒门(>=3 张中张数最少者)。"""
    # 万 6、条 4、筒 3 -> 倾倒筒(3 张)
    hand = ["1m2m3m4m5m6m", "1s2s3s4s", "1p2p3p"]
    view = _view(hand, lack=None)
    actor = HeuristicActor("strong", 0)
    t3 = actor.choose_swap(view)
    assert tiles.suit_of(t3[0]) == 2, "应倾倒筒门(最少且>=3)"
