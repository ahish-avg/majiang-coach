"""tests for analysis/threat.py (Phase 3 v0,见计划 §6.4)。

只验单调趋势(副露多/缺门清/晚巡 -> 威胁更高)与范围 0..1,不钉绝对值。
"""

from __future__ import annotations

from majiang_coach.analysis.threat import opponent_threat, opp_lack
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand


def _view(public_melds=((), (), (), ()), discards=None, lack_suits=(), wall=50):
    dc = discards if discards is not None else ((), (), (), ())
    return PlayerView(
        seat=0, hand=Hand.from_codes(["1m2m3m"]), lack_suits=lack_suits,
        public_melds=public_melds, discards=dc, wall_remaining=wall,
    )


def test_threat_range_and_basics():
    v = _view()
    t = opponent_threat(v, 1)
    assert 0.0 <= t <= 1.0
    assert t == 0.0  # 无副露、无缺门清、不晚巡


def test_more_melds_higher_threat():
    v0 = _view(public_melds=((), (), (), ()))
    pon = Meld(kind="pon", tile=4, src_seat=0)
    v1 = _view(public_melds=((), (pon,), (), ()))
    v2 = _view(public_melds=((), (pon, pon), (), ()))
    t0 = opponent_threat(v0, 1)
    t1 = opponent_threat(v1, 1)
    t2 = opponent_threat(v2, 1)
    assert t0 < t1 < t2


def test_meld_cap_at_06():
    # 5 副露 -> 0.15*5=0.75 cap 0.6
    pon = Meld(kind="pon", tile=4, src_seat=0)
    v = _view(public_melds=((), (pon,) * 5, (), ()))
    # 副露贡献应被 cap 在 0.6
    assert opponent_threat(v, 1) == 0.6


def test_lack_cleared_higher_threat():
    # 座1 缺筒(2),最近弃牌非筒 -> 已清;对照最近弃牌为筒 -> 未清
    lack_suits = (2, 2, 0, 0)
    v_cleared = _view(discards=((), (0,), (), ()), lack_suits=lack_suits)  # 弃1m(万,非筒)
    v_not = _view(discards=((), (18,), (), ()), lack_suits=lack_suits)     # 弃1p(筒=缺门)
    assert opponent_threat(v_cleared, 1) > opponent_threat(v_not, 1)


def test_late_wall_higher_threat():
    v_early = _view(wall=50)
    v_late = _view(wall=10)
    assert opponent_threat(v_late, 1) > opponent_threat(v_early, 1)


def test_threat_combined_capped_at_1():
    pon = Meld(kind="pon", tile=4, src_seat=0)
    # 5 副露(0.6) + 缺门清(0.2) + 晚巡(0.2) = 1.0
    v = _view(
        public_melds=((), (pon,) * 5, (), ()),
        discards=((), (0,), (), ()),
        lack_suits=(2, 2, 0, 0),
        wall=10,
    )
    assert opponent_threat(v, 1) == 1.0


def test_opp_lack_helper():
    v = _view(lack_suits=(2, 0, 1, None))
    assert opp_lack(v, 0) == 2
    assert opp_lack(v, 3) is None
    assert opp_lack(v, 5) is None  # 越界
