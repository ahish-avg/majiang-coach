"""tests for engine/record.py: serialization + replay()."""

from __future__ import annotations

import json
import pytest

from majiang_coach.hand import Hand
from majiang_coach.engine.melds import Meld
from majiang_coach.engine.record import (
    GameRecord, FinalState, replay, make_meld_dict, meld_from_dict,
)
from majiang_coach.engine.game import Game, RandomActor


def test_make_meld_dict_and_back():
    m = Meld("pon", 13, 2)
    d = make_meld_dict(m)
    assert d == {"kind": "pon", "tile": "5s", "from": 2}
    assert meld_from_dict(d) == m

    m2 = Meld("ankan", 4, None)
    d2 = make_meld_dict(m2)
    assert d2 == {"kind": "ankan", "tile": "5m", "from": None}
    assert meld_from_dict(d2) == m2


def test_record_to_dict_from_dict_roundtrip():
    r = GameRecord(meta={"seed": 1, "version": 1}, events=[{"t": "ryuukyoku"}], result={"drawn": True})
    d = r.to_dict()
    assert d["meta"]["seed"] == 1
    assert d["events"] == [{"t": "ryuukyoku"}]
    r2 = GameRecord.from_dict(d)
    assert r2.meta == r.meta
    assert r2.events == r.events
    assert r2.result == r.result


def test_record_json_serializable():
    r = GameRecord(meta={"seed": 1}, events=[{"t": "deal", "seat": 0, "tiles": ["1m", "2m"]}],
                   result={"winners": [], "losers": [], "drawn": True})
    s = json.dumps(r.to_dict())
    r2 = GameRecord.from_dict(json.loads(s))
    assert r2.events == r.events


def test_replay_basic_deal_lack():
    record = GameRecord(
        meta={"seed": 0},
        events=[
            {"t": "deal", "seat": 0, "tiles": ["1m", "2m", "3m"]},
            {"t": "deal", "seat": 1, "tiles": ["4m", "5m", "6m"]},
            {"t": "lack", "seat": 0, "suit": 2},
        ],
    )
    fs = replay(record)
    assert len(fs.hands[0]) == 3
    assert len(fs.hands[1]) == 3
    assert fs.lack[0] == 2
    assert fs.winners == []
    assert fs.drawn is False


def test_replay_draw_discard():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["1m", "2m", "3m", "4m", "5m"]},
        {"t": "draw", "seat": 0, "tile": "6m", "src": "wall"},
        {"t": "discard", "seat": 0, "tile": "6m"},
    ])
    fs = replay(record)
    assert fs.hands[0] == [0, 1, 2, 3, 4]  # 1m-5m
    assert fs.discards[0] == [5]  # 6m


def test_replay_pon():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["5s"]},
        {"t": "deal", "seat": 1, "tiles": ["5s", "5s", "1m", "2m", "3m"]},
        {"t": "discard", "seat": 0, "tile": "5s"},
        {"t": "pon", "seat": 1, "from": 0, "tile": "5s"},
    ])
    fs = replay(record)
    # 座1: 暗手移除2张5s, 加碰副露
    assert fs.hands[1] == [0, 1, 2]  # 1m2m3m
    assert len(fs.melds[1]) == 1
    assert fs.melds[1][0].kind == "pon"
    # 弃牌堆: 座0的5s被碰走
    assert fs.discards[0] == []


def test_replay_ankan():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["5s", "5s", "5s", "5s", "1m"]},
        {"t": "kan", "seat": 0, "kind": "ankan", "tile": "5s"},
        {"t": "kan_draw", "seat": 0, "tile": "2m", "src": "rinshan"},
    ])
    fs = replay(record)
    assert fs.hands[0] == [0, 1]  # 1m, 2m
    assert fs.melds[0][0] == Meld("ankan", 13, None)


def test_replay_shouminkan():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["5s", "1m", "2m", "3m"]},
        {"t": "deal", "seat": 1, "tiles": ["5s", "5s", "7m", "8m", "9m"]},
        {"t": "discard", "seat": 1, "tile": "5s"},
        {"t": "pon", "seat": 0, "from": 1, "tile": "5s"},
        {"t": "kan", "seat": 0, "kind": "shouminkan", "tile": "5s"},
        {"t": "kan_draw", "seat": 0, "tile": "4m", "src": "rinshan"},
    ])
    fs = replay(record)
    # 碰(3张)+补杠(加1张)= shouminkan
    assert fs.melds[0][0].kind == "shouminkan"
    assert fs.hands[0] == [0, 1, 2, 3]  # 1m2m3m4m


def test_replay_tsumo():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["1m", "2m", "3m", "4m", "5m", "6m",
                                            "7m", "8m", "9m", "1s", "2s", "3s", "5s"]},
        {"t": "draw", "seat": 0, "tile": "5s", "src": "wall"},
        {"t": "tsumo", "seat": 0, "tile": "5s", "hand": ["1m", "2m", "3m", "4m", "5m", "6m",
                                                          "7m", "8m", "9m", "1s", "2s", "3s", "5s", "5s"],
         "melds": [], "lack": 2},
    ])
    fs = replay(record)
    assert fs.winners == [0]
    assert fs.win_details[0]["by"] == "tsumo"
    assert len(fs.hands[0]) == 14


def test_replay_ron():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["5s"]},
        {"t": "deal", "seat": 1, "tiles": ["1m", "2m", "3m", "4m", "5m", "6m",
                                            "7m", "8m", "9m", "1s", "2s", "3s", "5s"]},
        {"t": "discard", "seat": 0, "tile": "5s"},
        {"t": "ron", "seat": 1, "from": 0, "tile": "5s", "robbery": False,
         "hand": ["5s", "5s"], "melds": [], "lack": 2},
    ])
    fs = replay(record)
    assert fs.winners == [1]
    assert fs.discards[0] == []  # 弃牌被胡走
    assert 13 in fs.hands[1]  # 含胡牌5s


def test_replay_robbery_ron():
    record = GameRecord(events=[
        {"t": "deal", "seat": 0, "tiles": ["1m", "2m", "3m"]},
        {"t": "deal", "seat": 1, "tiles": ["1m", "2m", "3m", "4m", "5m", "6m",
                                            "7m", "8m", "9m", "1s", "2s", "3s", "5s"]},
        {"t": "draw", "seat": 0, "tile": "5s", "src": "wall"},
        {"t": "ron", "seat": 1, "from": 0, "tile": "5s", "robbery": True,
         "hand": [], "melds": [], "lack": 2},
    ])
    fs = replay(record)
    assert fs.winners == [1]
    # 抢杠:5s从座0暗手移除(非弃牌堆);座0仅剩1m2m3m
    assert fs.hands[0] == [0, 1, 2]
    assert fs.discards[0] == []


def test_replay_random_game_consistency():
    """随机局:replay 复现终局与 record.result 一致。"""
    for seed in range(20):
        g = Game([RandomActor(seed * 4 + i) for i in range(4)], seed)
        r = g.run()
        fs = replay(r)
        # 赢家一致
        record_winners = [w["seat"] for w in r.result["winners"]]
        assert fs.winners == record_winners, f"seed {seed}"
        # 赢家暗手张数 = 14 - 3*melds
        for w in r.result["winners"]:
            seat = w["seat"]
            meld_count = len(w["melds"])
            expected = 14 - 3 * meld_count
            assert len(fs.hands[seat]) == expected, f"seed {seed} seat {seat}"
