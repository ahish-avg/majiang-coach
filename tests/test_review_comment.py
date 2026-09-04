"""tests for review/comment.py:川麻口语点评文案(Phase 6)。

覆盖:turn 差 X 张下叫 / 已下叫列叫牌 / 推荐与实战比对(打得好 vs 推荐打 A 实际打 B);
claim 可胡/可碰提示;win 自摸/点炮/抢杠(Phase 7 起含实际番种/番数/倍数文案)。
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


def test_win_comment_with_fan_tsumo():
    """Phase 7:自摸胡牌点评含番种/番数/倍数/收付。"""
    c = build_win_comment("tsumo", "5m", fan_names=["清一色", "自摸"],
                          total_fan=5, multiplier=16, cap_applied=True,
                          payer_text="在局三家各付")
    assert "自摸 5m 胡牌" in c
    assert "清一色、自摸,5 番 16 倍" in c
    assert "封顶" in c
    assert "在局三家各付" in c


def test_win_comment_with_fan_ron():
    """点炮胡:点炮者付;抢杠胡用抢杠文案。"""
    c = build_win_comment("ron", "3p", from_seat=2, fan_names=["平胡"],
                          total_fan=1, multiplier=1, payer_text="座2付")
    assert "点炮(座2)胡 3p" in c
    assert "平胡,1 番 1 倍" in c
    assert "座2付" in c

    c2 = build_win_comment("ron", "3p", from_seat=1, robbery=True,
                           fan_names=["抢杠胡", "平胡"], total_fan=3,
                           multiplier=4, payer_text="座1付")
    assert "抢杠胡 3p" in c2
    assert "点炮" not in c2
    assert "4 倍" in c2


def test_win_comment_without_fan_plain():
    """无番种输入时退化为纯胡牌播报(不出现占位文案)。"""
    c = build_win_comment("tsumo", "5m")
    assert "自摸 5m 胡牌" in c
    assert "番" not in c
    assert "Phase 7" not in c
