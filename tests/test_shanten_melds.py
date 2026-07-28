"""tests for shanten() melds extension (Phase 3).

覆盖:
  - melds=0 严格回归(与 Phase 1 一致,含张数校验)。
  - melds=1/2/3 差张下叫、含杠、下叫(听牌)。
  - 杠占张钉死 3*melds(反驳"杠扣4"):待弃态=14-3*melds、待摸态=13-3*melds。
  - 属性:副露胡牌去一牌 -> 待摸态向听 == 0(下叫)。
  - melds>0 禁七对。
"""

from __future__ import annotations

import pytest

from majiang_coach.hand import Hand
from majiang_coach.shanten import shanten
from majiang_coach.win import win


# ---- melds=0 回归(与 Phase 1 一致) ----

def test_melds0_default_equals_explicit():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    assert shanten(h) == 0
    assert shanten(h, None, 0) == shanten(h)


def test_melds0_invalid_count_still_raises():
    # 原 12/16 张报错用例对 melds=0 必须继续生效
    h16 = Hand.from_codes(["1m1m1m1m", "2m2m", "3m3m", "4s4s", "5s5s", "6s6s", "7s7s"])
    with pytest.raises(ValueError):
        shanten(h16, None, 0)
    h12 = Hand.from_codes(["1m2m3m", "4s5s6s", "7p8p9p"])
    with pytest.raises(ValueError):
        shanten(h12, None, 0)


def test_melds0_param_validation():
    h = Hand.from_codes(["5s5s"])
    with pytest.raises(ValueError):
        shanten(h, None, -1)
    with pytest.raises(ValueError):
        shanten(h, None, True)  # bool 不可


# ---- melds=1: 暗手 刚摸态 11 / 待摸态 10, 目标 3 面子 + 1 将对 ----

def test_melds1_win_returns_minus_one():
    # 刚摸态 11 张 = 3 面子 + 将对 -> 胡牌 -1
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    assert h.total == 11
    assert win(h, 2, 1) is True
    assert shanten(h, 2, 1) == -1


def test_melds1_tenpai_wait_state():
    # 待摸态 10 张:3 面子 + 1 浮牌(单吊叫) -> 下叫 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 0


def test_melds1_one_shanten():
    # 待摸态 10 张:2 面子 + 2 搭子(无将对) -> 差 1 张下叫
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s8s", "4s5s"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 1


def test_melds1_two_shanten():
    # 待摸态 10 张:1 面子 + 2 搭子 + 3 浮牌 -> 差 2 张下叫
    h = Hand.from_codes(["1m2m3m", "4s5s", "7s8s", "1s", "4m", "7m"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 2


def test_melds1_invalid_count_raises():
    # melds=1 合法张数 {10, 11};13/14 张应报错
    h13 = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "1s2s3s", "5s"])
    with pytest.raises(ValueError):
        shanten(h13, 2, 1)


def test_melds1_seven_pairs_disabled():
    # melds>0 禁七对:对子手(无顺子可成)七对路径会给更低值,但 melds=1 只走标准形
    # 1m1m 3m3m 5m5m 7s7s 9s9s(10 张):标准形=2,七对(若启用)=0;melds=1 须取标准 2
    h = Hand.from_codes(["1m1m", "3m3m", "5m5m", "7s7s", "9s9s"])
    assert h.total == 10
    assert shanten(h, 2, 1) == 2  # 标准形;若误启用七对会得 0


# ---- melds=2: 暗手 刚摸态 8 / 待摸态 7, 目标 2 面子 + 1 将对 ----

def test_melds2_win_returns_minus_one():
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert h.total == 8
    assert shanten(h, 2, 2) == -1


def test_melds2_tenpai():
    # 待摸态 7 张:2 面子 + 1 浮牌(单吊) -> 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s"])
    assert h.total == 7
    assert shanten(h, 2, 2) == 0


def test_melds2_one_shanten():
    # 待摸态 7 张:1 面子 + 2 搭子(无将) -> 1
    h = Hand.from_codes(["1m2m3m", "4s5s", "7s8s"])
    assert h.total == 7
    assert shanten(h, 2, 2) == 1


def test_melds2_auto_lack_two_suits():
    # lack=None,暗手仅两门 -> 枚举取最优缺门
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert shanten(h, None, 2) == -1


# ---- melds=3: 暗手 刚摸态 5 / 待摸态 4, 目标 1 面子 + 1 将对 ----

def test_melds3_win():
    h = Hand.from_codes(["1m2m3m", "5s5s"])
    assert h.total == 5
    assert shanten(h, 2, 3) == -1


def test_melds3_tenpai():
    h = Hand.from_codes(["1m2m3m", "5s"])
    assert h.total == 4
    assert shanten(h, 2, 3) == 0


def test_melds3_one_shanten():
    # 待摸态 4 张:2 搭子(无面子无将) -> 1
    h = Hand.from_codes(["1m2m", "4m5m"])
    assert h.total == 4
    assert shanten(h, 2, 3) == 1


# ---- 杠占张钉死 3*melds(反驳"杠扣4",见计划 §9) ----

def test_kan_tile_count_single_kan_melds1():
    """(a) 仅 1 杠 melds=1:刚摸态(待弃)暗手 11、待摸态 10。

    杠虽 4 张但计 1 副露;杠后岭上补摸,暗手净 -3,故 14-3*1=11(刚摸)/13-3*1=10(待摸)。
    若误用"杠扣4"会期望 10/9,此用例必失败。
    """
    # 杠上开花:暗杠后补摸成 11 张暗手 = 3 面子 + 将对 + 1 杠面 -> win(...,melds=1) True
    h_win = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"])
    assert h_win.total == 11  # 刚摸态
    assert win(h_win, 2, 1) is True
    assert shanten(h_win, 2, 1) == -1
    # 待摸态 10
    h_wait = h_win.remove(13)  # 去 5s(idx 13)
    assert h_wait.total == 10
    assert shanten(h_wait, 2, 1) == 0  # 下叫(单吊 5s)


def test_kan_tile_count_pon_plus_kan_melds2():
    """(b) 1 碰+1 杠 melds=2:刚摸态(待弃)暗手 8、待摸态 7。"""
    h_win = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert h_win.total == 8  # 刚摸态
    assert win(h_win, 2, 2) is True
    assert shanten(h_win, 2, 2) == -1
    h_wait = h_win.remove(15)  # 去 7s(idx 15)
    assert h_wait.total == 7
    assert shanten(h_wait, 2, 2) == 0  # 下叫


def test_kan_counts_as_one_meld_not_four_tiles():
    """杠计 1 副露(非"扣4张"):同一暗手在 melds=1 与 melds=2 下张数校验不同。

    8 张暗手:melds=2 合法(刚摸态 8);melds=1 非法(刚摸态应为 11)。
    """
    h8 = Hand.from_codes(["1m2m3m", "4m5m6m", "7s7s"])
    assert shanten(h8, 2, 2) == -1  # melds=2 合法
    with pytest.raises(ValueError):
        shanten(h8, 2, 1)  # melds=1 期望 10/11,8 张非法


# ---- 缺门罚(副露下保留) ----

def test_melds1_lack_present_raises_shanten():
    # 暗手含筒(lack=筒),副露下仍受缺门罚
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5p"])
    assert h.total == 10
    s_lack = shanten(h, 2, 1)   # 缺筒但暗手有筒 -> 筒废
    s_none = shanten(h, None, 1)
    assert s_lack >= 0
    # 指定缺筒(暗手有筒,罚)应 >= 自动枚举(可缺条)
    assert s_lack >= s_none


def test_melds1_lack_isolated_penalty():
    # 3 面子(万) + 1 筒缺门孤立(待摸态 10):缺门牌不能当单吊叫 -> 差 1 张下叫(非 0)
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5p"])
    assert shanten(h, 2, 1) == 1  # 缺门孤立 -> +1


# ---- 属性:副露胡牌去一牌 -> 待摸态向听 == 0(下叫) ----

@pytest.mark.parametrize("codes,melds,lack", [
    (["1m2m3m", "4m5m6m", "7m8m9m", "5s5s"], 1, 2),       # melds=1 标准胡
    (["1m2m3m", "4m5m6m", "7s7s"], 2, 2),                  # melds=2(碰+杠)
    (["1m2m3m", "5s5s"], 3, 2),                            # melds=3
    (["5s5s"], 4, 2),                                      # melds=4 仅将对
    (["1m1m1m", "2m2m2m", "3m3m3m", "5s5s"], 1, 2),       # melds=1 全刻子
])
def test_win_remove_any_tile_is_tenpai_with_melds(codes, melds, lack):
    """副露胡牌(刚摸态)去掉任意 1 张 -> 待摸态向听 == 0(下叫)。"""
    h = Hand.from_codes(codes)
    expected = 14 - 3 * melds
    assert h.total == expected, f"前提:暗手应为 {expected} 张"
    assert win(h, lack, melds) is True, f"前提:应为胡牌 {' '.join(codes)}"
    for idx in h.to_indices():
        h_wait = h.remove(idx)
        assert h_wait.total == expected - 1
        s = shanten(h_wait, lack, melds)
        assert s == 0, (
            f"副露胡牌去掉 {idx} 后应下叫(0),实得 {s}: {' '.join(h_wait.to_codes())}"
        )


# ---- 14 张(刚摸态)非胡 -> 弃一张取最优 ----

def test_melds1_draw_state_discard_to_tenpai():
    # 刚摸态 11 张:3 面子 + 1 搭子(无将),非胡;弃一张可单吊叫 -> 0
    h = Hand.from_codes(["1m2m3m", "4m5m6m", "7m8m9m", "5s6s"])
    assert h.total == 11
    assert win(h, 2, 1) is False
    assert shanten(h, 2, 1) == 0  # 弃 5s 或 6s -> 单吊叫
