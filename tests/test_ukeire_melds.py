"""tests for ukeire() melds extension (Phase 3).

覆盖:
  - melds=0 回归(含 14 张报错用例)。
  - melds=1/2 下叫叫牌(待ち)、进张(改善牌)。
  - 属性:副露胡牌去一牌 -> 下叫,其 ukeire 非空且被去牌必在 ukeire(摸回即胡)。
  - 缺门牌不在 ukeire;四张上限排除。
"""

from __future__ import annotations

import pytest

from majiang_coach.hand import Hand
from majiang_coach.shanten import shanten
from majiang_coach.ukeire import ukeire, ukeire_codes


def _codes(result):
    return [u.code for u in result]


# ---- melds=0 回归 ----

def test_melds0_default_equals_explicit():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert _codes(ukeire(h)) == ["5s"]
    assert _codes(ukeire(h, None, 0)) == _codes(ukeire(h))


def test_melds0_non_13_raises():
    h14 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    with pytest.raises(ValueError):
        ukeire(h14, None, 0)


# ---- melds=1: 待摸态 10 张 ----

def test_melds1_tenpai_single_wait():
    # 3 面子 + 1 浮牌(5s 单吊叫) -> 待ち 5s,new_shanten=-1
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 0
    res = ukeire(h, 2, 1)
    assert _codes(res) == ["5s"]
    assert res[0].new_shanten == -1


def test_melds1_tenpai_ryanmen():
    # 2 面子 + 5s5s 将对 + 3m4m 两面 -> 待ち 2m,5m
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "5s5s", "3m4m"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 0
    res = ukeire(h, 2, 1)
    assert _codes(res) == ["2m", "5m"]
    assert all(u.new_shanten == -1 for u in res)


def test_melds1_one_shanten_improvers():
    # 2 面子 + 2 搭子(无将) -> 差 1 张;进张摸入后向听=0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s8s", "4s5s"])
    assert shanten(h, 2, 1) == 1
    res = ukeire(h, 2, 1)
    assert len(res) > 0
    assert all(u.new_shanten == 0 for u in res)  # 差 1 张摸一张最多到下叫(0)


def test_melds1_improver_lowers_shanten():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s8s", "4s5s"])
    base = shanten(h, 2, 1)
    for u in ukeire(h, 2, 1):
        assert u.new_shanten < base
        assert shanten(h.add(u.tile_index), 2, 1) == u.new_shanten


def test_melds1_lack_tile_not_in_ukeire():
    # 3 面子 + 1 筒缺门孤立 -> 差 1 张;摸缺门牌(筒)不改善
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5p"])
    assert shanten(h, 2, 1) == 1
    res = ukeire(h, 2, 1)
    assert "5p" not in _codes(res)
    assert len(res) > 0  # 摸任意非缺门牌,弃 5p 后单吊叫


def test_melds1_invalid_count_raises():
    # melds=1 输入须 10 张;11/13 张应报错
    h11 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    with pytest.raises(ValueError):
        ukeire(h11, 2, 1)


# ---- melds=2: 待摸态 7 张 ----

def test_melds2_tenpai():
    # 2 面子 + 1 浮牌(7s 单吊) -> 待ち 7s
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s"])
    assert h.total == 7
    assert shanten(h, 2, 2) == 0
    res = ukeire(h, 2, 2)
    assert _codes(res) == ["7s"]
    assert res[0].new_shanten == -1


def test_melds2_one_shanten_improvers():
    # 1 面子 + 2 搭子 -> 差 1 张
    h = Hand.from_codes(["1m2m3m", "4s5s", "7s8s"])
    assert shanten(h, 2, 2) == 1
    res = ukeire(h, 2, 2)
    assert len(res) > 0
    assert all(u.new_shanten == 0 for u in res)


def test_melds2_auto_lack_consistent():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s"])
    assert _codes(ukeire(h, None, 2)) == _codes(ukeire(h, 2, 2)) == ["7s"]


# ---- 四张上限(副露下同样) ----

def test_melds1_quad_tile_not_drawable():
    # 1m 已 4 张:1m 不可摸,即使结构上相关也不在 ukeire
    # melds=1 待摸态 10 张:1m1m1m1m 2m3m4m 5s5s6s(听 7s、5s 等);1m 被排除
    h = Hand.from_codes(["1m1m1m1m", "2m3m4m", "5s5s6s"])
    assert h.total == 10
    res = ukeire(h, 2, 1)
    assert "1m" not in _codes(res)  # 1m 已 4 张


# ---- 属性:副露胡牌去一牌 -> 下叫,ukeire 非空且被去牌在内 ----

@pytest.mark.parametrize("codes,melds,lack", [
    (["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"], 1, 2),
    (["1m2m3m", "4m5m6m", "7s7s"], 2, 2),
    (["1m2m3m", "5s5s"], 3, 2),
    (["1m1m1m", "2m2m2m", "3m3m3m", "5s5s"], 1, 2),
])
def test_win_remove_any_tile_ukeire_nonempty(codes, melds, lack):
    """副露胡牌(刚摸态)去掉任意 1 张 -> 待摸态下叫,其 ukeire 必非空,
    且被去掉的那张牌本身必在 ukeire 中(摸回即胡)。
    """
    from majiang_coach.win import win

    h = Hand.from_codes(codes)
    assert win(h, lack, melds) is True
    for idx in h.to_indices():
        h_wait = h.remove(idx)
        assert shanten(h_wait, lack, melds) == 0
        res = ukeire(h_wait, lack, melds)
        assert len(res) > 0, f"下叫 ukeire 为空: {' '.join(h_wait.to_codes())}"
        assert idx in [u.tile_index for u in res], (
            f"去掉的 {idx} 应在 ukeire: {' '.join(h_wait.to_codes())}"
        )
        assert all(u.new_shanten == -1 for u in res)


# ---- 参数校验 ----

def test_melds_negative_raises():
    h = Hand.from_codes(["5s5s"])
    with pytest.raises(ValueError):
        ukeire(h, 2, -1)


def test_melds_bool_raises():
    h = Hand.from_codes(["5s5s"])
    with pytest.raises(ValueError):
        ukeire(h, 2, True)


def test_ukeire_codes_helper_melds():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    assert ukeire_codes(h, 2, 1) == ["5s"]
