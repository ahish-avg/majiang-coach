"""tests for PlayerView.lack_suits extension (Phase 3).

覆盖:
  - 默认 () 向后兼容(直接构造 PlayerView 不传 lack_suits)。
  - make_view 从 state.lack 填充 4 座公开缺门。
  - 缺门选择后(游戏推进)lack_suits 反映全座缺门。
"""

from __future__ import annotations

from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.engine.state import GameState
from majiang_coach.engine.wall import TileWall
from majiang_coach.hand import Hand


def test_default_empty_backward_compat():
    """直接构造 PlayerView 不传 lack_suits -> 默认 ()(向后兼容 Phase 2)。"""
    v = PlayerView(seat=0, hand=Hand.from_codes(["1m2m3m", "4s5s6s"]))
    assert v.lack_suits == ()


def test_explicit_lack_suits():
    v = PlayerView(
        seat=0,
        hand=Hand.from_codes(["1m2m3m"]),
        lack_suit=2,
        lack_suits=(2, 0, 1, None),
    )
    assert v.lack_suits == (2, 0, 1, None)
    assert v.lack_suit == 2  # 自家缺门仍单独字段


def test_make_view_fills_lack_suits():
    """make_view 从 state.lack 填充 4 座公开缺门。"""
    st = GameState.new(seed=7)
    st.lack = [2, 0, 1, None]
    v = st.make_view(0)
    assert v.lack_suits == (2, 0, 1, None)
    assert v.lack_suit == 2  # 自家缺门同步
    # 任意座视角都能看到全部 4 座缺门(公开)
    v1 = st.make_view(1)
    assert v1.lack_suits == (2, 0, 1, None)
    assert v1.lack_suit == 0


def test_make_view_lack_suits_length_four():
    st = GameState.new(seed=3)
    st.lack = [0, 1, 2, 0]
    v = st.make_view(2)
    assert len(v.lack_suits) == 4
    assert v.lack_suits[2] == 2


def test_view_is_frozen_and_hashable():
    """扩展字段后 PlayerView 仍 frozen 可哈希。"""
    v = PlayerView(
        seat=0, hand=Hand.from_codes(["1m2m3m"]), lack_suits=(0, 1, 2, None)
    )
    assert hash(v) == hash(v)
    import pytest
    with pytest.raises(Exception):
        v.lack_suits = (1, 1, 1, 1)  # type: ignore[misc]


def test_game_random_lack_suits_populated():
    """Phase 2 随机局中段 make_view 应填充 lack_suits(集成烟雾测试)。"""
    from majiang_coach.engine.game import Game, RandomActor

    actors = [RandomActor(100 + i) for i in range(4)]
    game = Game(actors, 100)
    record = game.run()
    # 找一个有缺门信息的事件点:从结果 meta 取 lack,直接构造状态验证
    lack_meta = record.meta.get("lack", [])
    assert len(lack_meta) == 4, f"meta lack 应 4 座: {lack_meta}"
    # lack_suits 在 make_view 路径填充正确(用新状态构造)
    st = GameState.new(seed=100)
    st.lack = list(lack_meta)
    v = st.make_view(0)
    assert v.lack_suits == tuple(lack_meta)
