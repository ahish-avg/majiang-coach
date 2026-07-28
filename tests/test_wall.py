"""tests for engine/wall.py"""

from __future__ import annotations

import pytest

from majiang_coach.engine.wall import TileWall, WallExhausted
from majiang_coach import tiles


def test_seed_reproducible():
    a = TileWall(12345)
    b = TileWall(12345)
    assert a.deal() == b.deal()
    # 同种子后续摸牌也一致
    assert [a.draw() for _ in range(10)] == [b.draw() for _ in range(10)]


def test_different_seed_different():
    a = TileWall(1)
    b = TileWall(2)
    # 极不可能完全相同
    assert a.deal() != b.deal() or a.draw() != b.draw()


def test_deal_counts():
    w = TileWall(0)
    hands = w.deal()
    assert len(hands) == 4
    for h in hands:
        assert len(h) == 13
    # 总 52 张
    dealt = [t for h in hands for t in h]
    assert len(dealt) == 52
    # 剩余 56
    assert w.remaining() == 56
    assert not w.exhausted()


def test_tile_conservation_full_wall():
    """整副牌墙 108 张,牌种 27 种各 4 张。"""
    w = TileWall(42)
    hands = w.deal()
    all_tiles = [t for h in hands for t in h]
    while not w.exhausted():
        all_tiles.append(w.draw())
    assert len(all_tiles) == 108
    for idx in range(tiles.NUM_TILES):
        assert all_tiles.count(idx) == 4


def test_draw_decrements_remaining():
    w = TileWall(7)
    w.deal()
    start = w.remaining()
    w.draw()
    assert w.remaining() == start - 1


def test_rinshan_from_opposite_end():
    """杠尾摸从尾端取,与首摸互不干扰直到相遇。"""
    w = TileWall(7)
    w.deal()
    front_tile = w._wall[w._front]
    back_tile = w._wall[w._back - 1]
    assert w.draw() == front_tile
    assert w.draw_rinshan() == back_tile
    # 首摸推进前指针,杠尾退后指针,各消耗 1
    assert w.remaining() == 56 - 2


def test_exhaustion_and_exception():
    w = TileWall(7)
    w.deal()
    for _ in range(56):
        w.draw()
    assert w.exhausted()
    assert w.remaining() == 0
    with pytest.raises(WallExhausted):
        w.draw()
    with pytest.raises(WallExhausted):
        w.draw_rinshan()


def test_rinshan_then_front_meet():
    """交替首摸/杠尾,指针相遇即流局。"""
    w = TileWall(99)
    w.deal()
    count = 0
    while not w.exhausted():
        if count % 2 == 0:
            w.draw()
        else:
            w.draw_rinshan()
        count += 1
    assert count == 56
    assert w.remaining() == 0


def test_deal_only_once():
    w = TileWall(3)
    w.deal()
    with pytest.raises(RuntimeError):
        w.deal()


def test_rinshan_exhaustion_independent():
    """仅用杠尾摸也能耗尽(指针从两端逼近)。"""
    w = TileWall(5)
    w.deal()
    for _ in range(56):
        w.draw_rinshan()
    assert w.exhausted()
