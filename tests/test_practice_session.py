"""tests for practice/session.py: 练习模式会话状态机。

覆盖:5 类决策点暂停+恢复、自动推进 AI、非法动作拒绝(state 不变)、抢杠暂停
(可抢/不抢两条)、缺门约束、人类拒胡、终局牌谱 replay 一致 + 张数守恒、提示开关。
"""

from __future__ import annotations

import random
from collections import Counter

import pytest

from majiang_coach import tiles
from majiang_coach.ai import HeuristicActor
from majiang_coach.engine.action import Action, lack_action
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.record import replay
from majiang_coach.engine.wall import TileWall
from majiang_coach.hand import Hand
from majiang_coach.practice import PracticeSession, IllegalActionError

_S5 = 13  # 5s
_SUIT_LETTER = {0: "m", 1: "s", 2: "p"}


# ---- 辅助:自动人类(用 HeuristicActor 替人类决策)----

def auto_pick(pending, strength="mid"):
    actor = HeuristicActor(strength, 0)
    k = pending.kind
    if k == "swap":
        return Action("swap", tiles=actor.choose_swap(pending.view))
    if k == "lack":
        return lack_action(actor.choose_lack(pending.view))
    if k == "turn_action":
        return actor.choose_turn_action(pending.view, pending.drawn)
    if k in ("claim", "robbery"):
        return actor.choose_claim(pending.view, pending.legal_actions)
    raise ValueError(k)


def play_to_end(session, strength="mid", max_steps=4000):
    """自动跑完一局(人类用 HeuristicActor),返回步数。"""
    steps = 0
    while not session.is_over():
        session.current_prompt()
        if session.is_over():
            break
        session.submit(auto_pick(session.pending, strength))
        steps += 1
        if steps > max_steps:
            raise RuntimeError("步数过多,疑似死循环")
    return steps


def _build_wall(used_indices, front=None, seed=0):
    """从 108 张中扣除已用(手牌+副露),构建剩余牌墙;front 强制为首摸。"""
    used = Counter(used_indices)
    remaining = []
    for i in range(tiles.NUM_TILES):
        remaining.extend([i] * (4 - used.get(i, 0)))
    rng = random.Random(seed)
    rng.shuffle(remaining)
    if front is not None and front in remaining:
        remaining.remove(front)
        remaining = [front] + remaining
    return TileWall(seed, preset=remaining)


def _fast_forward_to_main_loop(session, strength="mid"):
    """跑过 swap+lack,进入主循环(人类首个 turn_action),返回。"""
    session.current_prompt()  # swap
    session.submit(auto_pick(session.pending, strength))
    session.current_prompt()  # lack
    session.submit(auto_pick(session.pending, strength))
    # 现在 pending 应为 turn_action(庄家先摸)
    assert session.pending.kind == "turn_action"


# ===== 起始决策点 =====

def test_session_starts_at_swap():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    p = s.current_prompt()
    assert p["phase"] == "swap"
    assert p["game_over"] is False
    assert p["view"] is not None
    assert p["legal_actions"] == []  # swap 自由选 3 张


def test_swap_then_lack_then_turn_action():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=1)
    _fast_forward_to_main_loop(s)
    p = s.current_prompt()
    assert p["phase"] == "turn_action"
    assert "drawn" in p  # 庄家先摸,附摸到的牌


# ===== 自动推进 + 5 类决策点(自然触发 swap/lack/turn_action/claim)=====

def test_decision_points_naturally_occur():
    """多种子自动跑局,swap/lack/turn_action 必现,claim 在某些种子出现。"""
    kinds = set()
    claim_seen = False
    for seed in range(25):
        s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=seed)
        while not s.is_over():
            p = s.current_prompt()
            if s.is_over():
                break
            kinds.add(s.pending.kind)
            s.submit(auto_pick(s.pending))
        assert s.is_over()
    assert {"swap", "lack", "turn_action"} <= kinds
    assert "claim" in kinds  # 25 种子内应出现可申索


def test_auto_advance_runs_ai_between_human_points():
    """人类提交后,AI 自动推进到下一人类点(不暴露 AI 决策细节)。"""
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=2)
    _fast_forward_to_main_loop(s)
    # 人类弃牌后,应自动推进:要么到人类下次 turn_action,要么 claim,要么终局
    p = s.current_prompt()
    assert p["phase"] == "turn_action"
    legal = s.pending.legal_actions
    discard_act = next(a for a in legal if a.kind == "discard")
    s.submit(discard_act)
    # 推进后:pending 应为新决策点或终局(不应停在 AI 的中间步)
    assert s.is_over() or s.pending is not None


# ===== 非法动作拒绝(state 不变)=====

def test_illegal_action_rejected_state_unchanged():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    hand_before = s.state.hands[0].to_indices()
    events_before = len(s._record.events)
    pending_before = s.pending
    # 弃一张手中没有的牌
    illegal = next(i for i in range(27) if s.state.hands[0].count(i) == 0)
    with pytest.raises(IllegalActionError):
        s.submit(Action("discard", tile=illegal))
    assert s.state.hands[0].to_indices() == hand_before
    assert len(s._record.events) == events_before
    assert s.pending is pending_before
    # 拒绝后合法动作仍可用
    legal = s.pending.legal_actions
    s.submit(next(a for a in legal if a.kind == "discard"))


def test_illegal_swap_rejected():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    s.current_prompt()  # swap
    # 不同门 3 张
    hand = s.state.hands[0]
    t_m = next(i for i in range(9) if hand.count(i))
    t_s = next(i for i in range(9, 18) if hand.count(i))
    t_p = next(i for i in range(18, 27) if hand.count(i))
    if t_m is not None and t_s is not None and t_p is not None:
        with pytest.raises(IllegalActionError):
            s.submit(Action("swap", tiles=(t_m, t_s, t_p)))


# ===== 缺门约束 =====

def test_lack_constraint_in_legal_discards():
    """人类有缺门牌时,合法弃牌只列缺门牌。"""
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    lack = s.state.lack[0]
    # 若手中仍有缺门牌,legal discards 须全为缺门牌
    from majiang_coach.engine.action import legal_discards
    view = s.state.make_view(0)
    ld = legal_discards(view)
    has_lack = any(tiles.suit_of(i) == lack for i in range(lack * 9, lack * 9 + 9)
                   if view.hand.count(i) > 0)
    if has_lack:
        assert all(tiles.suit_of(i) == lack for i in ld), "缺门优先未生效"


# ===== 人类可拒胡(战略弃胡)=====

def test_human_can_decline_tsumo():
    """人类可胡自摸时,仍可选弃牌(拒胡合法)。构造可胡场景。"""
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    # 注入:人类手牌为可胡 14 张
    s.state.hands[0] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    s.state.lack[0] = 2
    s._drawn = _S5
    s.pending = None
    s._set_turn_action_pending()
    legal = s.pending.legal_actions
    assert any(a.kind == "tsumo" for a in legal), "应可自摸"
    # 选择弃牌(拒胡)
    discard_act = next(a for a in legal if a.kind == "discard")
    p = s.submit(discard_act)  # 不抛异常即合法拒胡
    assert p["phase"] in ("claim", "turn_action", "game_over") or p["game_over"]


def _setup_claim(session, seat1_codes):
    """覆盖状态:座1(AI 缺条)必弃 5s,座0(人类)听 5s;座2/3 已胡(不参与)。"""
    session.pending = None
    session.state.lack = [2, 1, 1, 1]  # 座0 缺筒,座1-3 缺条
    session.state.hands[0] = Hand.from_codes(_ROBBERY_SEAT0)  # 听 5s
    session.state.hands[1] = Hand.from_codes(seat1_codes)     # 14 张,唯一条牌 5s
    session.state.melds = [[], [], [], []]
    # 座2/3 已胡(不参与申索/续打),使人类 ron 后即 3 胡终局
    session.state.active = [True, True, False, False]
    session.state.winners = [2, 3]
    session.state.wall = TileWall(0, preset=[])  # 空墙:pass 后即流局
    session._mode = "act"; session._seat = 1; session._drawn = tiles.code_to_index("4m")
    session.state.turn = 1; session.state.last_discard = None
    session._advance()


# 座1:14 张(5s + 13 万),缺条 -> 必弃 5s
_CLAIM_SEAT1 = ["5s", "1m2m3m", "4m5m6m", "7m8m9m", "1m2m3m", "4m"]


def test_claim_pause_and_ron():
    """AI 弃人类可胡牌 -> 人类申索暂停 -> 人类 ron 胡牌(3 胡终局)。"""
    s = PracticeSession(["strong", "strong", "strong"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    _setup_claim(s, _CLAIM_SEAT1)
    assert s.pending is not None, "应暂停在 claim(座1 弃 5s,座0 可胡)"
    assert s.pending.kind == "claim"
    assert any(a.kind == "ron" for a in s.pending.legal_actions)
    ron_act = next(a for a in s.pending.legal_actions if a.kind == "ron")
    s.submit(ron_act)
    rec = s._record
    ron_evs = [e for e in rec.events if e["t"] == "ron"]
    assert any(e["seat"] == 0 and e["tile"] == "5s" for e in ron_evs), "人类应 ron 5s"
    assert s.is_over()  # 3 胡终局


def test_claim_pause_and_pass():
    """人类可申索但选择 pass(拒胡),游戏继续(流局);座0 未胡。"""
    s = PracticeSession(["strong", "strong", "strong"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    _setup_claim(s, _CLAIM_SEAT1)
    assert s.pending.kind == "claim"
    s.submit(Action("pass"))  # 空墙 -> 流局
    assert s.is_over()
    assert 0 not in s.state.winners  # 人类未胡


# ===== 抢杠暂停(脚本化:座1 补杠,座0 可抢)=====

_ROBBERY_SEAT1 = ["5s", "6s", "4s", "7s", "5m", "3s", "4m", "2m", "5m", "8s"]  # 10 张(1 副露)
_ROBBERY_SEAT0 = ["1m2m3m", "4m5m6m", "7m8m9m", "3s4s", "6s6s"]  # 听 5s


def _setup_robbery(session, rinshan_tile):
    """覆盖状态:座1(pon 5s)摸 1m 后补杠,座0 可抢;座2/3 已胡。"""
    session.pending = None
    session.state.lack = [2, 2, 2, 2]
    session.state.hands[0] = Hand.from_codes(_ROBBERY_SEAT0)  # 13 张听 5s
    session.state.hands[1] = Hand.from_codes(_ROBBERY_SEAT1)  # 10 张(待摸,1 副露)
    # 座2/3 已胡(不参与抢杠/续打),人类抢杠后即 3 胡终局
    session.state.hands[2] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "4m"])
    session.state.hands[3] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5m"])
    session.state.melds = [[], [Meld("pon", _S5, 0)], [], []]
    session.state.active = [True, True, False, False]
    session.state.winners = [2, 3]
    # 牌墙:首摸 1m(座1),杠尾 rinshan_tile
    m1 = tiles.code_to_index("1m")
    session.state.wall = TileWall(0, preset=[m1, rinshan_tile])
    session._mode = "draw"; session._seat = 1; session._drawn = None
    session.state.turn = 1; session.state.last_discard = None
    session._advance()


def test_robbery_pause_and_rob():
    s = PracticeSession(["strong", "strong", "strong"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    _setup_robbery(s, tiles.code_to_index("2m"))
    assert s.pending is not None, "应暂停在 robbery(座1 补杠,座0 可抢)"
    assert s.pending.kind == "robbery"
    assert any(a.kind == "ron" for a in s.pending.legal_actions)
    ron_act = next(a for a in s.pending.legal_actions if a.kind == "ron")
    s.submit(ron_act)
    rec = s._record
    ron_evs = [e for e in rec.events if e["t"] == "ron"]
    assert any(e["seat"] == 0 and e.get("robbery") for e in ron_evs), "人类应抢杠胡"
    assert s.is_over()


def test_robbery_pause_and_pass():
    s = PracticeSession(["strong", "strong", "strong"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    _setup_robbery(s, tiles.code_to_index("2m"))
    assert s.pending.kind == "robbery"
    s.submit(Action("pass"))  # 不抢 -> 杠成立 + 杠尾摸 + 流局
    rec = s._record
    kan_evs = [e for e in rec.events if e["t"] == "kan"]
    assert any(e["kind"] == "shouminkan" for e in kan_evs), "不抢则补杠成立"
    assert 0 not in s.state.winners  # 人类未胡


# ===== 终局牌谱 replay 一致 + 张数守恒 =====

def test_terminal_record_replay_and_conservation():
    for seed in range(15):
        s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=seed)
        play_to_end(s)
        assert s.is_over()
        s._finalize()
        rec = s._record
        fs = replay(rec)
        # 赢家一致
        rw = [w["seat"] for w in rec.result["winners"]]
        assert fs.winners == rw, f"seed {seed}: 回放赢家不一致"
        # 张数守恒 = 108
        total = 0
        for seat in range(4):
            total += len(fs.hands[seat])
            total += sum(m.tile_count for m in fs.melds[seat])
            total += len(fs.discards[seat])
        nd = sum(1 for e in rec.events if e["t"] == "draw")
        nk = sum(1 for e in rec.events if e["t"] == "kan_draw")
        assert total + (56 - nd - nk) == 108, f"seed {seed}: 张数不守恒"


# ===== 提示开关 =====

def test_hints_off_advise_null():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, seed=0)
    _fast_forward_to_main_loop(s)
    p = s.current_prompt()
    assert p["phase"] == "turn_action"
    assert p["advise"] is None  # 纯实战不调 LLM
    assert p["hint"] is not None  # Phase 3 硬算始终有


def test_hints_on_advise_null_without_config():
    """开提示但无 LLM 配置:advise=null(hints_on 仍 true,但 advice 不可用)。"""
    s = PracticeSession(["mid", "mid", "mid"], hints_on=True, llm_config=None, seed=0)
    _fast_forward_to_main_loop(s)
    p = s.current_prompt()
    assert p["phase"] == "turn_action"
    # advise 字段为 AdviseResult.to_dict()(analysis 在,advice=null,error 说明未配置)
    assert p["advise"] is not None
    assert p["advise"]["advice"] is None
    assert p["advise"]["hints_on"] is True


def test_advise_on_demand_without_config():
    s = PracticeSession(["mid", "mid", "mid"], hints_on=False, llm_config=None, seed=0)
    _fast_forward_to_main_loop(s)
    res = s.advise_on_demand()
    assert res["advice"] is None  # 无配置 -> advice=null
    assert res["analysis"] is not None  # 硬算始终有


# ===== SessionStore:内存存储 + idle TTL =====

def test_session_store_create_get_delete():
    from majiang_coach.practice import SessionStore
    store = SessionStore()
    sid = store.create(ai_strengths=["mid", "mid", "mid"], seed=0)
    assert store.get(sid) is not None
    assert store.get("nope") is None
    store.delete(sid)
    assert store.get(sid) is None
    assert len(store) == 0


def test_session_store_sweep_idle():
    import time
    from majiang_coach.practice import SessionStore
    store = SessionStore()
    sid = store.create(ai_strengths=["mid", "mid", "mid"], seed=0)
    assert len(store) == 1
    # 手动老化:last_access 减到 ttl 之前
    with store._lock:
        session, _ = store._sessions[sid]
        store._sessions[sid] = (session, time.time() - 100)
    removed = store.sweep_idle(ttl=50)
    assert removed == 1
    assert store.get(sid) is None
    # 未过期的保留
    sid2 = store.create(ai_strengths=["mid", "mid", "mid"], seed=1)
    assert store.sweep_idle(ttl=1800) == 0
    assert store.get(sid2) is not None
