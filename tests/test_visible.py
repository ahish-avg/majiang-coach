"""tests for analysis/visible.py (Phase 3).

覆盖(钉死 §6.2):
  - sum(visible)+sum(remaining) == 108 恒成立。
  - 自家暗手 / 自家副露 / 全部弃牌 / 全部公开副露 计入正确,不重复。
  - 未见张语义 = 4 - visible;未见0 = 全壁。
  - 注释明示未见张 = 牌墙 + 他家暗手。
"""

from __future__ import annotations

from majiang_coach.analysis.visible import visible_counts, remaining_counts
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand


def _view(hand_codes, melds=(), public_melds=None, discards=None, lack=None):
    hand = Hand.from_codes(hand_codes)
    pm = public_melds if public_melds is not None else (tuple(melds), (), (), ())
    dc = discards if discards is not None else ((), (), (), ())
    return PlayerView(
        seat=0, hand=hand, melds=tuple(melds), lack_suit=lack,
        public_melds=pm, discards=dc,
    )


def test_sum_conservation_108():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    vis = visible_counts(v)
    rem = remaining_counts(v)
    assert sum(vis) + sum(rem) == 108
    assert len(vis) == 27 and len(rem) == 27


def test_self_hand_counted():
    v = _view(["1m2m3m", "5s5s"])
    vis = visible_counts(v)
    # 1m,2m,3m 各 1;5s=2(idx 13)
    assert vis[0] == 1 and vis[1] == 1 and vis[2] == 1
    assert vis[13] == 2


def test_self_meld_counted_once_via_public():
    # 自家碰 5s(3 张副露);public_melds[0] 含该碰;不应重复计
    pon = Meld(kind="pon", tile=13, src_seat=1)
    v = _view(["1m2m3m"], melds=(pon,),
              public_melds=((pon,), (), (), ()))
    vis = visible_counts(v)
    assert vis[13] == 3  # 碰 3 张;暗手无 5s
    assert vis[0] == 1 and vis[1] == 1 and vis[2] == 1


def test_kan_meld_counts_four():
    ankan = Meld(kind="ankan", tile=4)  # 5m=4,4 张
    v = _view(["1s2s3s"], melds=(ankan,),
              public_melds=((ankan,), (), (), ()))
    vis = visible_counts(v)
    assert vis[4] == 4  # 暗杠 4 张


def test_discards_counted():
    v = _view(["1m2m3m"], discards=((5, 5), (9,), (), (7, 7, 7)))
    vis = visible_counts(v)
    assert vis[5] == 2   # 座0 弃两张 6m(idx5)
    assert vis[9] == 1   # 座1 弃 1s(idx9)
    assert vis[7] == 3   # 座3 弃三张 8m(idx7)


def test_other_seat_melds_counted():
    pon = Meld(kind="pon", tile=22, src_seat=0)  # 5p=22,他座碰
    v = _view(["1m2m3m"], public_melds=((), (pon,), (), ()))
    vis = visible_counts(v)
    assert vis[22] == 3


def test_remaining_is_four_minus_visible():
    v = _view(["1m1m1m1m", "5s5s"], discards=((5,), (), (), ()))
    vis = visible_counts(v)
    rem = remaining_counts(v)
    for i in range(27):
        assert rem[i] == 4 - vis[i]
    # 1m 已 4 张可见 -> 未见0(全壁)
    assert rem[0] == 0
    # 6m(idx5)可见1 -> 未见3
    assert rem[5] == 3


def test_remaining_zero_means_all_visible():
    # 5m(idx4) 在暗手2 + 他座碰3 = 5? 不合法;构造 4 张全可见
    v = _view(["5m5m"], discards=((4, 4), (), (), ()))  # 暗手2 + 弃2 = 4
    rem = remaining_counts(v)
    assert rem[4] == 0  # 全壁
