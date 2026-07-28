"""tests for win() melds extension (Phase 2)."""

from __future__ import annotations

import pytest

from majiang_coach.hand import Hand
from majiang_coach.win import win


# ---- melds=0 regression: must equal Phase 1 behavior ----

def test_melds0_standard_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert win(h, None, 0) is True
    assert win(h, None) is True  # default melds


def test_melds0_seven_pairs():
    # 七对(含龙七对:count==4 视为两对)= 4m4m4m4m(2对) + 5 对 = 7 对 14 张
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4m4m4m4m", "5s5s", "6s6s"])
    assert h.total == 14
    assert win(h, None, 0) is True


def test_melds0_not_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert win(h, None, 0) is False  # 13 张
    assert win(h, None) is False


def test_melds0_three_suits_no_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"])
    assert win(h, None, 0) is False  # 三门齐


# ---- melds=1: 暗手 11 张 = 3 面子 + 1 雀头 ----

def test_melds1_win():
    # 1 碰(固定),暗手 1m2m3m 4m5m6m 7m8m9m 5s5s = 3 面子 + 雀头
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    assert h.total == 11
    assert win(h, 2, 1) is True  # lack=筒(2),暗手无筒


def test_melds1_win_with_explicit_lack():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    # lack=条(1)也行(暗手有条 5s5s,但 lack 是条 -> 有条就不能胡)
    assert win(h, 1, 1) is False
    # lack=万(0) -> 暗手有万,不能胡
    assert win(h, 0, 1) is False
    # lack=筒(2) -> 暗手无筒,可胡
    assert win(h, 2, 1) is True


def test_melds1_not_win_bad_structure():
    # 暗手 11 张但结构不成立
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s6s"])
    assert h.total == 11
    assert win(h, 2, 1) is False


def test_melds1_wrong_tile_count():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s5s"])  # 12 张
    assert win(h, 2, 1) is False  # 应为 11


def test_melds1_seven_pairs_disabled():
    # 七对结构暗手 11 张?七对需 14 张;melds=1 时即使凑出对子结构也不走七对
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4m4m", "5s5s", "6s"])  # 11 张
    assert win(h, 2, 1) is False  # 不是标准形,七对禁用


# ---- melds=2: 暗手 8 张 = 2 面子 + 1 雀头 ----

def test_melds2_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert h.total == 8
    assert win(h, 2, 2) is True  # lack=筒


def test_melds2_win_sou_head():
    h = Hand.from_codes(["1m2m3m", "7m8m9m", "5s5s"])
    assert h.total == 8
    assert win(h, 2, 2) is True


def test_melds2_not_win():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s8s"])  # 8 张但非 2面子+雀头
    assert win(h, 2, 2) is False


# ---- melds=3: 暗手 5 张 = 1 面子 + 1 雀头 ----

def test_melds3_win():
    h = Hand.from_codes(["1m2m3m", "5s5s"])
    assert h.total == 5
    assert win(h, 2, 3) is True


def test_melds3_not_win():
    h = Hand.from_codes(["1m2m3m", "5s6s"])  # 5 张但非面子+雀头
    assert win(h, 2, 3) is False


# ---- melds=4: 暗手 2 张 = 仅雀头(四杠十八罗汉结构) ----

def test_melds4_win_pair_only():
    h = Hand.from_codes(["5s5s"])
    assert h.total == 2
    assert win(h, 2, 4) is True


def test_melds4_not_win_single():
    h = Hand.from_codes(["5s"])
    assert h.total == 1
    assert win(h, 2, 4) is False


# ---- 含杠的胡牌(暗手张数仍为 14-3*melds) ----

def test_melds_with_kan_tile_count():
    # 杠虽 4 张但计 1 副露;杠后岭上补摸,暗手张数 = 14-3*melds
    # melds=2(一碰一杠),暗手 8 张
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert win(h, 2, 2) is True


# ---- lack 约束 ----

def test_melds_lack_suit_present_no_win():
    # 暗手含筒(lack=筒),不能胡
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5p5p"])
    assert h.total == 11
    assert win(h, 2, 1) is False


def test_melds_auto_lack_two_suits_ok():
    # lack=None,暗手仅两门 -> 可胡
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    assert win(h, None, 1) is True


def test_melds_auto_lack_three_suits_no_win():
    # lack=None,暗手三门齐 -> 不能胡
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "5s5s", "5p5p"])  # 11 张三门
    assert win(h, None, 1) is False


# ---- 参数校验 ----

def test_melds_negative_raises():
    h = Hand.from_codes(["5s5s"])
    with pytest.raises(ValueError):
        win(h, 2, -1)


def test_melds_bool_raises():
    h = Hand.from_codes(["5s5s"])
    with pytest.raises(ValueError):
        win(h, 2, True)  # bool 不可


def test_melds_too_many_returns_false():
    # melds=5 -> expected = -1,任何暗手都不等
    h = Hand.from_codes(["5s5s"])
    assert win(h, 2, 5) is False
