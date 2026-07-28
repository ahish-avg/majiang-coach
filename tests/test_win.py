"""tests for majiang_coach.win

缺一门规则(血战到底):胡牌时手中至多两门(非三门齐)。
计划文档示例中 "5p5p" 出现在 True 用例与该规则矛盾(该手为三门齐),
按"三门齐不算胡"的权威规则,将 True 用例的雀头置于已存在的门(5s5s),
"换成跨第三门(5p5p)使三门齐 -> False" 保持一致。
"""

import pytest

from majiang_coach.hand import Hand
from majiang_coach.win import win


# ---- 标准形 ----

def test_standard_two_suit_win():
    # 4 顺子(万) + 1s2s3s(条) + 5s5s 雀头 -> 两门 -> True
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert win(h) is True


def test_standard_three_suit_not_win():
    # 同结构,雀头换到第三门筒 -> 三门齐 -> False
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"])
    assert win(h) is False


def test_standard_triplet_melds_two_suit():
    # 1m1m1m 2m2m2m 3m3m3m 4m5m6m + 7s7s -> 两门 -> True
    h = Hand.from_codes(["1m1m1m", "2m2m2m", "3m3m3m", "4m5m6m", "7s7s"])
    assert win(h) is True


def test_standard_one_suit_win():
    # 全万:1m1m1m 2m2m2m 3m3m3m 4m4m4m 5m5m -> 一门 -> True
    h = Hand.from_codes(["1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m"])
    assert win(h) is True


def test_standard_missing_pair_not_win():
    # 4 面子 + 一个嵌张搭子(非雀头) -> 无雀头 -> False
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "4s6s"])
    assert win(h) is False


# ---- 七对 / 龙七对 ----

def test_seven_pairs_two_suit():
    # 7 对,万(1-5) + 条(6,7) -> 两门 -> True
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4m4m", "5m5m", "6s6s", "7s7s"])
    assert win(h) is True


def test_long_seven_pairs_quad_counts_as_two():
    # 龙七对结构:1m x4(两对) + 2m2m 3m3m 4m4m 5s5s 6s6s = 2+5=7 对,14 张 -> 两门 -> True
    h = Hand.from_codes(["1m1m1m1m", "2m2m", "3m3m", "4m4m", "5s5s", "6s6s"])
    assert win(h) is True


def test_seven_pairs_three_suit_not_win():
    # 7 对但跨三门 -> 三门齐 -> False
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6p6p", "7p7p"])
    assert win(h) is False


# ---- lack_suit 指定 ----

def test_lack_suit_absent_win():
    # 万+条 两门,缺筒(absent) -> True
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert win(h, lack_suit=2) is True  # 筒 absent


def test_lack_suit_present_not_win():
    # 万+条,指定缺万(万仍在) -> False;缺条同理
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert win(h, lack_suit=0) is False  # 万 present
    assert win(h, lack_suit=1) is False  # 条 present


def test_lack_suit_none_three_suit_false():
    h = Hand.from_codes(["1m1m1m", "2s2s2s", "3p3p3p", "4m4m4m", "5m5m"])
    # 万条筒三门齐 -> False(None)
    assert win(h) is False
    # 但指定缺筒且筒仍在 -> False;缺万且万仍在 -> False
    assert win(h, lack_suit=2) is False


def test_lack_suit_makes_two_suit_hand_win():
    # 一手结构为胡,且恰缺一门(已 absent):指定该缺门应 True
    h = Hand.from_codes(["1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m"])  # 全万
    # 全万:缺条(1)或缺筒(2)都 absent
    assert win(h, lack_suit=1) is True
    assert win(h, lack_suit=2) is True
    assert win(h, lack_suit=0) is False  # 万 present


# ---- 边界 ----

def test_non_14_tiles_not_win():
    h13 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])  # 13
    assert win(h13) is False


def test_invalid_lack_raises():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    with pytest.raises(ValueError):
        win(h, lack_suit=3)
    with pytest.raises(ValueError):
        win(h, lack_suit=-1)
    with pytest.raises(ValueError):
        win(h, lack_suit="m")  # type: ignore[arg-type]
