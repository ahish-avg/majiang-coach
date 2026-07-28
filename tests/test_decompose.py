"""tests for majiang_coach.decompose (内部模块)"""

import pytest

from majiang_coach.decompose import suit_can_full_melds, suit_decompositions


def _suit(*counts):
    return list(counts) + [0] * (9 - len(counts))


# ---------------- suit_can_full_melds ----------------

@pytest.mark.parametrize("counts,expected", [
    ([1, 1, 1], True),            # 顺子 123
    ([3, 0, 0], True),            # 刻子 111
    ([0] * 9, True),              # 空门(平凡全成面子)
    ([2, 1, 0], False),           # 11+2 无法成面子
    ([1, 1, 1, 1, 1, 1, 1, 1, 1], True),   # 123 456 789
    ([4, 1, 1], True),            # 111 + 123
    ([2, 2, 2], True),            # 123 + 123
    ([4, 4, 4], True),            # 111x2 + 111... 实为 (111)(111)(123)(123)? 12张全成面子
    ([1, 0, 1], False),           # 1m + 3m 无法成面子
    ([2, 0, 0], False),           # 仅一对,非面子
])
def test_can_full_melds(counts, expected):
    assert suit_can_full_melds(_suit(*counts)) is expected


def test_can_full_melds_six_tile_sequence_pair():
    # 1m1m1m 2m3m4m -> 刻子+顺子 全成面子
    assert suit_can_full_melds(_suit(3, 1, 1, 1)) is True
    # 1m1m 2m2m 3m3m -> 两顺子 全成面子
    assert suit_can_full_melds(_suit(2, 2, 2)) is True


# ---------------- suit_decompositions ----------------

def test_decompose_empty():
    assert suit_decompositions(_suit(0, 0, 0)) == ((0, 0, 0),)


def test_decompose_pair():
    res = suit_decompositions(_suit(2, 0, 0))
    assert (0, 0, 1) in res


def test_decompose_taatsu_ryanmen():
    res = suit_decompositions(_suit(1, 1, 0))
    assert (0, 1, 0) in res


def test_decompose_taatsu_kanchan():
    res = suit_decompositions(_suit(1, 0, 1))
    assert (0, 1, 0) in res


def test_decompose_sequence():
    res = suit_decompositions(_suit(1, 1, 1))
    assert (1, 0, 0) in res


def test_decompose_triplet():
    res = suit_decompositions(_suit(3, 0, 0))
    assert (1, 0, 0) in res


def test_decompose_quad_two_pairs():
    # 1m x4 -> 可视为两对 (0,0,2);也刻子+浮牌 (1,0,0)
    res = suit_decompositions(_suit(4, 0, 0))
    assert (0, 0, 2) in res
    assert (1, 0, 0) in res


def test_decompose_pareto_drops_dominated():
    # 1m1m1m 的 (1,0,0) 应存在;被其支配的纯浮牌 (0,0,0) 应被剪掉
    res = suit_decompositions(_suit(3, 0, 0))
    assert (1, 0, 0) in res
    assert (0, 0, 0) not in res


def test_decompose_best_decomposition_present():
    # 1m2m3m4m5m6m -> 2 顺子 (2,0,0) 应存在
    res = suit_decompositions(_suit(1, 1, 1, 1, 1, 1))
    assert (2, 0, 0) in res


def test_decompose_mixed_meld_and_pair():
    # 1m1m1m 2m2m -> 刻子+对子 (1,0,1)
    res = suit_decompositions(_suit(3, 2, 0))
    assert (1, 0, 1) in res
