"""tests for engine/rules.py: priority, multi-ron, seat conflict, robbery."""

from __future__ import annotations

from majiang_coach.hand import Hand
from majiang_coach.engine import action as A
from majiang_coach.engine.rules import nearest_claimer, resolve_claims, robbery_targets


# ---- nearest_claimer ----

def test_nearest_claimer_ccw():
    # discarder=0, claimers=[2,3] -> 最近逆时针是 1? 不在;2 在 -> 2
    assert nearest_claimer(0, [2, 3]) == 2
    assert nearest_claimer(0, [1, 3]) == 1
    assert nearest_claimer(2, [0, 3]) == 3  # 2->3 先到
    assert nearest_claimer(3, [1, 2]) == 1  # 3->0(不在)->1


def test_nearest_claimer_wrap():
    assert nearest_claimer(3, [2]) == 2  # 3->0->1->2


# ---- resolve_claims: ron priority ----

def test_resolve_ron_beats_pon():
    # seat1 ron, seat2 pon -> ron wins
    choices = [(1, A.ron(0, 5)), (2, A.pon(0, 5))]
    result = resolve_claims(0, choices)
    assert result[0] == "ron"
    assert result[1] == [1]


def test_resolve_multi_ron():
    # 一炮多响:seat1, seat2 都 ron -> 都胡
    choices = [(1, A.ron(0, 5)), (2, A.ron(0, 5)), (3, A.pass_action())]
    result = resolve_claims(0, choices)
    assert result[0] == "ron"
    assert set(result[1]) == {1, 2}


def test_resolve_pon_nearest():
    # seat1, seat3 都碰 -> 最近逆时针 seat1
    choices = [(1, A.pon(0, 5)), (3, A.pon(0, 5))]
    result = resolve_claims(0, choices)
    assert result[0] == "claim"
    assert result[1] == 1


def test_resolve_pon_seat_conflict_far():
    # discarder=0, seat2,seat3 碰 -> seat2 更近
    choices = [(2, A.pon(0, 5)), (3, A.pon(0, 5))]
    result = resolve_claims(0, choices)
    assert result[0] == "claim"
    assert result[1] == 2


def test_resolve_daiminkan_vs_pon_same_seat():
    # 同座不可能同时碰和大明杠(互斥),但若两座各选 -> 最近座
    choices = [(1, A.pon(0, 5)), (3, A.daiminkan(0, 5))]
    result = resolve_claims(0, choices)
    assert result[0] == "claim"
    assert result[1] == 1


def test_resolve_pass():
    choices = [(1, A.pass_action()), (2, A.pass_action()), (3, A.pass_action())]
    result = resolve_claims(0, choices)
    assert result[0] == "pass"


def test_resolve_empty():
    result = resolve_claims(0, [])
    assert result[0] == "pass"


def test_resolve_ron_with_pass_mixed():
    choices = [(1, A.pass_action()), (2, A.ron(0, 5)), (3, A.pon(0, 5))]
    result = resolve_claims(0, choices)
    assert result[0] == "ron"
    assert result[1] == [2]


# ---- robbery_targets ----

def test_robbery_can_ron():
    # seat1 听 5s(13),补杠 5s -> 可抢
    hand = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    others = [(1, hand, 2, 0)]  # seat, hand, lack=筒, meld_count=0
    targets = robbery_targets(others, 13)
    assert targets == [1]


def test_robbery_cannot_ron():
    hand = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    others = [(1, hand, 2, 0)]
    targets = robbery_targets(others, 0)  # 1m 不胡
    assert targets == []


def test_robbery_lack_tile_forbidden():
    # 补杠牌为缺门 -> 不可抢
    hand = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5p5p", "5p"])
    others = [(1, hand, 2, 0)]
    targets = robbery_targets(others, 22)  # 5p=筒=缺门
    assert targets == []


def test_robbery_multi():
    # 两家都可抢 -> 一炮多响(均听 5s,无筒)
    h1 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    h2 = Hand.from_codes(["1m2m3m", "4m4m4m", "7m8m9m", "1s2s3s", "5s"])
    others = [(1, h1, 2, 0), (2, h2, 2, 0)]
    targets = robbery_targets(others, 13)
    assert targets == [1, 2]
