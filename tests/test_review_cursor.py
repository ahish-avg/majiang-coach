"""tests for review/cursor.py:逐步回放光标(Phase 6)。

覆盖:final_state() == replay();每 draw 决策点 view 为 14-3*melds 张;
wall_remaining 单调递减;每步 108 张守恒;last_discard 生命周期;view 信息隔离。
"""

from __future__ import annotations

import pytest

from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.record import replay
from majiang_coach.review import ReviewCursor


def _game(seed: int):
    return Game([RandomActor(seed * 4 + i) for i in range(4)], seed).run()


@pytest.mark.parametrize("seed", [42, 7, 99, 123])
def test_final_state_equals_replay(seed):
    record = _game(seed)
    cursor = ReviewCursor(record)
    assert cursor.final_state() == replay(record)


@pytest.mark.parametrize("seed", [0, 5, 42])
def test_final_state_from_dict_record(seed):
    """dict 牌谱与 GameRecord 牌谱走同一光标路径。"""
    record = _game(seed)
    cursor = ReviewCursor(record.to_dict())
    assert cursor.final_state() == replay(record)


@pytest.mark.parametrize("seed", [42, 7, 99])
def test_draw_points_hand_total_and_wall(seed):
    """每 draw/kan_draw 决策点:view 暗手 = 14-3*melds;wall_remaining 单调递减。"""
    record = _game(seed)
    cursor = ReviewCursor(record)
    prev_wall: int | None = None
    n = 0
    for _event_index, seat, _drawn in cursor.iter_draw_events():
        view = cursor.view(seat)
        assert view.hand_total == 14 - 3 * view.meld_count
        if prev_wall is not None:
            assert cursor.wall_remaining < prev_wall
        prev_wall = cursor.wall_remaining
        cursor.assert_total()  # 每步 108 守恒
        n += 1
    assert n > 0


@pytest.mark.parametrize("seed", [42, 7])
def test_tile_conservation_every_event(seed):
    """逐事件推进:每步张数守恒 == 108。"""
    record = _game(seed)
    cursor = ReviewCursor(record)
    for _ev in record.events:
        cursor.advance_one()
        assert cursor.assert_total() == 108


def test_last_discard_lifecycle():
    """discard 后置位 (src, tile);draw/kan_draw 后清空;claim(pon/ron/大明杠)后清空。"""
    from majiang_coach.tiles import code_to_index
    record = _game(42)
    cursor = ReviewCursor(record)
    saw_discard = saw_cleared_after_draw = saw_cleared_after_claim = False
    prev_was_discard = False
    for ev in record.events:
        t = ev["t"]
        cursor.advance_one()
        if t == "discard":
            assert cursor.last_discard == (ev["seat"], code_to_index(ev["tile"]))
            saw_discard = True
            prev_was_discard = True
        elif t in ("draw", "kan_draw"):
            if prev_was_discard:
                assert cursor.last_discard is None
                saw_cleared_after_draw = True
            prev_was_discard = False
        elif t in ("pon", "ron", "kan") and prev_was_discard:
            # pon/ron/大明杠:申索后弃牌被取走,清空;ankan/shouminkan 不在弃牌后发生
            assert cursor.last_discard is None
            saw_cleared_after_claim = True
            prev_was_discard = False
    assert saw_discard
    assert saw_cleared_after_draw
    assert saw_cleared_after_claim


def test_view_info_isolation():
    """view 不含他家暗手:仅自家 hand + 公开 discards/melds/lack_suits。"""
    record = _game(42)
    cursor = ReviewCursor(record)
    for _event_index, seat, _drawn in cursor.iter_draw_events():
        view = cursor.view(seat)
        d = view_to_dict_safe(view)
        assert d["seat"] == seat
        assert len(d["hand"]) == view.hand_total
        assert len(d["discards"]) == 4
        assert len(d["public_melds"]) == 4
        break  # 首个决策点足够


def view_to_dict_safe(view):
    from majiang_coach.practice.prompt import view_to_dict
    return view_to_dict(view)


def test_winners_active_tracking():
    """tsumo/ron 后该座不在局(active=False)且计入 winners。"""
    record = _game(123)  # 该种子含胡牌事件
    cursor = ReviewCursor(record)
    while cursor.advance_one() is not None:
        pass
    for w in cursor.winners:
        assert cursor.active[w] is False
    replayed = replay(record)
    assert cursor.winners == replayed.winners
    assert len(cursor.winners) >= 1


def test_reset_idempotent():
    """reset 后重新迭代结果一致。"""
    record = _game(42)
    cursor = ReviewCursor(record)
    first = [(i, s, t) for i, s, t in cursor.iter_draw_events()]
    second = [(i, s, t) for i, s, t in cursor.iter_draw_events()]
    assert first == second
    assert len(first) > 0


def test_advance_to_matches_stepwise():
    """advance_to(i) 与逐事件推进状态一致。"""
    record = _game(7)
    a = ReviewCursor(record)
    for i in range(len(record.events)):
        a.advance_one()
        b = ReviewCursor(record)
        b.advance_to(i)
        assert a.counts == b.counts
        assert a.last_discard == b.last_discard
        assert a.wall_remaining == b.wall_remaining
        assert a.turn == b.turn
