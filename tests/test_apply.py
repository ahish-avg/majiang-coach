"""tests for engine/apply.py: 抽取后 Game 行为回归(Phase 2 牌谱逐事件一致)。

验证 apply_* 纯函数化 + Game 委托后,同种子 Game.run() 产出与抽取前完全相同
(逐事件一致),且 apply_* 直接调用与 Game._handle_* 等价。
"""

from __future__ import annotations

import json
import os

import pytest

from majiang_coach.engine.action import (
    discard, pon, ankan, daiminkan, shouminkan, tsumo, ron,
)
from majiang_coach.engine.apply import (
    apply_discard, apply_pon, apply_ankan, apply_daiminkan,
    apply_tsumo, apply_ron, apply_shouminkan,
)
from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.record import GameRecord
from majiang_coach.engine.state import GameState
from majiang_coach.hand import Hand

_S5 = 13  # 5s
_S9 = 17  # 9s


_BASELINE_PATH = os.path.join(os.path.dirname(__file__), "_phase5_baseline.json")


@pytest.mark.parametrize("seed", range(60))
def test_apply_extraction_records_identical(seed):
    """同种子 Game.run() 牌谱逐事件与抽取前 baseline 完全一致。"""
    with open(_BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)
    expected = baseline[str(seed)]

    actors = [RandomActor(seed * 4 + i) for i in range(4)]
    record = Game(actors, seed).run()

    actual = record.to_dict()
    assert actual == expected, f"seed {seed}: 抽取后牌谱与 baseline 不一致"


def test_apply_direct_equals_handle_methods():
    """apply_* 直接调用与 Game._handle_* 产出相同事件/状态。"""
    # discard
    s1 = GameState.new(0); s1.hands[0] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    s1.lack = [2, 2, 2, 2]
    r1 = GameRecord(); g = Game([RandomActor(i) for i in range(4)], 0)
    g._handle_discard(s1, r1, 0, 4)

    s2 = GameState.new(0); s2.hands[0] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    s2.lack = [2, 2, 2, 2]
    r2 = GameRecord()
    apply_discard(s2, r2, 0, 4)
    assert r1.events == r2.events
    assert s1.hands[0] == s2.hands[0]
    assert s1.discards[0] == s2.discards[0]

    # pon
    s1 = GameState.new(0); s1.hands[1] = Hand.from_codes(["9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    g._handle_pon(s1, r1, 1, 0, _S9)
    s2 = GameState.new(0); s2.hands[1] = Hand.from_codes(["9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    apply_pon(s2, r2, 1, 0, _S9)
    assert r1.events == r2.events and s1.melds[1] == s2.melds[1]

    # ankan
    s1 = GameState.new(0); s1.hands[0] = Hand.from_codes(["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    g._handle_ankan(s1, r1, 0, _S5)
    s2 = GameState.new(0); s2.hands[0] = Hand.from_codes(["5s5s5s5s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    apply_ankan(s2, r2, 0, _S5)
    assert r1.events == r2.events and s1.melds[0] == s2.melds[0]

    # daiminkan
    s1 = GameState.new(0); s1.hands[1] = Hand.from_codes(["9s9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    g._handle_daiminkan(s1, r1, 1, 0, _S9)
    s2 = GameState.new(0); s2.hands[1] = Hand.from_codes(["9s9s9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s"])
    s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    apply_daiminkan(s2, r2, 1, 0, _S9)
    assert r1.events == r2.events and s1.melds[1] == s2.melds[1]

    # tsumo
    s1 = GameState.new(0); s1.hands[0] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    g._handle_tsumo(s1, r1, 0, _S5)
    s2 = GameState.new(0); s2.hands[0] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s"])
    s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    apply_tsumo(s2, r2, 0, _S5)
    assert r1.events == r2.events and s1.winners == s2.winners and s1.win_details == s2.win_details

    # ron
    s1 = GameState.new(0); s1.hands[1] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    g._handle_ron(s1, r1, 1, 0, _S5, robbery=False)
    s2 = GameState.new(0); s2.hands[1] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    apply_ron(s2, r2, 1, 0, _S5, robbery=False)
    assert r1.events == r2.events and s1.win_details == s2.win_details

    # shouminkan (no robbery)
    s1 = GameState.new(0); s1.hands[0] = Hand.from_codes(["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    s1.melds[0] = [Meld("pon", _S9, 1)]; s1.lack = [2, 2, 2, 2]; r1 = GameRecord()
    robbed1 = g._handle_shouminkan(s1, r1, 0, _S9)
    s2 = GameState.new(0); s2.hands[0] = Hand.from_codes(["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
    s2.melds[0] = [Meld("pon", _S9, 1)]; s2.lack = [2, 2, 2, 2]; r2 = GameRecord()
    robbed2 = apply_shouminkan(s2, r2, 0, _S9)
    assert robbed1 is robbed2 and r1.events == r2.events and s1.melds[0] == s2.melds[0]


def test_apply_shouminkan_robbery_consistency():
    """补杠被抢:apply_shouminkan 与 Game._handle_shouminkan 一致(ron 抢杠)。"""
    g = Game([RandomActor(i) for i in range(4)], 0)

    def mk():
        s = GameState.new(0)
        # 座0 已碰9s,暗手含9s;座1 听9s可抢
        s.hands[0] = Hand.from_codes(["9s", "1m2m3m", "4m5m6m", "7m8m9m", "1s2s"])
        s.melds[0] = [Meld("pon", _S9, 2)]
        s.hands[1] = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "9s"])
        s.active = [True, True, False, False]  # 座2,3 已胡
        s.lack = [2, 2, 2, 2]
        return s

    s1, r1 = mk(), GameRecord()
    robbed1 = g._handle_shouminkan(s1, r1, 0, _S9)
    s2, r2 = mk(), GameRecord()
    robbed2 = apply_shouminkan(s2, r2, 0, _S9)

    assert robbed1 is True and robbed2 is True
    assert r1.events == r2.events
    assert s1.winners == s2.winners
    assert s1.win_details == s2.win_details
