"""tests for majiang_coach.hand"""

import pytest

from majiang_coach import tiles
from majiang_coach.hand import Hand


def _winning_standard():
    # 4 面子 + 1 雀头,14 张,两门
    return Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"])


def test_from_codes_and_total():
    h = _winning_standard()
    assert h.total == 14
    # counts length
    assert len(h.counts) == tiles.NUM_TILES
    # 1m..9m 各 1, 1s2s3s 各 1, 5p x2
    assert h.count(0) == 1  # 1m
    assert h.count(8) == 1  # 9m
    assert h.count(9) == 1  # 1s
    assert h.count(22) == 2  # 5p


def test_to_codes_roundtrip():
    codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"]
    h = Hand.from_codes(codes)
    # to_codes 按索引升序展开
    assert h.to_codes() == [
        "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
        "1s", "2s", "3s", "5p", "5p",
    ]
    # 重建应相等
    assert Hand.from_codes(h.to_codes()) == h


def test_suits_present():
    three_suit = Hand.from_codes(["1m", "1s", "1p"])
    assert three_suit.suits_present() == {0, 1, 2}

    two_suit = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p5p"])
    assert two_suit.suits_present() == {0, 1, 2}  # 实际含 m,s,p 三门
    # 纯两门
    only_ms = Hand.from_codes(["1m2m3m", "1s1s"])
    assert only_ms.suits_present() == {0, 1}
    # 纯一门
    only_m = Hand.from_codes(["1m1m1m", "2m3m4m"])
    assert only_m.suits_present() == {0}


def test_add_immutability():
    h = Hand.from_codes(["1m"])
    h2 = h.add(0)  # 再加一张 1m
    assert h.count(0) == 1  # 原实例不变
    assert h2.count(0) == 2
    assert h2.total == 2
    assert h is not h2


def test_remove_immutability():
    h = Hand.from_codes(["1m1m"])
    h2 = h.remove(0)
    assert h.count(0) == 2
    assert h2.count(0) == 1


def test_add_beyond_four_raises():
    h = Hand.from_codes(["1m1m1m1m"])
    assert h.count(0) == 4
    with pytest.raises(ValueError):
        h.add(0)


def test_remove_zero_raises():
    h = Hand.from_codes(["1m"])
    h2 = h.remove(0)
    assert h2.count(0) == 0
    with pytest.raises(ValueError):
        h2.remove(0)


def test_equality_and_hash():
    a = Hand.from_codes(["1m2m3m", "4s5s6s", "7p8p9p", "1m1m"])
    b = Hand.from_codes(a.to_codes())
    assert a == b
    assert hash(a) == hash(b)
    s = {a, b}
    assert len(s) == 1


def test_clone_equal():
    a = Hand.from_codes(["5p5p", "1m2m3m"])
    assert a.clone() == a


def test_from_indices_and_from_counts():
    h1 = Hand.from_indices([0, 0, 1, 2])
    assert h1.count(0) == 2 and h1.count(1) == 1 and h1.count(2) == 1
    h2 = Hand.from_counts([2, 1, 1] + [0] * 24)
    assert h2 == h1


def test_validation_bad_length():
    with pytest.raises(ValueError):
        Hand.from_counts([0] * 26)


def test_validation_bad_count():
    with pytest.raises(ValueError):
        Hand.from_counts([5] + [0] * 26)


def test_frozen_cannot_mutate():
    h = Hand.from_codes(["1m"])
    with pytest.raises(Exception):
        h.counts = (0,) * 27  # type: ignore[misc]


def test_empty_hand():
    e = Hand.empty()
    assert e.total == 0
    assert e.suits_present() == set()
    assert e.to_codes() == []


def test_repr_shows_codes():
    h = Hand.from_codes(["1m2m3m"])
    assert "1m" in repr(h) and "3m" in repr(h)
    assert "empty" in repr(Hand.empty())
