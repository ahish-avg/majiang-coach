"""tests for majiang_coach.ukeire"""

import pytest

from majiang_coach.hand import Hand
from majiang_coach.shanten import shanten
from majiang_coach.ukeire import UkeireTile, ukeire, ukeire_codes


def _codes(result):
    return [u.code for u in result]


# ---- 听牌 -> 待ち ----

def test_tenpai_tanki_single_wait():
    # 4 面子 + 1 浮牌(5s 单骑) -> 待ち 5s,new_shanten=-1
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert _codes(res) == ["5s"]
    assert res[0].new_shanten == -1


def test_tenpai_ryanmen_two_wait():
    # 3 面子 + 5s5s 雀头 + 3m4m 两面 -> 待ち 2m,5m
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert _codes(res) == ["2m", "5m"]
    assert all(u.new_shanten == -1 for u in res)


def test_tenpai_kanchan_single_wait():
    # 3 面子 + 8s8s 雀头 + 2m4m 嵌张 -> 待ち 3m
    h = Hand.from_codes(["4m5m6m", "7m8m9m", "1s2s3s", "8s8s", "2m4m"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert _codes(res) == ["3m"]


def test_tenpai_shanpon_two_wait():
    # 3 面子 + 5s5s 6s6s 双碰 -> 待ち 5s,6s
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "6s6s"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert _codes(res) == ["5s", "6s"]


def test_tenpai_penchan_single_wait():
    # 3 面子 + 5s5s 雀头 + 1m2m 边张 -> 待ち 3m
    h = Hand.from_codes(["4m5m6m", "7m8m9m", "1s2s3s", "5s5s", "1m2m"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert _codes(res) == ["3m"]


# ---- 1 向听 -> 改善牌 ----

def test_one_shanten_improvers_non_empty_and_lower():
    # 3 面子 + 2 搭子(无对子) -> 1 向听;改善牌摸入后向听=0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s", "4s5s"])
    assert shanten(h) == 1
    res = ukeire(h)
    assert len(res) > 0
    assert all(u.new_shanten == 0 for u in res)  # 1 向听摸一张最多到听牌(0),不能即胡


def test_improver_actually_lowers_shanten():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s", "4s5s"])
    base = shanten(h)
    for u in ukeire(h):
        assert u.new_shanten < base
        # 摸入后弃一张可到该 new_shanten
        assert shanten(h.add(u.tile_index)) == u.new_shanten


# ---- 缺门场景 ----

def test_lack_tile_not_in_ukeire():
    # 4 面子 + 1 缺门孤立(5p,缺筒) -> 1 向听;摸缺门牌(5p)不改善
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"])
    assert shanten(h, lack_suit=2) == 1
    res = ukeire(h, lack_suit=2)
    assert "5p" not in _codes(res)
    assert len(res) > 0  # 摸任意非缺门牌,弃 5p 后单骑听
    assert all(u.new_shanten == 0 for u in res)


def test_lack_none_enumerate_consistent():
    # 同上,lack_suit=None 枚举,结果与指定缺筒一致(缺筒为最优缺门)
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"])
    res_none = ukeire(h, lack_suit=None)
    res_p = ukeire(h, lack_suit=2)
    assert _codes(res_none) == _codes(res_p)
    assert "5p" not in _codes(res_none)


def test_two_suit_tenpai_ukeire():
    # 两门听牌(5s 单骑),缺第三门(None 枚举)应给出 5s
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert _codes(ukeire(h, lack_suit=None)) == ["5s"]


# ---- 四张上限 ----

def test_quad_tile_not_drawable():
    # 1m 已 4 张:1m 不可摸,即使结构上相关也不在 ukeire;但其它可摸的待ち仍在
    # 1m1m1m1m 234m 567m 789m(7m 跨 567/789) -> 听 4m、7m;1m 被排除
    h = Hand.from_codes(["1m1m1m1m", "2m3m4m", "5m6m7m", "7m8m9m"])
    assert shanten(h) == 0
    res = ukeire(h)
    assert "1m" not in _codes(res)  # 1m 已 4 张,不可摸
    assert _codes(res) == ["4m", "7m"]
    assert all(u.new_shanten == -1 for u in res)


# ---- 边界 ----

def test_non_13_raises():
    h14 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    with pytest.raises(ValueError):
        ukeire(h14)


def test_ukeire_tile_dataclass():
    u = UkeireTile(tile_index=0, code="1m", new_shanten=-1)
    assert u.tile_index == 0
    assert u.code == "1m"
    assert u.new_shanten == -1


def test_ukeire_codes_helper():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert ukeire_codes(h) == ["5s"]


# ---- 属性:听牌 ukeire 非空 ----

def test_property_tenpai_ukeire_nonempty():
    """任意 14 张胡牌去掉任意 1 张 -> 13 张听牌,其 ukeire 必非空,
    且被去掉的那张牌本身必在 ukeire 中(摸回即胡)。
    """
    from majiang_coach.win import win

    wins = [
        ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],
        ["1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m"],
        ["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7s7s"],
        ["1m1m1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s"],  # 龙七对
        ["1m2m3m", "3m4m5m", "6m7m8m", "8s8s8s", "9s9s"],
    ]
    checked = 0
    for codes in wins:
        h14 = Hand.from_codes(codes)
        assert win(h14) is True
        for idx in h14.to_indices():
            h13 = h14.remove(idx)
            assert shanten(h13) == 0
            res = ukeire(h13)
            assert len(res) > 0, f"听牌 ukeire 为空: {' '.join(h13.to_codes())}"
            # 被去掉的牌摸回即胡,必在 ukeire 中
            assert idx in [u.tile_index for u in res], (
                f"去掉的 {idx} 应在 ukeire: {' '.join(h13.to_codes())}"
            )
            assert all(u.new_shanten == -1 for u in res)
            checked += 1
    assert checked >= 20
