"""tests for analysis/recommend.py (Phase 3,见计划 §5/§6/§8)。

覆盖:
  - 14张(刚摸态):逐候选指标齐全;综合排序;recommend=综合最高且确定性;
    best_offense/best_defense;weights_used 回传。
  - 13张(待摸态):仅 hand + 可选 claim;不产出弃牌候选。
  - 缺门约束:有缺门牌时 candidates 只含缺门牌,推荐绝不打非缺门。
  - claim:can_ron 用 win(melds);can_pon 排除缺门;pon_shanten_after 按 §6.8。
  - 纯函数确定性;to_dict/from_dict 往返一致。
  - 副露通路(melds>0)。
"""

from __future__ import annotations

import pytest

from majiang_coach.analysis import (
    analyze, analysis_result_to_dict, analysis_result_from_dict,
)
from majiang_coach.analysis.recommend import AnalysisResult, Candidate
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand


def _view(hand_codes, lack=2, lack_suits=(2, 2, 0, 0), melds=(),
          public_melds=None, discards=None, wall=30, active=(0, 1, 2, 3),
          last_discard=None):
    h = Hand.from_codes(hand_codes)
    pm = public_melds if public_melds is not None else (tuple(melds), (), (), ())
    dc = discards if discards is not None else ((), (), (), ())
    return PlayerView(
        seat=0, hand=h, melds=tuple(melds), lack_suit=lack, lack_suits=lack_suits,
        public_melds=pm, discards=dc, wall_remaining=wall,
        active_seats=tuple(active), last_discard=last_discard,
    )


# ---- 14张(刚摸态):候选 + 排序 ----

def test_14_candidates_complete():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    assert r.hand_total == 14
    assert len(r.candidates) > 0
    c = r.candidates[0]
    # 候选字段齐全
    for attr in ["tile", "code", "shanten_after", "is_tenpai_after", "ukeire",
                 "ukeire_count", "ukeire_remaining_total", "offense_score",
                 "danger", "defense_score", "composite_score", "safety_reasons",
                 "per_opponent"]:
        assert hasattr(c, attr)


def test_14_sorted_by_composite_desc():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    scores = [c.composite_score for c in r.candidates]
    assert scores == sorted(scores, reverse=True)


def test_recommend_is_composite_max():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    assert r.recommend is not None
    assert r.recommend.composite_score == max(c.composite_score for c in r.candidates)


def test_best_offense_and_defense():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    assert r.best_offense is not None
    assert r.best_defense is not None
    assert r.best_offense.offense_score == max(c.offense_score for c in r.candidates)
    assert r.best_defense.defense_score == max(c.defense_score for c in r.candidates)


def test_weights_used_returned():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    assert r.weights_used == {"offense": 0.6, "defense": 0.4}
    r2 = analyze(v, weights={"offense": 0.7, "defense": 0.3})
    assert r2.weights_used == {"offense": 0.7, "defense": 0.3}


def test_weights_affect_ranking():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r_off = analyze(v, weights={"offense": 1.0, "defense": 0.0})
    assert r_off.recommend.tile == r_off.best_offense.tile  # 纯进攻 -> 推荐即最优进攻


def test_deterministic_same_view_same_result():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r1 = analyze(v)
    r2 = analyze(v)
    assert analysis_result_to_dict(r1) == analysis_result_to_dict(r2)


# ---- 缺门约束 ----

def test_lack_constraint_candidates_only_lack():
    # 14张(刚摸态),手中有缺门牌(筒)时,candidates 只含缺门牌
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "6s7s", "5p"], lack=2)
    r = analyze(v)
    assert r.hand_total == 14
    lack_tiles = [i for i in range(18, 27) if v.hand.count(i) > 0]  # 筒门
    cand_tiles = [c.tile for c in r.candidates]
    assert set(cand_tiles) == set(lack_tiles)
    # 推荐绝不打非缺门
    assert all(18 <= t <= 26 for t in cand_tiles)


def test_lack_cleared_all_discardable():
    # 14张(刚摸态),缺门已清(无筒),可弃任意手中牌
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m", "6m"], lack=2)
    r = analyze(v)
    assert r.hand_total == 14
    assert len(r.candidates) > 1  # 多张可弃


# ---- 13张(待摸态):仅 hand + claim ----

def test_13_no_candidates_only_hand_and_claim():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
              last_discard=(1, 4))
    r = analyze(v)
    assert r.hand_total == 13
    assert r.candidates == []
    assert r.recommend is None
    assert r.best_offense is None
    assert r.best_defense is None
    assert r.claim is not None
    # hand 有 ukeire
    assert r.hand.ukeire_count > 0


def test_13_no_last_discard_no_claim():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"])
    r = analyze(v)
    assert r.candidates == []
    assert r.claim is None


# ---- claim:can_ron / can_pon / pon_shanten_after ----

def test_claim_can_ron():
    # 听 5m(两面 3m4m/5s5s雀头);opp 弃 5m -> can_ron
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
              last_discard=(1, 4))  # 5m=4
    r = analyze(v)
    assert r.claim["can_ron"] is True
    assert r.claim["can_pon"] is False  # 手中无 5m


def test_claim_can_pon_and_shanten_after():
    # 手中 5s5s;opp 弃 5s -> can_pon;碰后 melds+1 待弃态下叫 -> pon_shanten_after=0
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
              last_discard=(1, 13))  # 5s=13
    r = analyze(v)
    assert r.claim["can_pon"] is True
    assert r.claim["can_ron"] is False  # 5s 非叫牌
    assert r.claim["pon_shanten_after"] == 0


def test_claim_pon_excludes_lack_suit():
    # 缺筒;手中 5p5p;opp 弃 5p(缺门牌)-> 不可碰
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5p5p", "3m4m"], lack=2,
              last_discard=(1, 22))  # 5p=22
    r = analyze(v)
    assert r.claim["can_pon"] is False  # 缺门牌不可碰


def test_claim_ron_uses_melds():
    # melds=1,13-3=10 张待摸态听 5s;opp 弃 5s -> can_ron(win melds=1)
    pon = Meld(kind="pon", tile=4, src_seat=1)
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s"], lack=2, melds=(pon,),
              public_melds=((pon,), (), (), ()),
              last_discard=(1, 13))
    r = analyze(v)
    assert r.hand_total == 10
    assert r.claim["can_ron"] is True


# ---- 副露通路 ----

def test_melds1_draw_state_candidates():
    pon = Meld(kind="pon", tile=4, src_seat=1)
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"], lack=2, melds=(pon,),
              public_melds=((pon,), (), (), ()))
    r = analyze(v)
    assert r.hand_total == 11  # 14-3*1
    assert len(r.candidates) > 0
    assert r.hand.shanten == -1  # 3面子+将对=胡


# ---- to_dict/from_dict 往返 ----

def test_roundtrip_14():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    d = analysis_result_to_dict(r)
    r2 = analysis_result_from_dict(d)
    assert analysis_result_to_dict(r2) == d


def test_roundtrip_13_with_claim():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
              last_discard=(1, 13))
    r = analyze(v)
    d = analysis_result_to_dict(r)
    r2 = analysis_result_from_dict(d)
    assert analysis_result_to_dict(r2) == d


def test_roundtrip_melds():
    pon = Meld(kind="pon", tile=4, src_seat=1)
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"], lack=2, melds=(pon,),
              public_melds=((pon,), (), (), ()))
    r = analyze(v)
    d = analysis_result_to_dict(r)
    r2 = analysis_result_from_dict(d)
    assert analysis_result_to_dict(r2) == d
    assert len(r2.melds) == 1
    assert r2.melds[0].tile == 4
