"""tests for POST /api/phase3/analyze (Phase 3 API 端点)。"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_phase3_14tile_candidates():
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],
        "lack_suit": "p",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["seat"] == 0
    assert body["hand_total"] == 14
    assert body["lack_suit"] == 2
    assert body["weights_used"] == {"offense": 0.6, "defense": 0.4}
    assert len(body["candidates"]) > 0
    assert body["recommend"] is not None
    assert body["best_offense"] is not None
    assert body["best_defense"] is not None
    assert body["claim"] is None  # 14 张无 claim
    # 候选字段齐全
    c = body["candidates"][0]
    for k in ["tile", "code", "shanten_after", "ukeire", "offense_score",
              "danger", "defense_score", "composite_score", "safety_reasons",
              "per_opponent"]:
        assert k in c


def test_phase3_13tile_claim():
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
        "lack_suit": "p",
        "last_discard": "5m",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["hand_total"] == 13
    assert body["candidates"] == []
    assert body["recommend"] is None
    assert body["claim"] is not None
    assert body["claim"]["can_ron"] is True  # 5m 是叫牌
    assert body["claim"]["can_pon"] is False


def test_phase3_pon_claim():
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "3m4m"],
        "lack_suit": "p",
        "last_discard": "5s",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["claim"]["can_pon"] is True
    assert body["claim"]["pon_shanten_after"] == 0


def test_phase3_melds():
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"],
        "lack_suit": "p",
        "melds": [{"kind": "pon", "tile": "5m", "src": 1}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["hand_total"] == 11  # 14-3*1
    assert len(body["melds"]) == 1
    assert body["melds"][0]["tile"] == "5m"
    assert body["hand"]["shanten"] == -1  # 3面子+将对=胡


def test_phase3_weights_override():
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],
        "lack_suit": "p",
        "weights": {"offense": 0.8, "defense": 0.2},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["weights_used"] == {"offense": 0.8, "defense": 0.2}


def test_phase3_lack_suits_affect_safety():
    # 对家缺筒 -> 弃筒牌对对家安全;lack_suits 暴露他座缺门
    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s", "5p6p"],
        "lack_suit": "p",
        "lack_suits": ["p", "p", "m", "s"],
    })
    assert r.status_code == 200
    body = r.json()
    # 有缺门牌(筒) -> candidates 只含筒
    cand_tiles = [c["tile"] for c in body["candidates"]]
    assert all(18 <= t <= 26 for t in cand_tiles)


def test_phase3_empty_codes_400():
    r = client.post("/api/phase3/analyze", json={"codes": []})
    assert r.status_code == 400


def test_phase3_invalid_codes_400():
    r = client.post("/api/phase3/analyze", json={"codes": ["zz"]})
    assert r.status_code == 400


def test_phase3_json_schema_consistency():
    """to_dict 输出可被 from_dict 还原(字段完整、类型一致)。"""
    from majiang_coach.analysis import analysis_result_from_dict

    r = client.post("/api/phase3/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],
        "lack_suit": "p",
    })
    body = r.json()
    result = analysis_result_from_dict(body)
    assert result.hand_total == 14
    assert result.recommend is not None
