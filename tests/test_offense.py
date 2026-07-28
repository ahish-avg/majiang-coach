"""tests for analysis/offense.py (Phase 3,见计划 §6.6)。

覆盖(钉死真实性质,非绝对魔数):
  - 已胡(s=-1)-> score 100(最大,胜过任何未胡)。
  - 死待(remaining0)不计进攻分:杀光进张后 score 退回 base。
  - base 单调:杀光进张后 下叫(50) > 差1(25)。
  - 活待 > 死待(同结构,进张未见多 -> 更高)。
  - 进张宽 > 窄(同差张下叫,活进张多 -> 更高)。
  - 副露通路(melds>0)。
"""

from __future__ import annotations

from majiang_coach.analysis.offense import offense_of
from majiang_coach.analysis.visible import remaining_counts
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand
from majiang_coach.shanten import shanten


def _view(hand_codes, discards=None, lack_suits=(2, 2, 0, 0), wall=30, melds=()):
    h = Hand.from_codes(hand_codes)
    dc = discards if discards is not None else ((), (), (), ())
    return PlayerView(
        seat=0, hand=h, melds=tuple(melds), lack_suits=lack_suits,
        public_melds=(tuple(melds), (), (), ()), discards=dc,
        wall_remaining=wall, active_seats=(0, 1),
    )


def _wall_suit(suit: int, hand: Hand) -> tuple:
    """构造弃牌 tuple,把 suit 门 9 张全部 wall 到 visible=4(remaining=0)。

    扣除暗手中已有的张数,余量放进座1 弃牌堆。
    """
    base = suit * 9
    extras = []
    for n in range(9):
        idx = base + n
        need = 4 - hand.count(idx)
        extras.extend([idx] * need)
    return ((), tuple(extras), (), ())


# ---- 已胡 -> 100 ----

def test_win_scores_max():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])  # 14t 胡
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    o = offense_of(h, 2, 0, v)
    assert o.shanten == -1
    assert o.score == 100
    assert o.is_tenpai is False


# ---- 死待不计 + base 单调 ----

def test_dead_wait_tenpai_is_base_50():
    # tanki 5s 单吊叫;杀光 5s(remaining0)-> 无活进张 -> score=base[0]=50
    codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]
    h = Hand.from_codes(codes)
    assert shanten(h, 2, 0) == 0
    v = _view(codes, discards=_wall_suit(1, h))  # wall 整个条门(5s 在条)
    rem = remaining_counts(v)
    assert rem[13] == 0  # 5s 全壁
    o = offense_of(h, 2, 0, v)
    assert o.score == 50  # base,死待不计
    assert o.ukeire_count >= 1  # 结构上仍有叫牌
    assert all(rem[u.tile_index] == 0 for u in o.ukeire)  # 但全死


def test_base_monotonic_dead_waits():
    """杀光进张后:下叫(50) > 差1(25)。base 单调。"""
    # 下叫:tanki 5s,wall 条门 -> score 50
    tenpai = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]
    h0 = Hand.from_codes(tenpai)
    assert shanten(h0, 2, 0) == 0
    v0 = _view(tenpai, discards=_wall_suit(1, h0))
    s0 = offense_of(h0, 2, 0, v0).score
    # 差1:3 面子 + 2 嵌张(无将),wall 条门 -> score 25
    one = ["1m2m3m", "4m5m6m", "7m8m9m", "6s8s", "4s6s"]
    h1 = Hand.from_codes(one)
    assert shanten(h1, 2, 0) == 1
    v1 = _view(one, discards=_wall_suit(1, h1))
    s1 = offense_of(h1, 2, 0, v1).score
    assert s0 == 50
    assert s1 == 25
    assert s0 > s1


# ---- 活待 > 死待 ----

def test_live_wait_higher_than_dead():
    codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]  # tanki 5s
    h = Hand.from_codes(codes)
    v_live = _view(codes)  # 5s 未见(remaining 3)
    v_dead = _view(codes, discards=_wall_suit(1, h))  # 5s 全壁
    s_live = offense_of(h, 2, 0, v_live).score
    s_dead = offense_of(h, 2, 0, v_dead).score
    assert s_live > s_dead  # 活待加分
    assert s_dead == 50


# ---- 进张宽 > 窄(同差张下叫) ----

def test_wider_ukeire_higher():
    # 两个差1手:窄(3 进张) vs 宽(6 进张),base 同为 25
    narrow = ["1m2m3m", "4m5m6m", "1m4m", "7s8s", "4s5s", "9m"]   # 进张 3s,6s,9s(3)
    wide = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s", "4s5s"]         # 进张 1s-6s(6)
    hn = Hand.from_codes(narrow)
    hw = Hand.from_codes(wide)
    assert shanten(hn, 2, 0) == 1 and shanten(hw, 2, 0) == 1
    on = offense_of(hn, 2, 0, _view(narrow))
    ow = offense_of(hw, 2, 0, _view(wide))
    assert ow.ukeire_count > on.ukeire_count  # 6 > 3
    assert ow.score > on.score  # 宽手活进张更多 -> 更高


# ---- 未见多 > 少(同结构,进张 remaining 多 -> 更高) ----

def test_more_remaining_higher():
    codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]  # tanki 5s
    h = Hand.from_codes(codes)
    # 视图A:5s 未见3(仅暗手1);视图B:5s 未见1(暗手1 + 弃2)
    v_more = _view(codes)
    v_less = _view(codes, discards=((), (13, 13), (), ()))  # 座1 弃两张 5s
    s_more = offense_of(h, 2, 0, v_more).score
    s_less = offense_of(h, 2, 0, v_less).score
    assert s_more > s_less


# ---- 副露通路(melds>0) ----

def test_melds1_tenpai():
    # melds=1 待摸态 10 张:3 面子 + 单吊 5s
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    o = offense_of(h, 2, 1, v)
    assert o.shanten == 0
    assert o.is_tenpai is True
    assert o.ukeire_count == 1
    assert o.ukeire[0].code == "5s"
    assert o.score > 50  # base 50 + 活待


def test_melds1_dead_wait():
    # melds=1 tanki 5s,wall 条门 -> score=base[0]=50
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s"], discards=_wall_suit(1, h))
    o = offense_of(h, 2, 1, v)
    assert o.score == 50


def test_score_clamped_0_100():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])  # 胡
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert offense_of(h, 2, 0, v).score == 100  # 上界
