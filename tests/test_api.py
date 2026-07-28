"""tests for api.main (FastAPI Phase 1 endpoint)"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "majiang-coach"
    assert "/api/phase2/play" in body["endpoints"]
    assert "/api/phase3/analyze" in body["endpoints"]


def test_analyze_win():
    r = client.post("/api/phase1/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 14
    assert body["is_win"] is True
    assert body["shanten"] == -1
    assert body["is_tenpai"] is False
    assert body["suits_present"] == ["万", "条"]


def test_analyze_tenpai_machi():
    r = client.post("/api/phase1/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 13
    assert body["is_win"] is False
    assert body["is_tenpai"] is True
    assert body["shanten"] == 0
    ukeire_codes = [u["code"] for u in body["ukeire"]]
    assert ukeire_codes == ["5s"]
    assert body["ukeire"][0]["new_shanten"] == -1


def test_analyze_lack_suit():
    # 4 面子 + 1 缺门(5p,缺筒)-> 向听 1
    r = client.post("/api/phase1/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"],
        "lack_suit": "p",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["shanten"] == 1
    assert body["lack_suit"] == "p"
    assert "5p" not in [u["code"] for u in body["ukeire"]]


def test_analyze_lack_null_enumerates():
    # 不指定缺门 -> 自动枚举,4面子+1缺门(5p)仍为 1(缺筒最优)
    r = client.post("/api/phase1/analyze", json={
        "codes": ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5p"],
    })
    assert r.status_code == 200
    assert r.json()["shanten"] == 1


def test_analyze_invalid_codes_400():
    r = client.post("/api/phase1/analyze", json={"codes": ["0m", "1z"]})
    assert r.status_code == 400


def test_analyze_empty_codes_400():
    r = client.post("/api/phase1/analyze", json={"codes": []})
    assert r.status_code == 400


def test_analyze_invalid_lack_422():
    r = client.post("/api/phase1/analyze", json={
        "codes": ["1m2m3m"],
        "lack_suit": "z",
    })
    assert r.status_code == 422  # Literal 校验失败


# ---- Phase 2 ----

def test_phase2_play():
    r = client.post("/api/phase2/play", json={"seed": 42})
    assert r.status_code == 200
    body = r.json()
    assert "record" in body and "summary" in body
    rec = body["record"]
    assert rec["meta"]["ruleset"] == "sichuan-xuezhan"
    assert rec["meta"]["seed"] == 42
    assert "events" in rec and len(rec["events"]) > 0
    assert "result" in rec
    s = body["summary"]
    assert s["seed"] == 42
    assert isinstance(s["drawn"], bool)
    # 赢家数 + 输家数 = 4
    assert len(s["winners"]) + len(s["losers"]) == 4


def test_phase2_play_reproducible():
    r1 = client.post("/api/phase2/play", json={"seed": 7})
    r2 = client.post("/api/phase2/play", json={"seed": 7})
    assert r1.json()["record"] == r2.json()["record"]


def test_phase2_play_default_seed():
    r = client.post("/api/phase2/play", json={})
    assert r.status_code == 200
    assert r.json()["summary"]["seed"] == 42
