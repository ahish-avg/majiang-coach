"""tests for review/review.py:复盘编排(Phase 6)。

覆盖:确定性(同 record -> to_dict 全等);hints_on=false -> advice 全 null;
hints_on=true + 假 LLM(镜像 test_llm_advisor.py 的 provider.chat monkeypatch)
-> advice 非空且防幻觉拦截路径仍生效;seat_focus 过滤;汇总 per_seat 统计;
claim/win/over 步结构;to_dict/from_dict 往返。
"""

from __future__ import annotations

import json
import re

import pytest

from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.record import GameRecord
from majiang_coach.llm import advisor
from majiang_coach.llm.config import LLMConfig
from majiang_coach.review import ReviewCursor, review_record
from majiang_coach.review.result import ReviewResult

_CFG = LLMConfig("https://x", "sk-key", "demo-model")


def _game(seed: int) -> GameRecord:
    return Game([RandomActor(seed * 4 + i) for i in range(4)], seed).run()


# ---- 假 LLM provider(镜像 test_llm_advisor.py 模式)----

_REC_RE = re.compile(r'"recommend"\s*:\s*\{[^{}]*"code"\s*:\s*"([^"]+)"')


def _extract_rec(messages) -> str | None:
    """从注入到 user 消息的 context JSON 中提取硬算推荐牌码。"""
    for m in messages:
        mm = _REC_RE.search(m.get("content", ""))
        if mm:
            return mm.group(1)
    return None


def _advice_payload(recommended_tile):
    return json.dumps({
        "recommended_tile": recommended_tile,
        "offense_reason": "弃后下叫",
        "defense_reason": "现物稍安全",
        "teaching_point": "学综合权衡",
        "opponent_read": "对家缺筒",
    }, ensure_ascii=False)


def _fake_chat_agree(messages, config, json_mode=True):
    """返回推荐牌与硬算一致(14 张);待摸态 recommended_tile=null。"""
    return _advice_payload(_extract_rec(messages))


def _fake_chat_wrong(messages, config, json_mode=True):
    """永远返回与硬算不同的牌 -> 防幻觉拦截。"""
    rec = _extract_rec(messages)
    wrong = "9p" if rec != "9p" else "9m"
    return _advice_payload(wrong)


# ---- 确定性 ----

@pytest.mark.parametrize("seed", [42, 7, 99])
def test_deterministic_same_record(seed):
    """同一 record + 同一参数 -> 两次 to_dict 全等(hints_on=false)。"""
    record = _game(seed)
    a = review_record(record, hints_on=False).to_dict()
    b = review_record(record, hints_on=False).to_dict()
    assert a == b


def test_deterministic_dict_input():
    record = _game(42)
    a = review_record(record.to_dict(), hints_on=False).to_dict()
    b = review_record(record, hints_on=False).to_dict()
    assert a == b


# ---- hints_off ----

def test_hints_off_advice_all_null():
    record = _game(42)
    res = review_record(record, hints_on=False)
    turn = [s for s in res.steps if s.phase == "turn_action"]
    assert turn, "应至少有一个 turn_action 步"
    for s in turn:
        assert s.advice is None
        assert s.analysis is not None  # analysis 始终在
    # claim/win/over 步 advice 亦为 None
    for s in res.steps:
        if s.phase != "turn_action":
            assert s.advice is None


def test_turn_action_view_and_analysis_present():
    record = _game(7)
    res = review_record(record)
    for s in res.steps:
        if s.phase == "turn_action":
            assert s.view is not None
            assert s.view["hand_total"] == s.hand_total
            assert s.analysis["hand_total"] == s.hand_total
            assert "recommend" in s.analysis
            assert s.comment


# ---- hints_on + 假 LLM ----

def test_hints_on_fake_llm_advice_present(monkeypatch):
    monkeypatch.setattr(advisor, "chat", _fake_chat_agree)
    record = _game(42)
    res = review_record(record, hints_on=True, llm_config=_CFG)
    turn = [s for s in res.steps if s.phase == "turn_action"]
    assert turn
    n_advised = 0
    for s in turn:
        adv = s.advice
        assert adv is not None, "hints_on 时 advice 字段应为 AdviseResult dict"
        assert adv["hints_on"] is True
        assert adv["analysis"] is not None
        # 假 LLM 与硬算一致 -> advice.advice 非空
        if s.analysis.get("recommend"):
            assert adv["advice"] is not None, f"步 {s.step} 应给出 Advice"
            assert adv["advice"]["recommended_tile"] == s.analysis["recommend"]["code"]
            assert adv["error"] is None
            n_advised += 1
    assert n_advised > 0


def test_hints_on_antihallucination_still_blocks(monkeypatch):
    """假 LLM 返回错误推荐牌 -> 防幻觉拦截:advice=null + error,analysis 仍在。"""
    monkeypatch.setattr(advisor, "chat", _fake_chat_wrong)
    record = _game(42)
    res = review_record(record, hints_on=True, llm_config=_CFG)
    turn = [s for s in res.steps if s.phase == "turn_action"]
    blocked = [s for s in turn if s.analysis.get("recommend")]
    assert blocked
    for s in blocked:
        adv = s.advice
        assert adv["advice"] is None
        assert "防幻觉" in adv["error"]
        assert adv["analysis"] is not None  # analysis 始终在


def test_hints_on_no_config_fallback():
    """hints_on=true 但无 llm_config -> advice=null+error,analysis 仍在。"""
    record = _game(42)
    res = review_record(record, hints_on=True, llm_config=None)
    turn = [s for s in res.steps if s.phase == "turn_action"]
    for s in turn:
        assert s.advice["advice"] is None
        assert "未配置" in s.advice["error"]
        assert s.advice["analysis"] is not None
        # step.analysis 与 advice.analysis 同一份硬算
        assert s.analysis == s.advice["analysis"]


def test_hints_on_deterministic_with_fake(monkeypatch):
    monkeypatch.setattr(advisor, "chat", _fake_chat_agree)
    record = _game(7)
    a = review_record(record, hints_on=True, llm_config=_CFG).to_dict()
    b = review_record(record, hints_on=True, llm_config=_CFG).to_dict()
    assert a == b


# ---- seat_focus ----

def test_seat_focus_only_reviews_one_seat():
    record = _game(42)
    res = review_record(record, seat_focus=0)
    steps = [s for s in res.steps if s.phase != "over"]
    assert steps, "应有非 over 步"
    for s in steps:
        assert s.seat == 0, f"seat_focus=0 但出现座 {s.seat}({s.phase})"


def test_seat_focus_list_and_summary_still_complete():
    record = _game(42)
    res = review_record(record, seat_focus=[1])
    steps = [s for s in res.steps if s.phase != "over"]
    assert all(s.seat == 1 for s in steps)
    # 汇总仍含全部 4 座事实
    assert set(res.summary["per_seat"].keys()) == {0, 1, 2, 3}


def test_seat_focus_reduces_steps():
    record = _game(42)
    full = review_record(record)
    focus = review_record(record, seat_focus=0)
    assert focus.summary["num_steps"] < full.summary["num_steps"]


# ---- 汇总结构 ----

def test_summary_structure():
    record = _game(42)
    res = review_record(record)
    summary = res.summary
    assert summary["num_steps"] == len(res.steps)
    assert set(summary["per_seat"].keys()) == {0, 1, 2, 3}
    for seat, stats in summary["per_seat"].items():
        assert set(stats.keys()) == {"turn_steps", "matched_actual", "win_by", "claims"}
        assert stats["turn_steps"] >= 0
        assert 0 <= stats["matched_actual"] <= stats["turn_steps"]
    assert "events" in summary
    assert summary["events"].get("discard") is not None


def test_matched_actual_within_bounds():
    """matched_actual 不超过该座 turn_steps(多种子抽查)。"""
    for seed in (1, 2, 3, 42):
        res = review_record(_game(seed))
        for seat, stats in res.summary["per_seat"].items():
            assert stats["matched_actual"] <= stats["turn_steps"], f"seed {seed} 座{seat}"


# ---- claim / win / over 步 ----

def test_claim_steps_have_claimable_info():
    """claim 步:phase=claim,analysis.claim 含 can_ron/can_pon,actual_action 合法。"""
    found_claim = False
    for seed in range(40):
        res = review_record(_game(seed))
        for s in res.steps:
            if s.phase == "claim":
                found_claim = True
                claim = s.analysis.get("claim") or {}
                assert claim.get("can_ron") or claim.get("can_pon")
                assert s.view is not None
                if s.actual_action is not None:
                    assert s.actual_action["kind"] in ("pon", "daiminkan", "ron")
                assert s.tile is not None
        if found_claim:
            break
    assert found_claim, "40 局未见可申索 claim 步(覆盖不足)"


def test_win_steps_and_win_by():
    """tsumo/ron -> win 步,summary.win_by 标注;至少一局出现胡牌。"""
    found = False
    for seed in range(40):
        res = review_record(_game(seed))
        win_steps = [s for s in res.steps if s.phase == "win"]
        for s in win_steps:
            found = True
            assert s.actual_action["kind"] in ("tsumo", "ron")
            assert "胡" in s.comment  # 自摸/点炮/抢杠 文案均含“胡”
            # Phase 7:win 步带番种与倍数(fans/score),占位文案消失
            assert s.fans is not None and s.score is not None
            assert s.fans["multiplier"] == 1 << (s.fans["total_fan"] - 1)
            assert s.score["multiplier"] == s.fans["multiplier"]
            assert s.score["payer_seats"]
            assert "倍" in s.comment and "不算番" not in s.comment
        winners_by = {seat: st["win_by"] for seat, st in res.summary["per_seat"].items()
                      if st["win_by"] is not None}
        for s in win_steps:
            assert winners_by.get(s.seat) in ("tsumo", "ron")
        if found:
            break
    assert found, "40 局未见胡牌步(覆盖不足)"


def test_over_step_on_draw():
    """流局 -> over 步;流局局必有。"""
    record = _game(42)
    res = review_record(record)
    over = [s for s in res.steps if s.phase == "over"]
    # 42 局为流局
    assert over and over[0].seat == -1
    assert "流局" in over[0].comment


# ---- 信息隔离 / 不修改既有行为 ----

def test_views_are_information_isolated():
    """turn_action/claim 步的 view 只含本座 hand,public 信息齐全,无他家暗手。"""
    record = _game(7)
    res = review_record(record)
    for s in res.steps:
        if s.view is not None and s.phase in ("turn_action", "claim"):
            v = s.view
            assert len(v["hand"]) == v["hand_total"]
            assert len(v["discards"]) == 4
            assert len(v["public_melds"]) == 4
            assert len(v["lack_suits"]) == 4
            assert len(v["active_seats"]) >= 1
            break


def test_result_roundtrip():
    record = _game(42)
    res = review_record(record)
    d = res.to_dict()
    assert ReviewResult.from_dict(d).to_dict() == d


def test_step_numbers_sequential():
    record = _game(42)
    res = review_record(record)
    assert [s.step for s in res.steps] == list(range(1, len(res.steps) + 1))


def test_cursor_final_state_anchor():
    """review 用的 cursor 终局与 replay 一致(锚点)。"""
    from majiang_coach.engine.record import replay
    record = _game(42)
    assert ReviewCursor(record).final_state() == replay(record)
