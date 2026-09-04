"""tests for Phase 6 API:POST /api/phase6/review(牌谱逐步回放 + AI 点评)。

覆盖:POST record -> 200 且 schema 齐全;seed -> 200;非法 record -> 400;
record/seed 二选一校验;seat_focus 过滤;hints_on 默认关(advice null);根端点含 phase6。
沿用 httpx TestClient 模式(见 test_practice_api.py)。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from majiang_coach.engine.game import Game, RandomActor

client = TestClient(app)


def _record(seed: int) -> dict:
    return Game([RandomActor(seed * 4 + i) for i in range(4)], seed).run().to_dict()


_STEP_KEYS = {
    "step", "event_index", "phase", "seat", "tile", "hand_total",
    "actual_action", "view", "analysis", "advice", "comment", "fans", "score",
}


# ---- 基本 200 + schema ----

def test_post_seed_returns_review():
    r = client.post("/api/phase6/review", json={"seed": 42})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d.keys()) == {"meta", "summary", "steps"}
    assert d["meta"]["seed"] == 42
    assert d["summary"]["num_steps"] == len(d["steps"])
    assert d["summary"]["num_steps"] > 0
    # per_seat 4 座
    assert set(int(k) for k in d["summary"]["per_seat"].keys()) == {0, 1, 2, 3}


def test_post_record_returns_review():
    record = _record(7)
    r = client.post("/api/phase6/review", json={"record": record})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["meta"]["seed"] == 7
    steps = d["steps"]
    assert steps
    for s in steps:
        assert set(s.keys()) == _STEP_KEYS
        assert s["comment"]


def test_turn_action_step_schema_complete():
    d = client.post("/api/phase6/review", json={"seed": 42}).json()
    ta = next(s for s in d["steps"] if s["phase"] == "turn_action")
    assert ta["view"] is not None
    assert set(ta["view"].keys()) >= {"seat", "hand", "melds", "discards",
                                      "public_melds", "wall_remaining", "turn"}
    assert ta["analysis"]["hand_total"] == ta["hand_total"]
    assert "recommend" in ta["analysis"]
    assert ta["actual_action"] is not None
    # 默认 hints_on=false -> advice null
    assert ta["advice"] is None


def test_claim_step_when_claimable():
    """至少一局出现 claim 步,且 analysis.claim 非空。"""
    found = False
    for seed in range(40):
        d = client.post("/api/phase6/review", json={"seed": seed}).json()
        for s in d["steps"]:
            if s["phase"] == "claim":
                found = True
                claim = s["analysis"].get("claim")
                assert claim and (claim["can_ron"] or claim["can_pon"])
                assert s["view"]["last_discard"] is not None
        if found:
            break
    assert found, "40 局未见 claim 步(覆盖不足)"


def test_over_step_present():
    d = client.post("/api/phase6/review", json={"seed": 42}).json()
    over = [s for s in d["steps"] if s["phase"] == "over"]
    assert over and over[0]["seat"] == -1


# ---- hints_on ----

def test_hints_on_without_config_fallback():
    """hints_on=true 无 llm 配置 -> advice dict 非 null 但内部 advice=null+error,analysis 在。"""
    d = client.post("/api/phase6/review", json={"seed": 42, "hints_on": True}).json()
    turn = [s for s in d["steps"] if s["phase"] == "turn_action"]
    assert turn and all(s["advice"] is not None for s in turn)
    assert all(s["advice"]["advice"] is None for s in turn)
    assert all(s["advice"]["error"] for s in turn)
    assert all(s["advice"]["analysis"] is not None for s in turn)


def test_hints_off_advice_null():
    d = client.post("/api/phase6/review", json={"seed": 42, "hints_on": False}).json()
    assert all(s["advice"] is None for s in d["steps"])


# ---- seat_focus ----

def test_seat_focus_filters_steps():
    full = client.post("/api/phase6/review", json={"seed": 42}).json()
    focused = client.post("/api/phase6/review", json={"seed": 42, "seat_focus": 2}).json()
    assert focused["summary"]["num_steps"] < full["summary"]["num_steps"]
    for s in focused["steps"]:
        if s["phase"] != "over":
            assert s["seat"] == 2


# ---- 400 校验 ----

def test_neither_record_nor_seed_400():
    r = client.post("/api/phase6/review", json={})
    assert r.status_code == 400


def test_both_record_and_seed_400():
    r = client.post("/api/phase6/review", json={"seed": 1, "record": _record(1)})
    assert r.status_code == 400


def test_record_missing_events_400():
    r = client.post("/api/phase6/review", json={"record": {"meta": {}, "events": None}})
    assert r.status_code == 400


def test_invalid_record_events_400():
    bad = {"meta": {}, "events": [{"t": "draw", "seat": 0, "tile": "ZZ"}]}
    r = client.post("/api/phase6/review", json={"record": bad})
    assert r.status_code == 400


def test_garbage_body_400():
    r = client.post("/api/phase6/review", json={"record": {"meta": {}, "events": "x"}})
    assert r.status_code == 400


def test_record_empty_events_400():
    r = client.post("/api/phase6/review", json={"record": {"events": []}})
    assert r.status_code == 400


# ---- 根端点 ----

def test_root_lists_phase6_and_version():
    root = client.get("/").json()
    assert root["version"] == "0.4.0"
    assert "/api/phase6/review" in root["endpoints"]
