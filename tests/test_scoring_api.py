"""tests for Phase 7 API:POST /api/phase7/score(完整结算)。

覆盖:seed -> 200;record -> 200 且 schema 齐全;record/seed 二选一(都给/都缺 -> 400);
非法 record -> 400;rules 覆盖生效 + 未知键 400;base 底分缩放;根端点含 phase7。
沿用 httpx TestClient 模式(见 test_review_api.py)。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from majiang_coach.engine.game import Game, RandomActor

client = TestClient(app)


def _record(seed: int) -> dict:
    return Game([RandomActor(seed * 4 + i) for i in range(4)], seed).run().to_dict()


_RESULT_KEYS = {
    "wins", "kans", "tenpais", "huazhus", "per_seat",
    "drawn", "base_score", "rules_used",
}


def test_root_lists_phase7():
    r = client.get("/")
    assert r.status_code == 200
    assert "/api/phase7/score" in r.json()["endpoints"]
    assert r.json()["version"] == "0.4.0"


def test_post_seed_returns_settlement():
    r = client.post("/api/phase7/score", json={"seed": 42})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d.keys()) == _RESULT_KEYS
    assert set(int(k) for k in d["per_seat"].keys()) == {0, 1, 2, 3}
    assert sum(d["per_seat"].values()) == 0
    assert d["base_score"] == 1
    assert d["rules_used"]["cap_fan"] == 5


def test_post_record_returns_settlement():
    record = _record(7)
    r = client.post("/api/phase7/score", json={"record": record})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d.keys()) == _RESULT_KEYS
    for w in d["wins"]:
        fan = w["fan"]
        assert {"items", "total_fan", "cap_applied", "multiplier", "by"} <= set(fan.keys())
        assert fan["multiplier"] == 1 << (fan["total_fan"] - 1)


def test_seed_and_record_both_given_400():
    r = client.post("/api/phase7/score", json={"seed": 1, "record": _record(1)})
    assert r.status_code == 400


def test_neither_seed_nor_record_400():
    r = client.post("/api/phase7/score", json={})
    assert r.status_code == 400


def test_record_missing_events_400():
    r = client.post("/api/phase7/score", json={"record": {"meta": {}, "events": "x"}})
    assert r.status_code == 400


def test_record_empty_events_400():
    r = client.post("/api/phase7/score", json={"record": {"events": []}})
    assert r.status_code == 400


def test_bad_record_400():
    r = client.post("/api/phase7/score", json={"record": {"events": [{"t": "tsumo"}]}})
    assert r.status_code == 400


def test_rules_override_applied():
    """cap_fan=3:倍数封顶 4;rules_used 回显覆盖值。"""
    r = client.post("/api/phase7/score", json={"seed": 42, "rules": {"cap_fan": 3}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["rules_used"]["cap_fan"] == 3
    for w in d["wins"]:
        assert w["fan"]["multiplier"] <= 4


def test_rules_unknown_key_400():
    r = client.post("/api/phase7/score", json={"seed": 1, "rules": {"nope": 1}})
    assert r.status_code == 400


def test_base_scales_amounts():
    """base=10:胡牌/杠钱金额 ×10。"""
    r1 = client.post("/api/phase7/score", json={"seed": 13}).json()
    r10 = client.post("/api/phase7/score", json={"seed": 13, "base": 10}).json()
    if r1["wins"]:
        assert r10["wins"][0]["amount_each"] == r1["wins"][0]["amount_each"] * 10
    assert r10["base_score"] == 10
    assert sum(r10["per_seat"].values()) == 0
