"""tests for Phase 7 settle_record():完整结算纯函数。

覆盖:
  - sum(per_seat)==0 不变式(种子局批量)+ to_dict/from_dict 往返 + 确定性。
  - 自摸三家付 / 点炮单付 / 一炮多响双赔 / 已胡者退出后续支付。
  - 杠钱三种(直杠点杠者付、补杠/暗杠在局三家付)+ 抢杠不落地。
  - 流局查叫(理论最大番)+ 查花猪(顶格 ×3、双花猪抵消);3 胡终局不查叫但查花猪。
  - 天胡/地胡/杠上开花/海底(构造小牌谱)。

构造小牌谱时不跑 Game:直接拼事件流(replay 只重放不验胡牌合法性),
暗手用 13 张占位牌 "1p" 等,胜负事实由 tsumo/ron 事件携带的 hand/melds 给出。
"""

from __future__ import annotations

import pytest

from majiang_coach.engine.game import Game, RandomActor
from majiang_coach.scoring import (
    DEFAULT_RULES, FanRules, SettleResult, settle_record,
)


def _record(seed: int):
    return Game([RandomActor(seed * 4 + i) for i in range(4)], seed).run()


def _ev(t, **kw):
    d = {"t": t}
    d.update(kw)
    return d


def _lacks(suits=(2, 0, 0, 0)):
    return [_ev("lack", seat=s, suit=suits[s]) for s in range(4)]


# 13 张占位手牌:万/条两门(缺筒,与 lack=2 一致)、4 对子 + 散张无搭子
# (向听 4,绝不十牌、绝非花猪),每牌全场 ≤4 张。查叫/花猪用例用自定义 deal。
_FILLER = [
    ["1m", "1m", "3m", "3m", "5m", "7m", "9m", "2s", "2s", "4s", "4s", "6s", "8s"],
    ["2m", "2m", "4m", "4m", "6m", "8m", "1s", "1s", "3s", "3s", "5s", "7s", "9s"],
    ["5m", "5m", "7m", "7m", "9m", "2m", "4m", "6s", "6s", "8s", "8s", "2s", "4s"],
    ["6m", "6m", "8m", "8m", "1m", "3m", "5s", "5s", "7s", "7s", "1s", "3s", "9s"],
]


def _mini_deals():
    """4 座 deal,各 13 张占位手牌(每牌全场 ≤4 张)。

    测试只关心事件携带的 hand/melds;占位暗手仅需 replay 张数守恒且可构造 Hand。
    """
    return [_ev("deal", seat=s, tiles=list(_FILLER[s])) for s in range(4)]


def _tsumo_win(seat, tile, hand_codes, melds=None, lack=2):
    return _ev("tsumo", seat=seat, tile=tile, hand=hand_codes, melds=melds or [], lack=lack)


def _ron_win(seat, frm, tile, hand_codes, melds=None, lack=2, robbery=False):
    d = _ev("ron", seat=seat, **{"from": frm}, tile=tile, hand=hand_codes,
            melds=melds or [], lack=lack)
    if robbery:
        d["robbery"] = True
    return d


# ---- 平胡手牌(14 张,缺筒:三副万顺 + 一副条顺 + 5s 将,两门有顺 = 非清一色非对对)----
PINGHU = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
          "1s", "2s", "3s", "5s", "5s"]
# 七对手牌(14 张,缺筒;万 5 对 + 条 2 对,无 4 同张)
QIDUI = ["1m", "1m", "2m", "2m", "3m", "3m", "4m", "4m", "5m", "5m",
         "6s", "6s", "7s", "7s"]


# ---- 批量不变式 / 往返 / 确定性 ----

@pytest.mark.parametrize("seed", list(range(60)))
def test_sum_zero_invariant(seed):
    """种子局批量:四座收付之和恒为 0。"""
    res = settle_record(_record(seed))
    assert sum(res.per_seat.values()) == 0


def test_roundtrip_and_deterministic():
    rec = _record(42)
    r1 = settle_record(rec).to_dict()
    r2 = settle_record(rec).to_dict()
    assert r1 == r2
    assert SettleResult.from_dict(r1).to_dict() == r1


def test_base_score_scales():
    """底分覆盖:金额随底分线性放大,倍数不变。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="2m", src="wall"),
        _ev("discard", seat=0, tile="2m"),
        _ev("draw", seat=1, tile="3m", src="wall"),
        _ev("discard", seat=1, tile="3m"),
        _ev("draw", seat=2, tile="4m", src="wall"),
        _ev("discard", seat=2, tile="4m"),
        _ev("draw", seat=3, tile="5m", src="wall"),
        _ev("discard", seat=3, tile="5m"),
        _ev("draw", seat=0, tile="5s", src="wall"),
        _tsumo_win(0, "5s", PINGHU),
    ]
    rec = {"meta": {}, "events": events, "result": None}
    d1 = settle_record(rec).to_dict()
    d5 = settle_record(rec, FanRules(base_score=5)).to_dict()
    assert d1["wins"][0]["amount_each"] == 2  # 平胡+自摸 = 2 倍
    assert d5["wins"][0]["amount_each"] == 10
    assert d1["wins"][0]["fan"]["multiplier"] == d5["wins"][0]["fan"]["multiplier"] == 2


# ---- 胡牌支付 ----

def test_tsumo_three_payers():
    """自摸:在局三家各付。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="2p", src="wall"),
        _ev("discard", seat=0, tile="2p"),
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("discard", seat=1, tile="1m"),
        _ev("draw", seat=2, tile="2m", src="wall"),
        _ev("discard", seat=2, tile="2m"),
        _ev("draw", seat=3, tile="3m", src="wall"),
        _ev("discard", seat=3, tile="3m"),
        _ev("draw", seat=0, tile="5s", src="wall"),
        _tsumo_win(0, "5s", PINGHU),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    w = d["wins"][0]
    assert sorted(w["payer_seats"]) == [1, 2, 3]
    assert w["amount_each"] == 2
    assert d["per_seat"] == {"0": 6, "1": -2, "2": -2, "3": -2}


def test_ron_single_payer():
    """点炮:点炮者一人付。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="2m", src="wall"),
        _ev("discard", seat=0, tile="2m"),
        _ev("draw", seat=1, tile="9m", src="wall"),
        _ev("discard", seat=1, tile="9m"),
        _ron_win(2, 1, "9m", PINGHU),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    w = d["wins"][0]
    assert w["payer_seats"] == [1]
    assert w["amount_each"] == 1  # 平胡点炮 1 倍
    assert d["per_seat"]["2"] == 1 and d["per_seat"]["1"] == -1
    assert d["per_seat"]["0"] == 0 and d["per_seat"]["3"] == 0


def test_double_ron_both_paid():
    """一炮多响:点炮者按各家番数分别赔。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="2m", src="wall"),
        _ev("discard", seat=0, tile="2m"),
        _ev("draw", seat=1, tile="9m", src="wall"),
        _ev("discard", seat=1, tile="9m"),
        _ron_win(2, 1, "9m", PINGHU),            # 平胡 1 倍
        _ron_win(3, 1, "9m", QIDUI, lack=2),     # 七对点炮 4 番 8 倍
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    assert len(d["wins"]) == 2
    assert d["per_seat"]["1"] == -9  # -(1 + 8)
    assert d["per_seat"]["2"] == 1
    assert d["per_seat"]["3"] == 8
    assert d["per_seat"]["0"] == 0


def test_winner_exits_later_payments():
    """已胡者退出后续支付:座 0 自摸后,座 2 自摸只收座 1、座 3。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="5s", src="wall"),
        _tsumo_win(0, "5s", PINGHU),             # 0 胡:1/2/3 各付 2
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("discard", seat=1, tile="1m"),
        _ev("draw", seat=2, tile="7s", src="wall"),
        _tsumo_win(2, "7s", QIDUI, lack=2),      # 2 自摸七对:在局 1/3 各付 8
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    w2 = d["wins"][1]
    assert sorted(w2["payer_seats"]) == [1, 3]
    # 七对(4)+自摸(1)= 5 番封顶 16 倍
    assert w2["amount_each"] == 16
    assert w2["fan"]["multiplier"] == 16
    assert sum(d["per_seat"].values()) == 0


# ---- 杠钱 ----

def test_daiminkan_payer_only():
    """直杠(大明杠):点杠者一人付 1 倍底分。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="1m", src="wall"),
        _ev("discard", seat=0, tile="9s"),
        _ev("kan", seat=2, kind="daiminkan", tile="9s", **{"from": 0}),
        _ev("kan_draw", seat=2, tile="1m", src="rinshan"),
        _ev("discard", seat=2, tile="1m"),
        _ev("ryuukyoku"),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    k = d["kans"][0]
    assert k["payer_seats"] == [0] and k["amount_each"] == 1
    assert d["per_seat"]["2"] == 1 and d["per_seat"]["0"] == -1


def test_ankan_three_active_pay():
    """暗杠:在局三家各付 2 倍。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("kan", seat=1, kind="ankan", tile="9s"),
        _ev("kan_draw", seat=1, tile="1m", src="rinshan"),
        _ev("discard", seat=1, tile="1m"),
        _ev("ryuukyoku"),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    k = d["kans"][0]
    assert sorted(k["payer_seats"]) == [0, 2, 3] and k["amount_each"] == 2
    assert d["per_seat"]["1"] == 6


def test_shouminkan_three_active_pay():
    """补杠:在局三家各付 1 倍。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="9s", src="wall"),
        _ev("discard", seat=0, tile="9s"),
        _ev("pon", seat=3, **{"from": 0}, tile="9s"),
        _ev("discard", seat=3, tile="1p"),
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("discard", seat=1, tile="1m"),
        _ev("draw", seat=2, tile="2m", src="wall"),
        _ev("discard", seat=2, tile="2m"),
        _ev("draw", seat=3, tile="9s", src="wall"),
        _ev("kan", seat=3, kind="shouminkan", tile="9s"),
        _ev("kan_draw", seat=3, tile="3m", src="rinshan"),
        _ev("discard", seat=3, tile="3m"),
        _ev("ryuukyoku"),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    k = d["kans"][0]
    assert k["kind"] == "shouminkan"
    assert sorted(k["payer_seats"]) == [0, 1, 2] and k["amount_each"] == 1


def test_robbery_no_kan_money():
    """抢杠:补杠不落地 -> 无杠钱;抢杠胡番种 +2。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="9s", src="wall"),
        _ev("discard", seat=0, tile="9s"),
        _ev("pon", seat=3, **{"from": 0}, tile="9s"),
        _ev("discard", seat=3, tile="1p"),
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("discard", seat=1, tile="1m"),
        _ev("draw", seat=2, tile="2m", src="wall"),
        _ev("discard", seat=2, tile="2m"),
        _ev("draw", seat=3, tile="9s", src="wall"),
        _ev("kan", seat=3, kind="shouminkan", tile="9s"),
        _ron_win(1, 3, "9s", PINGHU, lack=2, robbery=True),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    assert d["kans"] == []
    names = [i["name"] for i in d["wins"][0]["fan"]["items"]]
    assert "抢杠胡" in names
    assert d["wins"][0]["payer_seats"] == [3]


# ---- 流局查叫 / 查花猪 ----

def test_huazhu_pays_three():
    """流局花猪:赔其余三家(含已胡者)各顶格 16 倍。"""
    # 座 0 已胡;座 1 终局三门(花猪);座 2、3 下叫
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="5s", src="wall"),
        _tsumo_win(0, "5s", PINGHU),
        _ev("draw", seat=1, tile="1m", src="wall"),
        _ev("discard", seat=1, tile="1m"),
        _ev("ryuukyoku"),
    ]
    # 终局暗手:replay 后座 1 暗手 = 13 张 1p 占位(发牌)-1m 打出 +1m 摸入 = 13 张全 1p(一门)
    # 需要构造三门花猪:直接让座 1 占位牌含三门 -> 用自定义 deal
    deals = [
        _ev("deal", seat=0, tiles=PINGHU[:13]),
        _ev("deal", seat=1, tiles=["1m", "2m", "3m", "4m", "1s", "2s", "3s", "1p", "2p", "3p", "4p", "5p", "6p"]),  # 三门花猪
        _ev("deal", seat=2, tiles=list(_FILLER[2])),
        _ev("deal", seat=3, tiles=list(_FILLER[3])),
    ]
    events = deals + _lacks() + [
        _ev("draw", seat=0, tile=PINGHU[13], src="wall"),
        _tsumo_win(0, PINGHU[13], PINGHU),
        _ev("draw", seat=1, tile="2m", src="wall"),
        _ev("discard", seat=1, tile="2m"),
        _ev("ryuukyoku"),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    hz = d["huazhus"]
    assert len(hz) == 3  # 花猪赔三家(含已胡座 0)
    assert all(h["huazhu_seat"] == 1 and h["amount"] == 16 for h in hz)
    payees = {h["payee"] for h in hz}
    assert payees == {0, 2, 3}


def test_double_huazhu_offset():
    """双花猪:互赔抵消,各自只净付非花猪两家。"""
    deals = [
        _ev("deal", seat=s, tiles=list(_FILLER[s])) for s in (0, 3)
    ] + [
        _ev("deal", seat=1, tiles=["1m", "2m", "3m", "4m", "1s", "2s", "3s", "1p", "2p", "3p", "4p", "5p", "6p"]),
        _ev("deal", seat=2, tiles=["5m", "6m", "7m", "8m", "4s", "5s", "6s", "7p", "8p", "9p", "1p", "2p", "3p"]),
    ]
    events = deals + _lacks(suits=(2, 2, 2, 2)) + [
        _ev("draw", seat=0, tile="1m", src="wall"),
        _ev("discard", seat=0, tile="1m"),
        _ev("ryuukyoku"),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    # 座 1 赔 {0,2,3} 各 16;座 2 赔 {0,1,3} 各 16
    assert d["per_seat"]["1"] == -32  # -48 + 16(座 2 赔)
    assert d["per_seat"]["2"] == -32
    assert d["per_seat"]["0"] == 32 and d["per_seat"]["3"] == 32
    assert sum(d["per_seat"].values()) == 0


def test_three_wins_no_tenpai_but_huazhu():
    """3 胡终局:不查叫,但查花猪。"""
    deals = [
        _ev("deal", seat=0, tiles=PINGHU[:13]),
        _ev("deal", seat=1, tiles=["1m", "2m", "3m", "4m", "1s", "2s", "3s", "1p", "2p", "3p", "4p", "5p", "6p"]),  # 花猪
        _ev("deal", seat=2, tiles=QIDUI[:13]),
        _ev("deal", seat=3, tiles=PINGHU[:13]),
    ]
    events = deals + _lacks(suits=(2, 2, 2, 2)) + [
        _ev("draw", seat=0, tile=PINGHU[13], src="wall"),
        _tsumo_win(0, PINGHU[13], PINGHU),
        _ev("draw", seat=1, tile="2m", src="wall"),
        _ev("discard", seat=1, tile="2m"),
        _ev("draw", seat=2, tile=QIDUI[13], src="wall"),
        _tsumo_win(2, QIDUI[13], QIDUI, lack=2),
        _ev("draw", seat=3, tile=PINGHU[13], src="wall"),
        _tsumo_win(3, PINGHU[13], PINGHU),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    assert d["tenpais"] == []          # 3 胡不查叫
    assert len(d["huazhus"]) == 3      # 花猪座 1 赔其余三家
    assert sum(d["per_seat"].values()) == 0


# ---- 天地胡 / 杠上开花 / 海底 ----

def test_tianhu_settlement():
    """天胡:庄家首摸自摸,顶格 16 倍,三家各付。"""
    need = list(PINGHU)
    events = [
        _ev("deal", seat=0, tiles=need[:13]),
        _ev("deal", seat=1, tiles=list(_FILLER[1])),
        _ev("deal", seat=2, tiles=list(_FILLER[2])),
        _ev("deal", seat=3, tiles=list(_FILLER[3])),
    ] + _lacks() + [
        _ev("draw", seat=0, tile=need[13], src="wall"),
        _tsumo_win(0, need[13], need),
    ]
    d = settle_record({"meta": {"dealer": 0}, "events": events}).to_dict()
    names = [i["name"] for i in d["wins"][0]["fan"]["items"]]
    assert "天胡" in names
    assert d["wins"][0]["fan"]["multiplier"] == 16
    assert d["per_seat"]["0"] == 48


def test_dihu_settlement():
    """地胡:非庄胡庄家首打,顶格。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="9m", src="wall"),
        _ev("discard", seat=0, tile="9m"),
        _ron_win(2, 0, "9m", PINGHU),
    ]
    d = settle_record({"meta": {"dealer": 0}, "events": events}).to_dict()
    names = [i["name"] for i in d["wins"][0]["fan"]["items"]]
    assert "地胡" in names
    assert d["wins"][0]["fan"]["multiplier"] == 16
    assert d["wins"][0]["payer_seats"] == [0]


def test_kan_kaihua_settlement():
    """杠上开花:暗杠后岭上摸牌自摸,+2 番。"""
    events = _mini_deals() + _lacks() + [
        _ev("draw", seat=0, tile="9s", src="wall"),
        _ev("kan", seat=0, kind="ankan", tile="9s"),
        _ev("kan_draw", seat=0, tile="5s", src="rinshan"),
        _tsumo_win(0, "5s", PINGHU),
    ]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    names = [i["name"] for i in d["wins"][0]["fan"]["items"]]
    assert "杠上开花" in names
    # 暗杠杠钱:1/2/3 各付 2;胡牌:平胡1+自摸1+杠开2=4 番 8 倍
    assert d["wins"][0]["fan"]["multiplier"] == 8
    assert d["kans"][0]["amount_each"] == 2
    assert sum(d["per_seat"].values()) == 0


def test_tenpai_chajiao_construction():
    """流局查叫:下叫未胡者收未下叫者的听牌理论最大番倍数(死叫也算下叫)。

    座 0 听 3s(胡成平胡,1 倍);座 1/2/3 未下叫(2 门散张、非花猪)。
    三家各赔座 0 一份 1 倍。
    """
    tenpai_hand = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
                   "1s", "2s", "5s", "5s"]  # 13 张,听 3s
    deals = [_ev("deal", seat=0, tiles=tenpai_hand)] + [
        _ev("deal", seat=s, tiles=list(_FILLER[s])) for s in (1, 2, 3)
    ]
    events = deals + _lacks() + [_ev("ryuukyoku")]
    d = settle_record({"meta": {}, "events": events}).to_dict()
    assert len(d["tenpais"]) == 3
    for t in d["tenpais"]:
        assert t["wait_seat"] == 0 and t["payer"] in (1, 2, 3)
        assert t["wait_tiles"] == ["3s"]
        assert t["max_fan"] == 1 and t["multiplier"] == 1 and t["amount"] == 1
    assert d["per_seat"]["0"] == 3
    assert d["per_seat"]["1"] == d["per_seat"]["2"] == d["per_seat"]["3"] == -1
    assert d["huazhus"] == []


def test_rules_override_unknown_key():
    """FanRules 未知键抛 ValueError。"""
    with pytest.raises(ValueError, match="未知"):
        FanRules.from_dict({"no_such_key": 1})


def test_rules_to_dict_reflects_defaults():
    d = DEFAULT_RULES.to_dict()
    assert d["cap_fan"] == 5 and d["kan_ankan"] == 2 and d["huazhu_pay"] == 16
