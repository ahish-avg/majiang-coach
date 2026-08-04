"""tests for llm/context.py(Phase 4,见计划 §5/§8.2)。"""

from __future__ import annotations

from majiang_coach.analysis import analyze
from majiang_coach.engine.view import PlayerView
from majiang_coach.hand import Hand
from majiang_coach.llm.context import build_context


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


# ---- 14 张(弃牌态) ----

def test_context_14tile_discard_phase():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    ctx = build_context(analyze(v), v)
    assert ctx["phase"] == "discard"
    assert ctx["lack_suit"] == "p"
    assert ctx["wall_remaining"] == 30
    assert ctx["weights_used"] == {"offense": 0.6, "defense": 0.4}


def test_context_hand_subset():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    ctx = build_context(analyze(v), v)
    h = ctx["hand"]
    for k in ("shanten", "is_tenpai", "ukeire_count", "ukeire_remaining_total", "score"):
        assert k in h


def test_context_recommend_brief():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    ctx = build_context(r, v)
    rec = ctx["recommend"]
    assert rec is not None
    assert rec["code"] == r.recommend.code
    for k in ("code", "offense", "danger", "defense", "composite",
              "shanten_after", "ukeire_count", "ukeire_remaining_total", "safety_reasons"):
        assert k in rec


def test_context_top5_sorted_and_capped():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    ctx = build_context(r, v)
    top5 = ctx["top5"]
    assert len(top5) <= 5
    # candidates 已按综合降序 -> top5 亦应降序
    scores = [c["composite"] for c in top5]
    assert scores == sorted(scores, reverse=True)
    # 与硬算 candidates 前 5 一致
    for brief, cand in zip(top5, r.candidates[:5]):
        assert brief["code"] == cand.code
        assert brief["composite"] == cand.composite_score


def test_context_best_offense_defense_codes():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    r = analyze(v)
    ctx = build_context(r, v)
    assert ctx["best_offense"] == r.best_offense.code
    assert ctx["best_defense"] == r.best_defense.code
    assert ctx["claim"] is None  # 14 张无 claim


def test_context_opponents_visible_only():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"], lack_suits=(2, 2, 0, 1))
    ctx = build_context(analyze(v), v)
    opps = ctx["opponents"]
    # 仅在局、非己(座 1/2/3)
    assert [o["seat"] for o in opps] == [1, 2, 3]
    for o in opps:
        for k in ("seat", "lack", "threat", "meld_count"):
            assert k in o
        assert o["meld_count"] == 0  # 无副露
    # lack 为字母码或缺门:座1缺筒(p)、座2缺万(m)、座3缺条(s)
    lack_map = {o["seat"]: o["lack"] for o in opps}
    assert lack_map[1] == "p"
    assert lack_map[2] == "m"
    assert lack_map[3] == "s"


def test_context_opponents_excludes_inactive():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"], active=(0, 1, 3))
    ctx = build_context(analyze(v), v)
    assert [o["seat"] for o in ctx["opponents"]] == [1, 3]


# ---- 13 张(待摸态) ----

def test_context_13tile_wait_phase():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
              last_discard=(1, __import__("majiang_coach.tiles", fromlist=["code_to_index"]).code_to_index("5m")))
    r = analyze(v)
    ctx = build_context(r, v)
    assert ctx["phase"] == "wait"
    assert ctx["recommend"] is None
    assert ctx["top5"] == []
    assert ctx["best_offense"] is None
    assert ctx["best_defense"] is None
    assert ctx["claim"] is not None
    assert "can_ron" in ctx["claim"]
    assert "can_pon" in ctx["claim"]


def test_context_13tile_opponents_still_present():
    v = _view(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"])
    ctx = build_context(analyze(v), v)
    # 待摸态无 candidates/recommend,但对手可见信息仍注入
    assert len(ctx["opponents"]) == 3
