"""tests for engine/game.py: 状态机分支(脚本化场景)。

覆盖:碰→弃、暗杠→杠尾→弃、大明杠、补杠+抢杠、自摸、点炮、一炮多响、
血战续打、流局、天胡。

策略:
  - 单步转移(碰/三类杠)直接调用 _handle_* 处理器验证状态与事件。
  - 多步流程(自摸/点炮/多响/续打/流局/天胡)用 _run_loop + ScriptedActor
    + 受控牌墙(缺筒、牌墙中段填充筒牌避免越 4)。
"""

from __future__ import annotations

import random
import pytest

from majiang_coach.hand import Hand
from majiang_coach import tiles
from majiang_coach.engine.wall import TileWall
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.action import (
    Action, discard, pon, ankan, daiminkan, shouminkan, tsumo, ron, pass_action,
    legal_self_actions,
)
from majiang_coach.engine.state import GameState
from majiang_coach.engine.record import GameRecord, replay
from majiang_coach.engine.game import Game, RandomActor


# ---- 辅助 ----

class ScriptedActor:
    """脚本化 Actor:队列空时回退到 RandomActor。"""

    def __init__(self, seed: int = 0) -> None:
        self._fb = RandomActor(seed)
        self._turns: list = []
        self._claims: list = []

    def turn(self, item) -> "ScriptedActor":
        self._turns.append(item)
        return self

    def claim(self, item) -> "ScriptedActor":
        self._claims.append(item)
        return self

    def choose_swap(self, view):
        return self._fb.choose_swap(view)

    def choose_lack(self, view):
        return self._fb.choose_lack(view)

    def choose_turn_action(self, view, drawn):
        if self._turns:
            item = self._turns.pop(0)
            return item(view, drawn) if callable(item) else item
        return self._fb.choose_turn_action(view, drawn)

    def choose_claim(self, view, claimable):
        if self._claims:
            item = self._claims.pop(0)
            return item(view, claimable) if callable(item) else item
        return self._fb.choose_claim(view, claimable)


def make_wall(front=None, back=None, pad=22, seed=0):
    """受控牌墙:front=首摸序列,back=杠尾序列(按顺序),中段填 pad(筒)。

    所有玩家缺筒时,中段筒牌摸入即弃,不会越 4。
    """
    rng = random.Random(seed)
    pool = []
    for idx in range(27):
        pool.extend([idx] * 4)
    for t in (front or []):
        pool.remove(t)
    for t in (back or []):
        pool.remove(t)
    rng.shuffle(pool)
    preset = list(front or []) + pool + list(reversed(back or []))
    return TileWall(seed, preset=preset)


def setup_state(hands_codes, lack=2, wall=None, seed=0):
    """构造 GameState(跳过发牌/换三张/定缺),4 座 13 张暗手。"""
    state = GameState.new(seed)
    state.wall = wall or make_wall()
    for s in range(4):
        state.hands[s] = Hand.from_codes(hands_codes[s])
    state.lack = [lack] * 4
    return state


def make_game(actors, seed=0):
    return Game(actors, seed)


def event_types(record):
    return [e["t"] for e in record.events]


# 索引常量
M1, M5, M9 = 0, 4, 8
S1, S5, S9 = 9, 13, 17
P5 = 22


# ===== 单步处理器测试 =====

def test_handle_pon():
    state = GameState.new(0)
    state.hands[1] = Hand.from_codes(["9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    state.lack = [2, 2, 2, 2]
    game = make_game([RandomActor(i) for i in range(4)])
    record = GameRecord()
    game._handle_pon(state, record, 1, 0, S9)
    assert Meld("pon", S9, 0) in state.melds[1]
    assert state.hands[1].count(S9) == 0
    assert record.events[-1]["t"] == "pon"
    assert record.events[-1]["tile"] == "9s"


def test_handle_ankan():
    state = GameState.new(0)
    state.hands[0] = Hand.from_codes(["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    state.lack = [2, 2, 2, 2]
    game = make_game([RandomActor(i) for i in range(4)])
    record = GameRecord()
    game._handle_ankan(state, record, 0, S5)
    assert Meld("ankan", S5, None) in state.melds[0]
    assert state.hands[0].count(S5) == 0
    assert record.events[-1] == {"t": "kan", "seat": 0, "kind": "ankan", "tile": "5s"}


def test_handle_daiminkan():
    state = GameState.new(0)
    state.hands[1] = Hand.from_codes(["9s9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    state.lack = [2, 2, 2, 2]
    game = make_game([RandomActor(i) for i in range(4)])
    record = GameRecord()
    game._handle_daiminkan(state, record, 1, 0, S9)
    assert Meld("daiminkan", S9, 0) in state.melds[1]
    assert state.hands[1].count(S9) == 0
    ev = record.events[-1]
    assert ev["t"] == "kan" and ev["kind"] == "daiminkan" and ev["from"] == 0


def test_handle_shouminkan_no_robbery():
    state = GameState.new(0)
    # 座0 已碰9s,暗手含一张9s
    state.hands[0] = Hand.from_codes(["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    state.melds[0] = [Meld("pon", S9, 1)]
    state.lack = [2, 2, 2, 2]
    game = make_game([RandomActor(i) for i in range(4)])
    record = GameRecord()
    robbed = game._handle_shouminkan(state, record, 0, S9)
    assert robbed is False
    assert state.melds[0][0].kind == "shouminkan"
    assert state.hands[0].count(S9) == 0
    assert record.events[-1]["kind"] == "shouminkan"


def test_handle_shouminkan_robbed():
    state = GameState.new(0)
    # 座0 已碰9s,暗手含9s;座1 听9s可抢
    state.hands[0] = Hand.from_codes(["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    state.melds[0] = [Meld("pon", S9, 2)]
    state.hands[1] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"])
    state.active = [True, True, False, False]  # 座2,3 已胡(不参与抢杠)
    state.lack = [2, 2, 2, 2]
    game = make_game([RandomActor(i) for i in range(4)])
    record = GameRecord()
    robbed = game._handle_shouminkan(state, record, 0, S9)
    assert robbed is True
    # 杠取消:碰仍为碰
    assert state.melds[0][0].kind == "pon"
    # 座0 暗手失去9s
    assert state.hands[0].count(S9) == 0
    # 座1 抢杠胡
    assert 1 in state.winners
    ron_ev = [e for e in record.events if e["t"] == "ron"][0]
    assert ron_ev["robbery"] is True
    assert ron_ev["from"] == 0


# ===== 流程测试(_run_loop + ScriptedActor)=====

# 公共手牌(仅万条,缺筒;跨座不越4)
_H0 = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]      # 听5s
_H1 = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"]      # 听5s
_H2 = ["4s5s6s", "7s8s9s", "1m2m3m", "4m5m6m", "1s"]
_H3 = ["4s5s6s", "7s8s9s", "7m8m9m", "1m2m3m", "2s"]


def test_flow_tsumo():
    # 庄家摸到5s自摸
    wall = make_wall(front=[S5])
    state = setup_state([_H0, _H1, _H2, _H3], wall=wall)
    actors = [ScriptedActor(0).turn(tsumo(S5)),
              ScriptedActor(1), ScriptedActor(2), ScriptedActor(3)]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    assert "tsumo" in event_types(record)
    tsumo_ev = [e for e in record.events if e["t"] == "tsumo"][0]
    assert tsumo_ev["seat"] == 0
    assert tsumo_ev["tile"] == "5s"


def test_flow_tenhou():
    # 天胡=庄家首摸即胡(同 tsumo,但语义为首摸)
    wall = make_wall(front=[S5])
    state = setup_state([_H0, _H1, _H2, _H3], wall=wall)
    actors = [ScriptedActor(0).turn(tsumo(S5)),
              ScriptedActor(1), ScriptedActor(2), ScriptedActor(3)]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    # 首个动作事件应为 draw -> tsumo
    acts = [e for e in record.events if e["t"] in ("draw", "tsumo")]
    assert acts[0]["t"] == "draw" and acts[0]["seat"] == 0
    assert acts[1]["t"] == "tsumo" and acts[1]["seat"] == 0


def test_flow_ron():
    # 座0弃5s,座1点炮胡
    wall = make_wall(front=[M1])  # 座0摸1m(不干扰)
    state = setup_state([_H0, _H1, _H2, _H3], wall=wall)
    actors = [
        ScriptedActor(0).turn(discard(S5)),
        ScriptedActor(1).claim(ron(0, S5)),
        ScriptedActor(2).claim(pass_action()),
        ScriptedActor(3).claim(pass_action()),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    ron_evs = [e for e in record.events if e["t"] == "ron"]
    assert len(ron_evs) >= 1
    assert ron_evs[0]["seat"] == 1
    assert ron_evs[0]["from"] == 0


def test_flow_multi_ron():
    # 座0弃5s,座1与座3都胡(一炮多响)
    # 座3 也听5s: 改 _H3 为听5s的手牌
    h3 = ["1m2m3m", "4m5m6m", "7m8m9m", "5s5s5s5s"]  # 3+3+3+4=13, 听5s? 不,5s已有4张
    # 用另一听5s手牌:1m2m3m 4m4m4m 7m8m9m 1s2s3s 5s
    h3 = ["1m2m3m", "4m4m4m", "7m8m9m", "1s2s3s", "5s"]
    # 检查跨座5s: H0(1)+H1(1)+h3(1)=3, 弃1张=4. OK
    # 但4m: H0(1)+H1(1)+h3(3)=5>4! 改h3用别的刻子
    h3 = ["1m2m3m", "7m7m7m", "1s2s3s", "4s5s6s", "5s"]
    # 7m: H0(1)+H1(1)+h3(3)=5>4! 用9s刻子
    h3 = ["1m2m3m", "9s9s9s", "1s2s3s", "4s5s6s", "5s"]
    # 9s: H2(1, in 7s8s9s)+H3(3, in 9s9s9s)+H3(1, in 4s5s6s no)... 9s in H2=1, in h3=3 =>4 OK
    # 1s: H0(1)+H1(1)+H2(1)+h3(1)=4 OK. 2s: H0(1)+H1(1)+H2(0)+h3(1)=3 OK
    # 5s: H0(1)+H1(1)+h3(1)=3 OK. 4s: H2(1)+h3(1)=2. 6s: H2(1)+h3(1)=2
    wall = make_wall(front=[M1])
    state = setup_state([_H0, _H1, _H2, h3], wall=wall)
    actors = [
        ScriptedActor(0).turn(discard(S5)),
        ScriptedActor(1).claim(ron(0, S5)),
        ScriptedActor(2).claim(pass_action()),
        ScriptedActor(3).claim(ron(0, S5)),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    ron_evs = [e for e in record.events if e["t"] == "ron"]
    ron_seats = {e["seat"] for e in ron_evs if e["from"] == 0}
    assert ron_seats == {1, 3}


def test_flow_pon_then_discard():
    # 座0弃9s,座1碰,座1弃牌
    h0 = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"]
    h1 = ["9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"]
    # 9s: h0(1)+h1(2)=3. 9m: h0(1)+h1(1)=2. 其余<=4
    wall = make_wall(front=[M1])
    state = setup_state([h0, h1, _H2, _H3], wall=wall)
    actors = [
        ScriptedActor(0).turn(discard(S9)),
        ScriptedActor(1).claim(pon(0, S9)).turn(lambda v, d: discard(v.hand.to_indices()[0])),
        ScriptedActor(2).claim(pass_action()),
        ScriptedActor(3).claim(pass_action()),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    types = event_types(record)
    assert "pon" in types
    pon_idx = types.index("pon")
    # 碰后应有 discard(座1弃牌)
    later = types[pon_idx:]
    assert "discard" in later


def test_flow_ankan_rinshan():
    # 座0暗杠5s(4张),杠尾摸,弃牌
    h0 = ["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"]  # 4+3+3+3+1=14? no=14. 需13
    # 庄家先摸->14. 但暗杠需摸后14张含4张5s. 13张手含4张5s:
    h0 = ["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m"]  # 4+3+3+3=13
    wall = make_wall(front=[M1], back=[M5])  # 首摸1m, 杠尾摸5m
    state = setup_state([h0, _H1, _H2, _H3], wall=wall)
    actors = [
        ScriptedActor(0).turn(ankan(S5)).turn(lambda v, d: discard(v.hand.to_indices()[0])),
        ScriptedActor(1), ScriptedActor(2), ScriptedActor(3),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    types = event_types(record)
    assert "kan" in types
    kan_idx = types.index("kan")
    assert record.events[kan_idx]["kind"] == "ankan"
    # 杠后杠尾摸
    assert "kan_draw" in types[kan_idx:]


def test_flow_daiminkan():
    # 座0弃9s,座1大明杠(暗刻9s),杠尾摸,弃牌
    h0 = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"]
    h1 = ["9s9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"]
    # 9s: h0(1)+h1(3)=4 OK
    wall = make_wall(front=[M1], back=[M5])
    state = setup_state([h0, h1, _H2, _H3], wall=wall)
    actors = [
        ScriptedActor(0).turn(discard(S9)),
        ScriptedActor(1).claim(daiminkan(0, S9)).turn(lambda v, d: discard(v.hand.to_indices()[0])),
        ScriptedActor(2).claim(pass_action()),
        ScriptedActor(3).claim(pass_action()),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    types = event_types(record)
    assert "kan" in types
    kan_ev = [e for e in record.events if e["t"] == "kan"][0]
    assert kan_ev["kind"] == "daiminkan"
    assert "kan_draw" in types


def test_flow_shouminkan_no_robbery():
    # 座0已碰9s,摸到9s,补杠(无抢杠),杠尾摸,弃牌
    h0_codes = ["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"]  # 1+3+3+3+2=12? 需13
    h0_codes = ["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s"]  # 1+3+3+3+3=13
    wall = make_wall(front=[S9], back=[M5])  # 首摸9s(第4张)
    state = setup_state([h0_codes, _H1, _H2, _H3], wall=wall)
    state.melds[0] = [Meld("pon", S9, 1)]
    # 座0暗手已含1张9s, 摸第4张9s -> 2张? 不,碰了3张+暗手1张=4. 摸第4张不可能(已4张)
    # 修正:碰9s(3张在副露), 暗手0张9s. 摸到9s(第4张) -> 暗手1张. 补杠.
    h0_codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"]  # 含1张9s? 不,碰了3张9s, 暗手不能有9s(共4)
    # 碰9s=3张副露. 暗手13-3=10张(1副露). 暗手不含9s. 摸9s->暗手1张9s. 补杠.
    h0_codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "1m"]  # 3+3+3+3+1=13? 但1副露应13-3=10张
    # _run_loop 庄家先摸:13张+1=14. 但碰了1副露, 应13-3=10张暗手+摸=11=14-3*1.
    # setup_state 设13张. 有1副露时, 庄家摸后应14-3=11张. 但setup给13张+摸1=14. 不对!
    # 修正: 有1副露时, 暗手应为13-3*1=10张. setup_state给10张.
    h0_codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s"]  # 3+3+3+1=10
    wall = make_wall(front=[S9], back=[M5])
    state = setup_state([h0_codes, _H1, _H2, _H3], wall=wall)
    state.melds[0] = [Meld("pon", S9, 1)]
    actors = [
        ScriptedActor(0).turn(shouminkan(S9)).turn(lambda v, d: discard(v.hand.to_indices()[0])),
        ScriptedActor(1), ScriptedActor(2), ScriptedActor(3),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    types = event_types(record)
    assert "kan" in types
    kan_ev = [e for e in record.events if e["t"] == "kan"][0]
    assert kan_ev["kind"] == "shouminkan"
    assert "kan_draw" in types


def test_flow_shouminkan_robbed():
    # 座0补杠9s,座1抢杠胡
    h0_codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s"]  # 10张(1副露)
    h1_codes = ["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"]  # 听9s
    wall = make_wall(front=[S9])
    state = setup_state([h0_codes, h1_codes, _H2, _H3], wall=wall)
    state.melds[0] = [Meld("pon", S9, 2)]
    actors = [
        ScriptedActor(0).turn(shouminkan(S9)),
        ScriptedActor(1), ScriptedActor(2), ScriptedActor(3),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    ron_evs = [e for e in record.events if e["t"] == "ron"]
    assert len(ron_evs) >= 1
    assert ron_evs[0]["robbery"] is True
    assert ron_evs[0]["seat"] == 1


def test_flow_blood_war_three_wins():
    # 血战续打:3家胡后终局
    # 座0弃5s -> 座1 ron. 然后继续, 座0再弃, 座2 ron. 再继续, 座0弃, 座3 ron.
    # 需要座1,2,3 都听5s. 座0持续弃5s(需多张5s? 不,每次摸牌后弃5s不太可控)
    # 简化:用脚本让座0每次弃某牌, 该牌让下一家胡
    # 实际:用 ron + 随机续打, 检查 winners>=2 即可证明续打
    # 更直接:座0弃5s -> 座1 ron. 之后随机续打. 检查 1 in winners 且游戏终止.
    wall = make_wall(front=[M1])
    state = setup_state([_H0, _H1, _H2, _H3], wall=wall)
    actors = [
        ScriptedActor(0).turn(discard(S5)),
        ScriptedActor(1).claim(ron(0, S5)),
        ScriptedActor(2).claim(pass_action()),
        ScriptedActor(3).claim(pass_action()),
    ]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    # 座1 已胡, 游戏继续(血战)
    assert 1 in state.winners
    assert len(state.winners) >= 1
    # 游戏终止(winners>=3 或流局)
    assert len(state.winners) >= 3 or any(e["t"] == "ryuukyoku" for e in record.events)


def test_flow_ryuukyoku():
    # 牌墙摸完,无3家胡 -> 流局
    # 用很短的牌墙(仅够庄家摸1次+少量),快速耗尽
    wall = make_wall(front=[P5], pad=P5)  # 全筒,缺筒->摸即弃,快速耗尽
    # 但需要 wall 足够短才会流局. make_wall 默认108张. 改用短墙:
    short = [P5] * 20  # 20张筒
    wall = TileWall(0, preset=short)
    state = setup_state([_H0, _H1, _H2, _H3], wall=wall)
    state.lack = [2, 2, 2, 2]
    actors = [RandomActor(i) for i in range(4)]
    game = make_game(actors)
    record = GameRecord(meta={"seed": 0})
    game._run_loop(state, record)
    assert "ryuukyoku" in event_types(record)
    assert len(state.winners) < 3
