"""tests for review/comment.py:川麻口语点评文案(Phase 6)。

覆盖:turn 差 X 张下叫 / 已下叫列叫牌 / 推荐与实战比对(打得好 vs 推荐打 A 实际打 B);
claim 可胡/可碰提示;win 自摸/点炮/抢杠(番种占位不算番)。
"""

from __future__ import annotations

from majiang_coach.review.comment import (
    shanten_cn, build_turn_comment, build_claim_comment, build_win_comment,
)


# ---- shanten_cn ----

def test_shanten_cn():
    assert shanten_cn(-1) == "已胡牌"
    assert shanten_cn(0) == "已下叫"
    assert shanten_cn(1) == "差 1 张下叫"
    assert shanten_cn(3) == "差 3 张下叫"


# ---- build_turn_comment ----

def test_turn_comment_shanten_words():
    """差 X 张下叫(向听>=1)/ 已下叫(0)/ 已胡牌(-1)。"""
    c = build_turn_comment(1, "5m", 2, [], None, None, None)
    assert "第 1 巡" in c
    assert "摸 5m" in c
    assert "差 2 张下叫" in c

    c0 = build_turn_comment(1, "5m", 0, ["3s", "6s"], None, None, None)
    assert "已下叫" in c0
    assert "叫牌:3s、6s" in c0

    cw = build_turn_comment(1, "5m", -1, [], None, None, None)
    assert "已胡牌" in cw


def test_turn_comment_recommend_match():
    """实战与推荐一致 -> 打得好。"""
    c = build_turn_comment(3, "7p", 1, [], "4s", 88, "4s")
    assert "硬算推荐打 4s(综合 88)" in c
    assert "打得好" in c


def test_turn_comment_recommend_mismatch():
    """实战与推荐不一致 -> 推荐打 A,实际打 B。"""
    c = build_turn_comment(3, "7p", 1, [], "4s", 88, "9m")
    assert "推荐打 4s,实际打 9m" in c
    assert "打得好" not in c


def test_turn_comment_no_actual():
    """实际动作非弃牌(tsumo/kan)-> 无实战比对。"""
    c = build_turn_comment(5, "2m", 1, [], "1p", 70, None)
    assert "硬算推荐打 1p(综合 70)" in c
    assert "实际" not in c
    assert "打得好" not in c


def test_turn_comment_no_recommend():
    """无推荐(异常兜底)-> 仅巡目/摸牌/状态。"""
    c = build_turn_comment(2, "9s", 3, [], None, None, "1m")
    assert "第 2 巡" in c
    assert "差 3 张下叫" in c
    assert "实际打 1m" in c
    assert "推荐" not in c


# ---- build_claim_comment ----

def test_claim_comment_ron():
    c = build_claim_comment("5m", 2, can_ron=True, can_pon=False, pon_shanten_after=None)
    assert "座2打 5m" in c
    assert "可以胡牌(点炮)" in c


def test_claim_comment_pon_tenpai():
    c = build_claim_comment("5m", 2, can_ron=False, can_pon=True, pon_shanten_after=0)
    assert "可以碰(碰后下叫)" in c


def test_claim_comment_pon_shanten():
    c = build_claim_comment("5m", 1, can_ron=False, can_pon=True, pon_shanten_after=2)
    assert "可以碰(碰后差 2 张下叫)" in c


def test_claim_comment_ron_and_pon():
    c = build_claim_comment("7s", 3, can_ron=True, can_pon=True, pon_shanten_after=1)
    assert "可以胡牌(点炮)" in c
    assert "可以碰" in c


def test_claim_comment_none():
    c = build_claim_comment("7s", 3, can_ron=False, can_pon=False, pon_shanten_after=None)
    assert "无申索" in c


# ---- build_win_comment ----

def test_win_comment_tsumo():
    c = build_win_comment("tsumo", "5m")
    assert "自摸 5m 胡牌" in c


def test_win_comment_ron():
    c = build_win_comment("ron", "3p", from_seat=2)
    assert "点炮(座2)胡 3p" in c


def test_win_comment_robbery():
    c = build_win_comment("ron", "3p", from_seat=1, robbery=True)
    assert "抢杠胡 3p" in c
    assert "点炮" not in c


def test_win_comment_no_fan_placeholder():
    """番种占位不算番(留 Phase 7)。"""
    for by, kw in (("tsumo", {}), ("ron", {"from_seat": 0})):
        c = build_win_comment(by, "5m", **kw)
        assert "不算番" in c
        assert "Phase 7" in c
