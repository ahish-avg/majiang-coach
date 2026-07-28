"""tests for majiang_coach.shanten

覆盖:
  - 13/14 张语义(用户强调:与 ukeire 配合,语义写清)
  - 缺一门"禁搭但仍占张数"(用户强调):4 面子 + 1 缺门孤立 -> 向听 1
  - 缺门罚:同结构 3 门(含缺门废牌)向听 > 2 门
  - 七对 / 龙七对结构(count==4 视为两对)
  - oracle:标准形与 MahjongRepository regular shanten 在大量随机手牌上完全一致
  - 属性:14 张胡牌去掉任意 1 张 -> 13 张向听 == 0(听牌)
"""

import random

import pytest

from majiang_coach.hand import Hand
from majiang_coach.shanten import _standard_13, shanten

try:
    from mahjong.shanten import Shanten

    _HAS_ORACLE = True
except Exception:  # pragma: no cover
    _HAS_ORACLE = False


def _to_34(counts):
    arr = [0] * 34
    for i, c in enumerate(counts):
        arr[i] = c
    return arr


def _ref_regular(hand: Hand) -> int:
    return Shanten.calculate_shanten_for_regular_hand(_to_34(hand.counts))


def _rand_hand(n, rng):
    counts = [0] * 27
    total = 0
    while total < n:
        i = rng.randrange(27)
        if counts[i] < 4:
            counts[i] += 1
            total += 1
    return Hand.from_counts(counts)


# ============ 13 张语义 ============

def test_13_tenpai_tanki():
    # 4 面子 + 1 浮牌(单骑听) -> 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert shanten(h) == 0


def test_13_tenpai_ryanmen():
    # 3 面子 + 1 对子(雀头) + 1 两面搭子 -> 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "1s2s"])
    assert shanten(h) == 0


def test_13_one_shanten():
    # 3 面子 + 2 搭子(无对子) -> 1
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s", "4s5s"])
    assert shanten(h) == 1


def test_13_two_shanten():
    # 2 面子 + 3 搭子 + 1 浮牌 -> 2
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "9m", "1s2s", "4s5s", "7s8s"])
    assert shanten(h) == 2


# ============ 14 张语义 ============

def test_14_win_returns_minus_one():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    assert shanten(h) == -1


def test_14_non_win_discard_to_tenpai_is_zero():
    # 4 面子 + 1 搭子(无雀头),弃一张即单骑听 -> 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s6s"])
    assert shanten(h) == 0


def test_14_non_win_two_shanten():
    # 3 面子 + 2 搭子 + 1 缺门废牌(14 张):弃缺门废牌后仍 1 向听
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s", "4s5s", "7p"])
    # 三门齐(含 7p),lack=None 枚举;缺筒最优,弃 7p 后 3 面子+2 搭子 -> 1 向听
    assert shanten(h) == 1


# ============ 缺一门(用户强调) ============

def test_four_melds_plus_one_lack_isolated_is_one_shanten():
    """用户硬性要求:4 面子 + 1 缺门孤立牌 -> 向听 1(非 0)。

    缺门牌禁止入搭但仍占张数,故无法当单骑雀头 -> 比可用浮牌(tanki=0)多 1 向听。
    """
    # 4 面子(万+条) + 1 张筒(缺门) ,13 张,指定缺筒
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"])
    assert shanten(h, lack_suit=2) == 1
    # lack_suit=None 枚举取最小,仍应为 1(缺筒是最优缺门)
    assert shanten(h) == 1


def test_lack_tile_vs_usable_tile_same_structure():
    """同结构:4 面子 + 1 可用浮牌(tanki=0) vs 4 面子 + 1 缺门废牌(=1)。"""
    usable = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])  # 两门,tanki 5s
    lack = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"])  # 三门,5p 为缺门废牌
    assert shanten(usable) == 0
    assert shanten(lack) == 1
    assert shanten(lack) > shanten(usable)


def test_lack_specified_absent_equals_no_lack():
    # 两门手,缺其不在的第三门 -> 与不指定缺门(枚举)结果一致
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert shanten(h, lack_suit=2) == shanten(h) == 0


def test_lack_specified_present_raises_penalty():
    # 两门手(万+条),指定缺万(万仍在) -> 万全废,向听升高
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert shanten(h, lack_suit=0) > shanten(h, lack_suit=2)


def test_more_lack_tiles_more_shanten():
    # 4 面子 + 2 缺门废牌(14 张):非胡,弃一张后仍受缺门影响
    # 4 面子(万+条,12) + 2 张筒(缺门)=14;非胡 -> 弃一张(筒)后 4面子+1筒缺门 = 1 向听
    h14 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"])
    assert shanten(h14, lack_suit=2) == 1  # 弃一张 5p -> 4面子+1缺门孤立=1


# ============ 七对 / 龙七对 ============

def test_chiitoitsu_tenpai():
    # 6 对 + 1 单张 -> 0
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7s"])
    assert shanten(h) == 0


def test_chiitoitsu_quad_counts_as_two_pairs():
    # 1m x4(两对) + 4 对 + 1 单 = 6 对 + 1 单 -> 0(count==4 视为两对)
    h = Hand.from_codes(["1m1m1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s"])
    assert shanten(h) == 0


def test_chiitoitsu_lack_single_not_wait():
    # 6 对(万+条) + 1 张筒(缺门单张):缺门单张不能当待ち -> 1
    h = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7p"])
    assert shanten(h, lack_suit=2) == 1
    assert shanten(h) == 1  # 枚举:缺筒最优 -> 1
    # 对照:7s 可用单张 -> 0
    h2 = Hand.from_codes(["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7s"])
    assert shanten(h2) == 0


# ============ oracle:标准形 vs MahjongRepository ============

@pytest.mark.skipif(not _HAS_ORACLE, reason="mahjong 包未安装")
def test_oracle_standard_no_lack_random():
    """标准形(三门可用,dead_suit=None)与参考实现完全一致。"""
    rng = random.Random(20260728)
    mismatches = 0
    for _ in range(800):
        h = _rand_hand(13, rng)
        mine = _standard_13(h.counts, None)
        ref = _ref_regular(h)
        if mine != ref:
            mismatches += 1
            if mismatches <= 5:
                pytest.fail(
                    f"standard mismatch: mine={mine} ref={ref} hand={' '.join(h.to_codes())}"
                )
    assert mismatches == 0


@pytest.mark.skipif(not _HAS_ORACLE, reason="mahjong 包未安装")
def test_oracle_lack_path_two_suit_dead_zero():
    """两门手:缺其不在的第三门(dead_tiles=0)走缺门代码路径,应与参考一致。"""
    rng = random.Random(424242)
    mismatches = 0
    for _ in range(400):
        h = _rand_hand(13, rng)
        present = h.suits_present()
        if len(present) != 2:
            continue
        absent = ({0, 1, 2} - present).pop()
        mine = _standard_13(h.counts, absent)  # 缺门=不在的门,dead_tiles=0
        ref = _ref_regular(h)
        if mine != ref:
            mismatches += 1
            if mismatches <= 5:
                pytest.fail(
                    f"lack-path mismatch: mine={mine} ref={ref} hand={' '.join(h.to_codes())} lack={absent}"
                )
    assert mismatches == 0


# ============ 属性测试 ============

@pytest.mark.parametrize("codes", [
    ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],          # 标准胡
    ["1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m"],          # 全刻子胡
    ["1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7s7s"],  # 七对胡
    ["1m1m1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s"],      # 龙七对胡
    ["1m2m3m", "3m4m5m", "6m7m8m", "8s8s8s", "9s9s"],          # 复杂标准胡(含跨顺子)
])
def test_win_remove_any_tile_is_tenpai(codes):
    """任意 14 张胡牌,去掉任意 1 张 -> 13 张向听 == 0(听牌)。"""
    from majiang_coach.win import win

    h14 = Hand.from_codes(codes)
    assert win(h14) is True, f"前提:应为胡牌 {' '.join(codes)}"
    for idx in h14.to_indices():
        h13 = h14.remove(idx)
        assert shanten(h13) == 0, (
            f"胡牌去掉 {idx} 后应听牌(0),实得 {shanten(h13)}: {' '.join(h13.to_codes())}"
        )


def test_invalid_lack_raises():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    with pytest.raises(ValueError):
        shanten(h, lack_suit=3)
    with pytest.raises(ValueError):
        shanten(h, lack_suit=-1)


def test_invalid_tile_count_raises():
    """血战合法手牌只有 13/14 张;其余张数应报错,而非返回误导性向听。"""
    # 16 张(曾因七对路径 p>=7 误判 -1)
    h16 = Hand.from_codes(["1m1m1m1m", "2m2m", "3m3m", "4m4m", "5m5s", "6s6s", "7s7s"])
    with pytest.raises(ValueError):
        shanten(h16)
    # 12 张
    h12 = Hand.from_codes(["1m2m3m", "4s5s6s", "7p8p9p"])
    with pytest.raises(ValueError):
        shanten(h12)
