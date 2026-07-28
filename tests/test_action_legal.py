"""tests for engine/action.py: legal discards / claims / self-actions.

索引:1m=0..9m=8 | 1s=9..9s=17 | 1p=18..9p=26。故 5m=4, 5s=13, 5p=22。
"""

from __future__ import annotations

import pytest

from majiang_coach.hand import Hand
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.engine import action as A


def _view(hand_codes, lack=None, melds=(), wall=10, last_discard=None):
    hand = Hand.from_codes(hand_codes)
    m = tuple(melds)
    return PlayerView(
        seat=0,
        hand=hand,
        melds=m,
        lack_suit=lack,
        wall_remaining=wall,
        last_discard=last_discard,
    )


# ---- legal_discards ----

def test_legal_discards_no_lack():
    v = _view(["1m2m3m", "4m5m6m", "5s5s"], lack=None)
    d = A.legal_discards(v)
    assert set(d) == {0, 1, 2, 3, 4, 5, 13}  # 5s=13


def test_legal_discards_lack_must_clear():
    v = _view(["1m2m3m", "4m5m6m", "5s5s", "5p"], lack=2)
    d = A.legal_discards(v)
    assert d == [22]  # 5p=22


def test_legal_discards_lack_multiple():
    v = _view(["1m2m3m", "5p5p6p"], lack=2)
    d = A.legal_discards(v)
    assert set(d) == {22, 23}  # 5p=22, 6p=23
    assert 0 not in d and 1 not in d


def test_legal_discards_lack_cleared():
    v = _view(["1m2m3m", "5s5s"], lack=2)
    d = A.legal_discards(v)
    assert set(d) == {0, 1, 2, 13}


# ---- legal_claims ----

def test_legal_claims_pon():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5m5m"], lack=2, last_discard=(1, 4))
    claims = A.legal_claims(v, 4)  # 5m=4
    assert "pon" in [c.kind for c in claims]


def test_legal_claims_daiminkan():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s5s"], lack=2, last_discard=(1, 13), wall=5)
    claims = A.legal_claims(v, 13)  # 5s
    kinds = [c.kind for c in claims]
    assert "daiminkan" in kinds
    assert "pon" in kinds


def test_legal_claims_daiminkan_no_wall():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s5s"], lack=2, last_discard=(1, 13), wall=0)
    claims = A.legal_claims(v, 13)
    kinds = [c.kind for c in claims]
    assert "daiminkan" not in kinds
    assert "pon" in kinds


def test_legal_claims_ron():
    # 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s(听5s) -> 弃5s 可胡
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"], lack=2, last_discard=(1, 13))
    claims = A.legal_claims(v, 13)  # 5s
    assert "ron" in [c.kind for c in claims]


def test_legal_claims_lack_tile_no_claim():
    v = _view(["1m2m3m", "4m5m6m", "5p5p"], lack=2, last_discard=(1, 22))
    claims = A.legal_claims(v, 22)  # 5p=缺门
    assert claims == []


def test_legal_claims_none():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"], lack=2, last_discard=(1, 0))
    claims = A.legal_claims(v, 0)  # 1m 不构成申索
    assert claims == []


def test_legal_claims_ron_with_melds():
    # 1 副露(碰5s),暗手 10 张听 5s
    melds = (Meld("pon", 13, 1),)
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s"], lack=2, melds=melds, last_discard=(1, 13))
    claims = A.legal_claims(v, 13)
    assert any(c.kind == "ron" for c in claims)


# ---- legal_self_actions ----

def test_self_actions_tsumo():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"], lack=2)
    acts = A.legal_self_actions(v, drawn=13)
    assert any(a.kind == "tsumo" for a in acts)


def test_self_actions_ankan():
    # 14 张含 5s5s5s5s(四张同牌)-> 暗杠可选
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1m", "5s5s5s5s"], lack=2, wall=5)
    acts = A.legal_self_actions(v, drawn=0)
    ankan_actions = [a for a in acts if a.kind == "ankan"]
    assert len(ankan_actions) == 1
    assert ankan_actions[0].tile == 13  # 5s


def test_self_actions_ankan_no_wall():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1m", "5s5s5s5s"], lack=2, wall=0)
    acts = A.legal_self_actions(v, drawn=0)
    assert not any(a.kind == "ankan" for a in acts)


def test_self_actions_ankan_lack_suit_forbidden():
    # 4 张筒(缺门)-> 不可暗杠
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1m", "5p5p5p5p"], lack=2, wall=5)
    acts = A.legal_self_actions(v, drawn=0)
    assert not any(a.kind == "ankan" and a.tile == 22 for a in acts)


def test_self_actions_shouminkan():
    # 已碰 5s,暗手含一张 5s -> 补杠可选
    melds = (Meld("pon", 13, 1),)
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s", "5s"], lack=2, melds=melds, wall=5)
    acts = A.legal_self_actions(v, drawn=13)
    sm = [a for a in acts if a.kind == "shouminkan"]
    assert len(sm) == 1
    assert sm[0].tile == 13


def test_self_actions_drawn_none_only_discard():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"], lack=2)
    acts = A.legal_self_actions(v, drawn=None)
    assert {a.kind for a in acts} == {"discard"}


def test_self_actions_lack_discard_only():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5p"], lack=2, wall=5)
    acts = A.legal_self_actions(v, drawn=22)
    discards = [a for a in acts if a.kind == "discard"]
    assert all(a.tile == 22 for a in discards)


def test_self_actions_includes_discard_always():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"], lack=2)
    acts = A.legal_self_actions(v, drawn=13)
    assert any(a.kind == "discard" for a in acts)


def test_action_equality_and_hash():
    a = A.discard(5)
    b = A.discard(5)
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
