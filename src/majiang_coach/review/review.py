"""review/review.py:review_record 编排(Phase 6,见计划 §6.4,纯函数)。

输入 GameRecord(JSON 牌谱),输出 ReviewResult:
  - 每个 draw/kan_draw 决策点:turn_action 步(该座 14 张刚摸态 view + Phase 3 analyze
    + 可选 Phase 4 advise(LLM 失败兜底 advice=null+error,analysis 始终在))。
  - discard 后:对每个在局他座建 13 张 view(带 last_discard),legal_claims 非空才产
    claim 步(避免纯 pass 噪音)。
  - tsumo/ron:win 步;ryuukyoku:over 步。
  - actual_action 取该事件后实际事件(discard/pon/kan/tsumo/ron),与 recommend 比对
    (matched);seat_focus 限定只点评该座(默认全部 4 座)。

确定性:同一 record + 同一参数 -> 同一 to_dict()(hints_on 依赖 LLM,测试用假 provider)。
"""

from __future__ import annotations

from collections import Counter

from .. import tiles
from ..analysis import analyze
from ..engine.action import legal_claims
from ..engine.record import GameRecord
from ..llm import advise
from ..practice.prompt import view_to_dict
from .comment import build_claim_comment, build_turn_comment, build_win_comment
from .cursor import ReviewCursor
from .result import ReviewResult, ReviewStep

__all__ = ["review_record"]


def _actual_after_draw(events: list[dict], i: int) -> dict | None:
    """draw/kan_draw 事件 i 后,该座实际回合动作 dict;无后续事件返 None。"""
    nxt = events[i + 1] if i + 1 < len(events) else None
    if nxt is None:
        return None
    t = nxt["t"]
    if t == "discard":
        return {"kind": "discard", "tile": nxt["tile"]}
    if t == "kan":
        return {"kind": nxt["kind"], "tile": nxt["tile"]}
    if t == "tsumo":
        return {"kind": "tsumo", "tile": nxt["tile"]}
    if t == "ron" and nxt.get("robbery"):
        # 补杠被抢:kan 事件不落地,实战意图为 shouminkan
        return {"kind": "shouminkan", "tile": nxt["tile"]}
    return None


def _claim_actual(events: list[dict], i: int, seat: int) -> dict | None:
    """discard 事件 i 后,座 seat 对这次弃牌的申索动作 dict;未申索(pass)返 None。

    申索窗口止于下一 discard/draw/kan_draw/ryuukyoku(新事件开启新窗口)。
    """
    for j in range(i + 1, len(events)):
        ev = events[j]
        t = ev["t"]
        if t in ("discard", "draw", "kan_draw", "ryuukyoku"):
            return None
        if t == "pon" and ev["seat"] == seat:
            return {"kind": "pon", "tile": ev["tile"], "from": ev.get("from")}
        if t == "ron" and ev["seat"] == seat and not ev.get("robbery"):
            return {"kind": "ron", "tile": ev["tile"], "from": ev.get("from")}
        if t == "kan" and ev.get("kind") == "daiminkan" and ev["seat"] == seat:
            return {"kind": "daiminkan", "tile": ev["tile"], "from": ev.get("from")}
    return None


def review_record(
    record: GameRecord | dict,
    *,
    hints_on: bool = False,
    llm_config=None,
    weights: dict | None = None,
    seat_focus: int | list[int] | None = None,
) -> ReviewResult:
    """一局牌谱 -> 结构化 ReviewResult(逐步回放 + AI 点评 + 按座汇总)。"""
    rec = record if isinstance(record, GameRecord) else GameRecord.from_dict(record)
    events = rec.events
    cursor = ReviewCursor(rec)

    if seat_focus is None:
        focus = None
    elif isinstance(seat_focus, int):
        focus = {seat_focus}
    else:
        focus = {int(s) for s in seat_focus}

    steps: list[ReviewStep] = []
    per_seat = {
        s: {"turn_steps": 0, "matched_actual": 0, "win_by": None, "claims": 0}
        for s in range(4)
    }
    event_counts: Counter = Counter()

    cursor.reset()
    for i, ev in enumerate(events):
        cursor.advance_one()
        event_counts[ev["t"]] += 1
        t = ev["t"]

        if t in ("draw", "kan_draw"):
            seat = ev["seat"]
            if focus is not None and seat not in focus:
                continue
            if not cursor.active[seat]:
                continue  # 已胡/已不在局座跳过
            view = cursor.view(seat)
            actual = _actual_after_draw(events, i)
            if hints_on:
                res = advise(view, hints_on=True, llm_config=llm_config, weights=weights)
                analysis = res.analysis
                advice = res.to_dict()
            else:
                analysis = analyze(view, weights).to_dict()
                advice = None
            rec_c = analysis.get("recommend") or {}
            rec_code = rec_c.get("code")
            rec_score = rec_c.get("composite_score")
            hand_off = analysis.get("hand") or {}
            ukeire_codes = [u["code"] for u in hand_off.get("ukeire", [])]
            actual_code = actual.get("tile") if actual and actual["kind"] == "discard" else None
            comment = build_turn_comment(
                turn=cursor.turn + 1,
                drawn_code=ev["tile"],
                shanten=hand_off.get("shanten", 0),
                ukeire_codes=ukeire_codes,
                recommend_code=rec_code,
                recommend_score=rec_score,
                actual_code=actual_code,
            )
            per_seat[seat]["turn_steps"] += 1
            if actual_code is not None and rec_code is not None and actual_code == rec_code:
                per_seat[seat]["matched_actual"] += 1
            steps.append(ReviewStep(
                step=len(steps) + 1,
                event_index=i,
                phase="turn_action",
                seat=seat,
                tile=ev["tile"],
                hand_total=view.hand_total,
                actual_action=actual,
                view=view_to_dict(view),
                analysis=analysis,
                advice=advice,
                comment=comment,
            ))

        elif t == "discard":
            src = ev["seat"]
            tile_code = ev["tile"]
            tile_idx = tiles.code_to_index(tile_code)
            for offset in range(1, 4):
                s = (src + offset) % 4
                if focus is not None and s not in focus:
                    continue
                if not cursor.active[s]:
                    continue  # 已胡/已不在局座跳过
                view = cursor.view(s)  # last_discard 已置位
                if not legal_claims(view, tile_idx):
                    continue  # 无可申索 -> 不产 claim 步(避免 pass 噪音)
                analysis = analyze(view, weights).to_dict()
                claim = analysis.get("claim") or {}
                comment = build_claim_comment(
                    last_code=tile_code,
                    src_seat=src,
                    can_ron=bool(claim.get("can_ron")),
                    can_pon=bool(claim.get("can_pon")),
                    pon_shanten_after=claim.get("pon_shanten_after"),
                )
                per_seat[s]["claims"] += 1
                steps.append(ReviewStep(
                    step=len(steps) + 1,
                    event_index=i,
                    phase="claim",
                    seat=s,
                    tile=tile_code,
                    hand_total=view.hand_total,
                    actual_action=_claim_actual(events, i, s),
                    view=view_to_dict(view),
                    analysis=analysis,
                    advice=None,
                    comment=comment,
                ))

        elif t in ("tsumo", "ron"):
            seat = ev["seat"]
            tile_code = ev["tile"]
            from_seat = ev.get("from")
            robbery = ev.get("robbery", False)
            per_seat[seat]["win_by"] = t
            if focus is not None and seat not in focus:
                continue
            view = cursor.view(seat)
            steps.append(ReviewStep(
                step=len(steps) + 1,
                event_index=i,
                phase="win",
                seat=seat,
                tile=tile_code,
                hand_total=view.hand_total,
                actual_action={"kind": t, "tile": tile_code, "from": from_seat},
                view=view_to_dict(view),
                analysis=None,
                advice=None,
                comment=build_win_comment(t, tile_code, from_seat, robbery),
            ))

        elif t == "ryuukyoku":
            steps.append(ReviewStep(
                step=len(steps) + 1,
                event_index=i,
                phase="over",
                seat=-1,
                view=None,
                analysis=None,
                advice=None,
                comment="牌墙摸完,流局。",
            ))

    summary = {
        "num_steps": len(steps),
        "per_seat": per_seat,
        "events": dict(event_counts),
    }
    return ReviewResult(meta=dict(rec.meta), summary=summary, steps=steps)
