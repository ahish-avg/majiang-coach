"""tests for analysis/safety.py (Phase 3,见计划 §6.3 / §6.5)。

钉死相对关系(非绝对魔数):
  - 未见0 绝对安全(danger 0)。
  - 对手缺门牌对该对手 danger 0。
  - 壁(4m 全壁)弃 5m 危险度 < 无壁弃 5m;壁越多危险越低(单调)。
  - 现物 remaining>0 仍 >0(非硬安全)。
  - 早巡 < 晚巡;remaining 多 > 少。
  - 逐对手明细齐全。
"""

from __future__ import annotations

from majiang_coach.analysis.safety import safety_of, seat_relative_name
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand


def _view(hand_codes, discards=None, lack_suits=(), public_melds=None,
          wall=30, active=(0, 1, 2, 3)):
    dc = discards if discards is not None else ((), (), (), ())
    pm = public_melds if public_melds is not None else ((), (), (), ())
    return PlayerView(
        seat=0, hand=Hand.from_codes(hand_codes), lack_suits=lack_suits,
        public_melds=pm, discards=dc, wall_remaining=wall,
        active_seats=tuple(active),
    )


# ---- 未见0 绝对安全 ----

def test_remaining_zero_absolute_safety():
    # 1m(idx0) 在暗手 4 张 -> visible 4 -> remaining 0 -> 绝对安全
    v = _view(["1m1m1m1m", "5s5s"])
    s = safety_of(0, v)
    assert s.danger == 0
    assert s.defense_score == 100
    assert s.per_opponent == []  # 短路,无逐对手


# ---- 对手缺门牌对该对手 0 ----

def test_opponent_lack_suit_zero_for_that_opp():
    # 座1 缺筒(2);评估 5p(idx22,筒)。座1 的 danger 应为 0
    v = _view(["5p5p", "5m5m"], lack_suits=(2, 2, 0, 0), active=(0, 1))
    s = safety_of(22, v)  # 5p
    opp1 = [o for o in s.per_opponent if o.seat == 1][0]
    assert opp1.danger == 0
    assert opp1.lack == 2
    assert any("缺筒" in r for r in opp1.reasons)


def test_all_opps_lack_then_danger_zero():
    # 仅一个对手座1,缺筒;弃 5p -> 对其绝对安全 -> danger 0
    v = _view(["5p5p", "5m5m"], lack_suits=(2, 2, 0, 0), active=(0, 1))
    s = safety_of(22, v)
    assert s.danger == 0


# ---- 壁(4m 全壁)削弱 ----

def test_kabe_4m_wall_lowers_5m_danger():
    """4m 全壁(弃牌堆 4 张 4m)弃 5m 危险度 < 无壁弃 5m。"""
    # 无壁:5m(idx4) 仅在暗手 1 张;4m 无可见
    v_no = _view(["5m", "5s5s"], discards=((), (), (), ()), active=(0, 1))
    # 4m 全壁:4 张 4m(idx3) 全在弃牌堆(座1 弃 4 张),5m 仍在暗手
    v_wall = _view(["5m", "5s5s"], discards=((), (3, 3, 3, 3), (), ()), active=(0, 1))
    d_no = safety_of(4, v_no).danger
    d_wall = safety_of(4, v_wall).danger
    assert d_wall < d_no, f"壁应削弱危险度:wall={d_wall} no={d_no}"


def test_kabe_monotonic_more_walls_lower():
    """壁越多(4m+6m 全壁)危险越低(单调)。"""
    # 5m(idx4) 待胡形状伙伴含 4m(idx3,形状[3,4]? 非;实际 [X-2,X-1]=[2,3],
    # [X-1,X+1]=[3,5])。4m(idx3) 全壁削弱;再加 6m(idx5) 全壁([X+1,X+2]=[5,6]、[X-1,X+1]=[3,5])进一步削弱。
    v_one = _view(["5m", "5s5s"], discards=((), (3, 3, 3, 3), (), ()), active=(0, 1))
    v_two = _view(["5m", "5s5s"],
                  discards=((), (3, 3, 3, 3, 5, 5, 5, 5), (), ()), active=(0, 1))
    d_one = safety_of(4, v_one).danger
    d_two = safety_of(4, v_two).danger
    assert d_two <= d_one, f"更多壁应更安全:two={d_two} one={d_one}"


# ---- 现物非硬安全 ----

def test_genbutsu_not_hard_safe():
    # 5m 在座1 弃牌堆(现物),但 remaining>0 -> danger 仍 >0
    v = _view(["5m", "5s5s"], discards=((), (4,), (), ()), active=(0, 1))
    s = safety_of(4, v)
    assert s.danger > 0  # 现物非硬安全
    opp1 = [o for o in s.per_opponent if o.seat == 1][0]
    assert any("现物" in r for r in opp1.reasons)


# ---- 早巡 < 晚巡 ----

def test_early_lower_than_late():
    # 同牌同局,仅 wall_remaining 不同:早巡(50) < 晚巡(10)
    v_early = _view(["5m", "5s5s"], wall=50, active=(0, 1))
    v_late = _view(["5m", "5s5s"], wall=10, active=(0, 1))
    d_early = safety_of(4, v_early).danger
    d_late = safety_of(4, v_late).danger
    assert d_early < d_late, f"早巡应更安全:early={d_early} late={d_late}"


# ---- remaining 多 > 少 ----

def test_more_remaining_more_danger():
    # 5m(idx4):仅暗手1张 -> remaining 3(base 45)
    # 5s(idx13):暗手1 + 座1弃2 -> remaining 1(base 15,且现物×0.8)
    v = _view(["5m", "5s"], discards=((), (13, 13), (), ()), active=(0, 1))
    d_m = safety_of(4, v).danger   # remaining 3
    d_s = safety_of(13, v).danger  # remaining 1
    assert d_m > d_s, f"未见多应更危险:m={d_m} s={d_s}"


# ---- 逐对手明细 ----

def test_per_opponent_complete():
    v = _view(["5m", "5s5s"], lack_suits=(2, 2, 0, 0), active=(0, 1, 2, 3))
    s = safety_of(4, v)  # 5m(万);座1缺筒不影响万
    seats = [o.seat for o in s.per_opponent]
    assert set(seats) == {1, 2, 3}  # 排除自家
    for o in s.per_opponent:
        assert 0 <= o.danger <= 100
        assert 0.0 <= o.threat <= 1.0


def test_seat_relative_name():
    assert seat_relative_name(0, 1) == "下家"
    assert seat_relative_name(0, 2) == "对家"
    assert seat_relative_name(0, 3) == "上家"
    assert seat_relative_name(2, 0) == "对家"


def test_danger_defense_sum_100():
    v = _view(["5m", "5s5s"], active=(0, 1))
    s = safety_of(4, v)
    assert s.danger + s.defense_score == 100
