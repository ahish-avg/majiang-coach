"""review/comment.py:川麻口语点评文案生成(Phase 6,见计划 §6.3)。

所有输出用川麻口语:第 N 巡/摸牌/差 X 张下叫/已下叫/叫牌/自摸/点炮/抢杠/番种倍数。
函数名沿用技术词(shanten/ukeire),文案对外一律口语。胡牌番种来自 Phase 7 scoring。
"""

from __future__ import annotations

__all__ = [
    "shanten_cn",
    "build_turn_comment",
    "build_claim_comment",
    "build_win_comment",
]


def shanten_cn(s: int) -> str:
    """向听数 -> 川麻口语状态串。"""
    if s == -1:
        return "已胡牌"
    if s == 0:
        return "已下叫"
    return f"差 {s} 张下叫"


def build_turn_comment(
    turn: int,
    drawn_code: str | None,
    shanten: int,
    ukeire_codes: list[str],
    recommend_code: str | None,
    recommend_score: int | None,
    actual_code: str | None,
) -> str:
    """刚摸待弃态点评:第 N 巡/摸牌/差 X 张下叫或下叫(列叫牌)/推荐打 A(综合分)/实战比对。

    一致「打得好」;不一致「推荐打 A,实际打 B」。
    """
    parts = [f"第 {turn} 巡,摸 {drawn_code}" if drawn_code else f"第 {turn} 巡"]
    parts.append(shanten_cn(shanten))
    if shanten == 0 and ukeire_codes:
        parts.append(f"叫牌:{'、'.join(ukeire_codes)}")
    if recommend_code is not None:
        score = f"(综合 {recommend_score})" if recommend_score is not None else ""
        parts.append(f"硬算推荐打 {recommend_code}{score}")
    if actual_code is not None:
        if recommend_code is not None and actual_code == recommend_code:
            parts.append(f"实际打 {actual_code},打得好!")
        elif recommend_code is not None:
            parts.append(f"推荐打 {recommend_code},实际打 {actual_code}")
        else:
            parts.append(f"实际打 {actual_code}")
    return "。".join(parts) + "。"


def build_claim_comment(
    last_code: str,
    src_seat: int | None,
    can_ron: bool,
    can_pon: bool,
    pon_shanten_after: int | None,
) -> str:
    """他人弃牌申索提示:可胡(点炮)/可碰(碰后下叫情况)。"""
    parts = [f"座{src_seat}打 {last_code}"]
    if can_ron:
        parts.append("可以胡牌(点炮)!")
    if can_pon:
        after = ""
        if pon_shanten_after == 0:
            after = "(碰后下叫)"
        elif pon_shanten_after is not None:
            after = f"(碰后{shanten_cn(pon_shanten_after)})"
        parts.append(f"可以碰{after}")
    if not can_ron and not can_pon:
        parts.append("无申索")
    return "。".join(parts) + "。"


def build_win_comment(
    by: str,
    tile_code: str,
    from_seat: int | None = None,
    robbery: bool = False,
    fan_names: list[str] | None = None,
    total_fan: int | None = None,
    multiplier: int | None = None,
    cap_applied: bool = False,
    payer_text: str | None = None,
) -> str:
    """胡牌点评:自摸/点炮(含胡牌张与抢杠)+ 实际番种/番数/倍数/收付(Phase 7)。

    fan_names 为空(未结算)时退化为纯胡牌播报。
    """
    if robbery:
        s = f"抢杠胡 {tile_code}!"
    elif by == "tsumo":
        s = f"自摸 {tile_code} 胡牌!"
    else:
        s = f"点炮(座{from_seat})胡 {tile_code}!"
    if fan_names:
        s += f"{'、'.join(fan_names)},{total_fan} 番 {multiplier} 倍"
        if cap_applied:
            s += "(封顶)"
        if payer_text:
            s += f",{payer_text}"
        s += "。"
    return s
