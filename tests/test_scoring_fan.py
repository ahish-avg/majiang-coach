"""tests for Phase 7 fan_of():番种识别纯函数。

覆盖:每番种正例 + 反例;叠加(清一色+对对胡+根)、封顶(6 番 → 5,
cap_applied)、龙七对不计根、金勾钓不重计对对胡且需 4 副露、幺九+对对(顶格)、
事件番 ctx 组合(杠上开花/杠上炮/抢杠/海底/天胡/地胡)、含缺门牌防呆、张数防呆。
"""

from __future__ import annotations

import pytest

from majiang_coach import tiles
from majiang_coach.engine.melds import Meld
from majiang_coach.scoring import FanRules, WinCtx, fan_of
from majiang_coach.scoring.fan import FanResult


def H(*codes):
    """牌码(可拼接)-> 索引列表。"""
    return tiles.codes_to_indices(codes)


def M(kind, code, src=None):
    return Meld(kind, tiles.code_to_index(code), src)


def ctx(**kw):
    base = dict(event_index=0, seat=0, by="tsumo", tile=0, from_seat=None,
                robbery=False, kan_win=False, kan_dama=False, sea_bottom=False,
                heaven=False, earth=False)
    base.update(kw)
    return WinCtx(**base)


# ---- 基本牌型 ----

def test_pinghu_tsumo():
    """平胡自摸:1+1 = 2 番 2 倍。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="tsumo")
    assert r.has("平胡") and r.has("自摸")
    assert r.total_fan == 2 and r.multiplier == 2 and not r.cap_applied


def test_pinghu_ron():
    """平胡点炮:1 番 1 倍,无自摸。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="ron")
    assert r.names() == ["平胡"]
    assert r.total_fan == 1 and r.multiplier == 1


def test_duidui():
    """对对胡:全刻子+将,2 番。"""
    hand = H("1m1m1m", "3m3m3m", "5m5m5m", "7s7s7s", "9p9p")
    r = fan_of(hand, lack=None, by="ron")
    assert r.has("对对胡") and not r.has("清一色")
    assert r.total_fan == 2


def test_duidui_negative_sequence_hand():
    """含顺子的标准形不算对对胡。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="ron")
    assert not r.has("对对胡")


def test_qingyise():
    """清一色:全万,4 番。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5m5m")
    r = fan_of(hand, lack=1, by="ron")
    assert r.has("清一色") and not r.has("对对胡")
    assert r.total_fan == 4 and r.multiplier == 8


def test_qingyise_duidui_gen_stack():
    """清一色+对对胡(+无根):4+2 = 6 番 -> 封顶 5 番 16 倍。"""
    hand = H("1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m")
    r = fan_of(hand, lack=1, by="ron")
    assert r.has("清一色") and r.has("对对胡")
    assert r.total_fan == 5 and r.multiplier == 16 and r.cap_applied


def test_qidui():
    """七对:7 个互异对子,4 番。"""
    hand = H("1m1m", "2m2m", "3m3m", "4m4m", "5m5m", "6p6p", "7p7p")
    r = fan_of(hand, lack=1, by="ron")
    assert r.has("七对") and not r.has("龙七对")
    assert r.total_fan == 4


def test_long_qidui():
    """龙七对:4 同张作两对,8 番(封顶 16 倍);龙对那 4 张不另计根。"""
    hand = H("1m1m1m1m", "2m2m", "3m3m", "4m4m", "5m5m", "6p6p")
    r = fan_of(hand, lack=1, by="ron")
    assert r.has("龙七对") and not r.has("七对") and not r.has("根")
    assert r.total_fan == 5 and r.multiplier == 16 and r.cap_applied


def test_long_qidui_gen_from_kan_impossible():
    """龙七对暗手 4 同张不计根(根条目缺该牌)。"""
    hand = H("1m1m1m1m", "2m2m", "3m3m", "4m4m", "5m5m", "6p6p")
    r = fan_of(hand, lack=1, by="ron")
    gen = [i for i in r.items if i.name == "根"]
    assert not gen


def test_jingoudiao_needs_four_melds():
    """金勾钓需 4 副露、暗手仅剩将;3 副露不算。"""
    melds3 = [M("pon", "1m", 1), M("pon", "2m", 2), M("ankan", "3m")]
    hand5 = H("4s4s", "7s8s9s")  # 3 副露暗手 5 张:一对将 + 一顺子
    r3 = fan_of(hand5, melds3, lack=2, by="ron")
    assert not r3.has("金勾钓")

    melds4 = melds3 + [M("pon", "5s", 3)]
    r4 = fan_of(H("6s6s"), melds4, lack=2, by="ron")
    assert r4.has("金勾钓")
    assert not r4.has("对对胡")  # 金勾钓不与对对胡重计
    assert r4.has("根")          # 暗杠计 1 根


def test_yaojiu():
    """幺九(全 1/9)+ 对对胡:4+2 = 6 番 -> 顶格。"""
    hand = H("1m1m1m", "9m9m9m", "1s1s1s", "9s9s9s", "1p1p")
    r = fan_of(hand, lack=None, by="ron")
    assert r.has("幺九") and r.has("对对胡")
    assert r.total_fan == 5 and r.multiplier == 16 and r.cap_applied


def test_yaojiu_negative():
    """含中张牌不算幺九。"""
    hand = H("1m1m1m", "9m9m9m", "1s1s1s", "2s3s4s", "9s9s")
    r = fan_of(hand, lack=2, by="ron")
    assert not r.has("幺九")


# ---- 根 ----

def test_gen_from_ankan_and_shouminkan():
    """暗杠/补杠各 1 根;暗手无 4 同张不重复计。"""
    melds = [M("ankan", "2m"), M("shouminkan", "1s")]
    hand = H("1m1m1m", "3m3m3m", "5s5s")
    r = fan_of(hand, melds, lack=2, by="ron")
    gen = [i for i in r.items if i.name == "根"][0]
    assert gen.fan == 2 and "2m" in gen.basis and "1s" in gen.basis


def test_gen_concealed_quad():
    """暗手 4 同张(标准形含顺)计 1 根。"""
    # 1m*4 + 2m3m4m + 5m6m7m + 8m8m? 构造:1m1m1m1m 2m3m4m 5m6m7m 9m9m 数张:4+3+3+2=12... 需14
    hand = H("1m1m1m1m", "2m3m4m", "5m6m7m", "8m", "9m9m", "8m")
    r = fan_of(hand, lack=1, by="ron")
    assert r.has("根")


# ---- 事件番 ctx ----

def test_kan_kaihua():
    """杠上开花 +2(tsumo 且 ctx.kan_win)。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="tsumo", ctx=ctx(kan_win=True))
    assert r.has("杠上开花") and r.has("自摸")
    assert r.total_fan == 4  # 平胡1 + 自摸1 + 杠上开花2


def test_kan_dama():
    """杠上炮 +2(ron 且 ctx.kan_dama);抢杠互斥。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="ron", ctx=ctx(by="ron", kan_dama=True))
    assert r.has("杠上炮") and not r.has("抢杠胡")
    r2 = fan_of(hand, lack=2, by="ron", ctx=ctx(by="ron", kan_dama=True, robbery=True))
    assert not r2.has("杠上炮") and r2.has("抢杠胡")


def test_haidi_tsumo_and_ron():
    """海底捞月(tsumo)/ 海底炮(ron)各 +2。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="tsumo", ctx=ctx(sea_bottom=True))
    assert r.has("海底捞月")
    r2 = fan_of(hand, lack=2, by="ron", ctx=ctx(by="ron", sea_bottom=True))
    assert r2.has("海底炮") and not r2.has("海底捞月")


def test_tianhu():
    """天胡:顶格 16 倍(平胡+天胡+自摸,总番封顶 5)。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s")
    r = fan_of(hand, lack=2, by="tsumo", ctx=ctx(heaven=True))
    assert r.has("天胡") and r.total_fan == 5 and r.multiplier == 16 and r.cap_applied


def test_dihu():
    """地胡:顶格 16 倍(ron)。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s5s")
    r = fan_of(hand, lack=2, by="ron", ctx=ctx(by="ron", earth=True))
    assert r.has("地胡") and r.total_fan == 5 and r.multiplier == 16 and r.cap_applied


def test_no_ctx_no_event_fans():
    """ctx=None 时只算牌型番 + 自摸(by 决定),无任何事件番。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    r = fan_of(hand, lack=2, by="ron", ctx=None)
    assert r.names() == ["平胡"]


# ---- 防呆 / 规则覆盖 ----

def test_lack_guard_concealed():
    """暗手含缺门牌抛 ValueError。"""
    hand = H("1m2m3m", "4m5m6m", "7m8m9m", "2m3m4m", "5s5s")
    with pytest.raises(ValueError, match="缺门"):
        fan_of(hand, lack=0, by="ron")  # 缺万但手有万


def test_lack_guard_meld():
    """副露含缺门牌抛 ValueError。"""
    melds = [M("pon", "1m", 1)]
    hand = H("2p3p4p", "5p6p7p", "8p8p", "3s4s5s")
    with pytest.raises(ValueError, match="缺门"):
        fan_of(hand, melds, lack=0, by="ron")


def test_wrong_tile_count():
    """暗手张数与副露不匹配抛 ValueError。"""
    with pytest.raises(ValueError, match="张"):
        fan_of(H("1m2m3m"), lack=2, by="ron")
    with pytest.raises(ValueError, match="张"):
        fan_of(H("1m1m"), [M("pon", "2m", 1), M("pon", "3m", 2)], lack=2, by="ron")


def test_custom_rules_cap():
    """FanRules 覆盖:cap_fan=4 -> 清一色对对(6 番)封到 4 番 8 倍。"""
    rules = FanRules(cap_fan=4)
    hand = H("1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m")
    r = fan_of(hand, lack=1, by="ron", rules=rules)
    assert r.total_fan == 4 and r.multiplier == 8 and r.cap_applied


def test_fan_result_roundtrip():
    """FanResult to_dict/from_dict 往返一致。"""
    hand = H("1m1m1m", "2m2m2m", "3m3m3m", "4m4m4m", "5m5m")
    r = fan_of(hand, lack=1, by="ron")
    d = r.to_dict()
    r2 = FanResult.from_dict(d)
    assert r2.to_dict() == d
    assert r2.names() == r.names()
