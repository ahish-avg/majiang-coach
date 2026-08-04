"""tests for llm/prompt.py(Phase 4,见计划 §5/§8.3)。"""

from __future__ import annotations

import json

from majiang_coach.llm.prompt import SYSTEM_PROMPT, build_messages


def _sample_context() -> dict:
    return {
        "phase": "discard",
        "lack_suit": "p",
        "wall_remaining": 30,
        "weights_used": {"offense": 0.6, "defense": 0.4},
        "hand": {"shanten": 0, "is_tenpai": True, "ukeire_count": 1, "ukeire_remaining_total": 3, "score": 80},
        "recommend": {"code": "5m", "offense": 70, "danger": 10, "defense": 90,
                      "composite": 80, "shanten_after": 0, "ukeire_count": 1,
                      "ukeire_remaining_total": 3, "safety_reasons": ["未见张为0,绝对安全"]},
        "top5": [{"code": "5m", "offense": 70, "danger": 10, "defense": 90, "composite": 80}],
        "best_offense": "5m",
        "best_defense": "5m",
        "claim": None,
        "opponents": [{"seat": 1, "lack": "p", "threat": 0.35, "meld_count": 0}],
    }


def test_build_messages_structure():
    msgs = build_messages(_sample_context())
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[0]["content"] is SYSTEM_PROMPT


def test_system_prompt_contains_rules_and_schema():
    s = SYSTEM_PROMPT
    # 防幻觉铁律关键词
    for kw in ["严禁自创", "recommended_tile", "川麻口语", "教学", "可见信息", "JSON"]:
        assert kw in s
    # 输出 schema 字段
    for field in ["offense_reason", "defense_reason", "teaching_point", "opponent_read"]:
        assert field in s


def test_user_content_is_context_json():
    msgs = build_messages(_sample_context())
    user = msgs[1]["content"]
    assert "分析数据" in user
    # 抽取 user 中的 JSON 块并验证可还原 context
    start = user.index("{")
    payload = json.loads(user[start:])
    assert payload["recommend"]["code"] == "5m"
    assert payload["phase"] == "discard"


def test_system_prompt_constrains_recommended_tile():
    # 待摸态 recommended_tile=null 约束在铁律中明示
    assert "待摸态为 null" in SYSTEM_PROMPT


def test_build_messages_13tile_context():
    ctx = _sample_context()
    ctx["phase"] = "wait"
    ctx["recommend"] = None
    ctx["top5"] = []
    ctx["claim"] = {"code": "5m", "can_ron": True, "can_pon": False, "pon_shanten_after": None}
    msgs = build_messages(ctx)
    payload = json.loads(msgs[1]["content"][msgs[1]["content"].index("{"):])
    assert payload["phase"] == "wait"
    assert payload["recommend"] is None
    assert payload["claim"]["can_ron"] is True
