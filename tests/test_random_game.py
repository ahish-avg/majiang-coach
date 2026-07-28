"""tests for engine: 随机局集成(N 局种子跑通)。

验证:每局终止(3 胡或流局)、全程张数守恒=108、无非法动作、牌谱可回放复现。
"""

from __future__ import annotations

import json
import pytest

from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.engine.record import replay
from majiang_coach import tiles

N_GAMES = 200


def _count_events(record, t):
    return sum(1 for e in record.events if e["t"] == t)


def _tile_conservation(record, fs):
    """验证张数守恒:暗手+副露+弃牌+牌墙余 = 108。

    牌墙余 = 56 - 首摸次数 - 杠尾摸次数(发牌52后余56)。
    """
    total = 0
    for s in range(4):
        total += len(fs.hands[s])
        total += sum(m.tile_count for m in fs.melds[s])
        total += len(fs.discards[s])
    num_draws = _count_events(record, "draw")
    num_kan_draws = _count_events(record, "kan_draw")
    wall_remaining = 56 - num_draws - num_kan_draws
    return total + wall_remaining


@pytest.mark.parametrize("seed", range(N_GAMES))
def test_random_game_terminates_and_conserved(seed):
    actors = [RandomActor(seed * 4 + i) for i in range(4)]
    game = Game(actors, seed)
    record = game.run()

    # 1. 终止:3 胡或流局
    n_winners = len(record.result["winners"])
    assert n_winners >= 3 or record.result["drawn"] is True, f"seed {seed} 未终止"

    # 2. 张数守恒 = 108
    fs = replay(record)
    total = _tile_conservation(record, fs)
    assert total == 108, f"seed {seed} 张数={total}≠108"

    # 3. 无非法动作(Game 内部已校验,到这里即通过)

    # 4. 回放一致
    record_winners = [w["seat"] for w in record.result["winners"]]
    assert fs.winners == record_winners, f"seed {seed} 回放赢家不一致"


@pytest.mark.parametrize("seed", range(30))
def test_record_json_serializable(seed):
    actors = [RandomActor(seed * 7 + i) for i in range(4)]
    record = Game(actors, seed).run()
    d = record.to_dict()
    s = json.dumps(d)  # 不抛异常即可
    assert "events" in json.loads(s)


def test_blood_war_occurs_in_some_games():
    """至少有一局出现 2+ 胡家(血战续打)。"""
    found_multi = False
    found_kan = False
    found_pon = False
    for seed in range(100):
        actors = [RandomActor(seed * 4 + i) for i in range(4)]
        record = Game(actors, seed).run()
        if len(record.result["winners"]) >= 2:
            found_multi = True
        if _count_events(record, "kan") > 0:
            found_kan = True
        if _count_events(record, "pon") > 0:
            found_pon = True
    # 宽松断言:随机局中应能见到碰/杠/多胡(若100局都没见到则覆盖不足)
    assert found_pon, "100 局无碰事件,覆盖不足"
    assert found_kan, "100 局无杠事件,覆盖不足"
    assert found_multi, "100 局无多胡(血战续打),覆盖不足"


def test_no_lack_tile_claimed():
    """缺门牌不可被碰/杠/胡:检查所有 pon/kan/ron 事件的牌非胡牌者缺门。"""
    for seed in range(50):
        actors = [RandomActor(seed * 4 + i) for i in range(4)]
        record = Game(actors, seed).run()
        lack = record.meta["lack"]
        for e in record.events:
            if e["t"] in ("pon", "kan"):
                seat = e["seat"]
                tile_idx = tiles.code_to_index(e["tile"])
                if lack[seat] is not None:
                    assert tiles.suit_of(tile_idx) != lack[seat], \
                        f"seed {seed}: 座{seat} 申索了缺门牌 {e['tile']}"
            if e["t"] == "ron":
                seat = e["seat"]
                tile_idx = tiles.code_to_index(e["tile"])
                if lack[seat] is not None:
                    assert tiles.suit_of(tile_idx) != lack[seat], \
                        f"seed {seed}: 座{seat} 胡了缺门牌 {e['tile']}"
