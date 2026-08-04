"""tests for Phase 5 API:REST 轮次制练习会话端点。

覆盖:创建/取提示/提交/问教练/结束;hints_on=false -> advise=null;非法动作 400;
game_over 返 record+summary;完整一局闭环(human 自动)。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, _phase5_store
from majiang_coach.ai import HeuristicActor
from majiang_coach.engine.action import Action, lack_action

client = TestClient(app)


def _auto_action_from_prompt(p):
    """从 prompt 的 legal_actions 选一个合法动作 dict(模拟人类)。"""
    actor = HeuristicActor("mid", 0)
    phase = p["phase"]
    las = p["legal_actions"]
    if phase == "swap":
        # 自由选 3 张:从 view 手牌选最弱门 3 张
        from majiang_coach.tiles import code_to_index
        hand_codes = p["view"]["hand"]
        hand_idxs = [code_to_index(c) for c in hand_codes]
        from majiang_coach.hand import Hand
        from majiang_coach.engine.view import PlayerView
        v = PlayerView(seat=0, hand=Hand.from_indices(hand_idxs))
        t3 = actor.choose_swap(v)
        return {"kind": "swap", "tiles": [__import__("majiang_coach.tiles", fromlist=["index_to_code"]).index_to_code(t) for t in t3]}
    if phase == "lack":
        hint = p.get("hint") or {}
        suit = hint.get("suggest_suit", "m")
        return {"kind": "lack", "suit": suit}
    # turn_action / claim / robbery:从 legal_actions 选第一个(偏安全:优先 pass/discard)
    if not las:
        return {"kind": "pass"}
    # 优先 discard(避免误胡),claim/robbery 取 pass
    for a in las:
        if a["kind"] == "discard":
            return a
    for a in las:
        if a["kind"] == "pass":
            return a
    return las[0]


@pytest.fixture(autouse=True)
def _clean_store():
    _phase5_store._sessions.clear()
    yield
    _phase5_store._sessions.clear()


def test_create_session_returns_swap_prompt():
    r = client.post("/api/phase5/session", json={"seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    p = body["prompt"]
    assert p["phase"] == "swap"
    assert p["game_over"] is False
    assert p["view"] is not None


def test_get_session_prompt():
    sid = client.post("/api/phase5/session", json={"seed": 2}).json()["session_id"]
    r = client.get(f"/api/phase5/session/{sid}")
    assert r.status_code == 200
    assert r.json()["phase"] == "swap"


def test_get_unknown_session_404():
    r = client.get("/api/phase5/session/nope")
    assert r.status_code == 404


def test_invalid_ai_strengths_count():
    r = client.post("/api/phase5/session", json={"ai_strengths": ["mid", "mid"]})
    assert r.status_code == 400


def test_submit_swap_then_lack_then_turn_action():
    sid = client.post("/api/phase5/session", json={"seed": 3}).json()["session_id"]
    # swap
    p = client.get(f"/api/phase5/session/{sid}").json()
    r = client.post(f"/api/phase5/session/{sid}/act",
                    json={"action": _auto_action_from_prompt(p)})
    assert r.status_code == 200
    assert r.json()["phase"] == "lack"
    # lack
    p = r.json()
    r = client.post(f"/api/phase5/session/{sid}/act",
                    json={"action": _auto_action_from_prompt(p)})
    assert r.status_code == 200
    assert r.json()["phase"] == "turn_action"


def test_illegal_action_returns_400_state_unchanged():
    sid = client.post("/api/phase5/session", json={"seed": 4}).json()["session_id"]
    # 推进到 turn_action
    p = client.get(f"/api/phase5/session/{sid}").json()
    client.post(f"/api/phase5/session/{sid}/act", json={"action": _auto_action_from_prompt(p)})
    p = client.get(f"/api/phase5/session/{sid}").json()
    client.post(f"/api/phase5/session/{sid}/act", json={"action": _auto_action_from_prompt(p)})
    p = client.get(f"/api/phase5/session/{sid}").json()  # turn_action
    assert p["phase"] == "turn_action"
    # 非法:弃一张手中没有的牌
    hand_codes = set(p["view"]["hand"])
    illegal = {"kind": "discard", "tile": "9p"}
    # 找一张手中没有的牌
    from majiang_coach.tiles import TILE_CODES
    for code in TILE_CODES:
        if code not in hand_codes:
            illegal = {"kind": "discard", "tile": code}
            break
    r = client.post(f"/api/phase5/session/{sid}/act", json={"action": illegal})
    assert r.status_code == 400
    # state 不变:再次取提示仍是 turn_action
    p2 = client.get(f"/api/phase5/session/{sid}").json()
    assert p2["phase"] == "turn_action"


def test_hints_off_advise_null():
    sid = client.post("/api/phase5/session",
                      json={"seed": 5, "hints_on": False}).json()["session_id"]
    # 推进到 turn_action
    for _ in range(2):
        p = client.get(f"/api/phase5/session/{sid}").json()
        client.post(f"/api/phase5/session/{sid}/act",
                    json={"action": _auto_action_from_prompt(p)})
    p = client.get(f"/api/phase5/session/{sid}").json()
    assert p["phase"] == "turn_action"
    assert p["advise"] is None  # 纯实战不调 LLM
    assert p["hint"] is not None


def test_advise_on_demand_without_config():
    sid = client.post("/api/phase5/session",
                      json={"seed": 6, "hints_on": False}).json()["session_id"]
    for _ in range(2):
        p = client.get(f"/api/phase5/session/{sid}").json()
        client.post(f"/api/phase5/session/{sid}/act",
                    json={"action": _auto_action_from_prompt(p)})
    p = client.get(f"/api/phase5/session/{sid}").json()
    assert p["phase"] == "turn_action"
    r = client.post(f"/api/phase5/session/{sid}/advise", json={})
    assert r.status_code == 200
    res = r.json()
    assert res["advice"] is None  # 无配置
    assert res["analysis"] is not None


def test_delete_session():
    sid = client.post("/api/phase5/session", json={"seed": 7}).json()["session_id"]
    r = client.delete(f"/api/phase5/session/{sid}")
    assert r.status_code == 200
    assert client.get(f"/api/phase5/session/{sid}").status_code == 404


def test_full_game_loop_game_over_returns_record():
    """完整一局闭环:human 自动,终局 prompt 含 record + summary。"""
    sid = client.post("/api/phase5/session",
                      json={"seed": 8, "ai_strengths": ["mid", "mid", "mid"]}).json()["session_id"]
    steps = 0
    p = client.get(f"/api/phase5/session/{sid}").json()
    while not p["game_over"]:
        r = client.post(f"/api/phase5/session/{sid}/act",
                        json={"action": _auto_action_from_prompt(p)})
        assert r.status_code == 200, f"步 {steps}: {r.text}"
        p = r.json()
        steps += 1
        if steps > 3000:
            pytest.fail("步数过多")
    assert p["game_over"] is True
    assert p["phase"] == "game_over"
    assert "record" in p
    assert "summary" in p
    assert "meta" in p["record"]
    assert "events" in p["record"]
