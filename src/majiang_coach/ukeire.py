"""有效牌 ukeire(hand待摸态, lack_suit=None, melds=0) -> list[UkeireTile]。

对每个可能摸到的牌 idx(0-26,该牌手中不足 4 张才可摸),构成刚摸态后计算向听;
若该刚摸态向听 < 输入待摸态向听,则为有效牌(进张)。

与 shanten 的语义锁定(见 shanten.py 模块文档):
  - 基线 = shanten(hand待摸态, lack_suit, melds)           # 待摸态向听
  - 摸入后 = shanten(hand.add(idx), lack_suit, melds)      # 刚摸态向听(win -> -1)
  - 有效牌 = { idx | 摸入后向听 < 基线 }
  - 下叫输入(基线 0):有效牌 = 使刚摸态向听 = -1 的牌,即待ち(胡牌牌),new_shanten = -1。
  - 差 1 张输入:有效牌 = 使刚摸态向听 = 0(弃一张即下叫)的牌,new_shanten = 0。

副露(melds>0,Phase 3 扩展):
  - 输入须为待摸态(13-3*melds 张);摸入后为刚摸态(14-3*melds),走 shanten 刚摸态路径。
  - melds>0 时七对禁用、目标面子数 (4-melds),均由 shanten 内部处理,本函数仅透传 melds。
  - 向后兼容:melds=0 与 Phase 1 完全一致(输入须 13 张)。

Phase 1/3 不考虑剩余张数/安全度(只看牌型),但手中已有 4 张的牌不可再摸(牌池上限)。
缺门牌摸入后仍为废牌,自然不会降低向听,故不会出现在结果中。
"""

from __future__ import annotations

from dataclasses import dataclass

from .hand import Hand
from .shanten import shanten
from .tiles import index_to_code
from .win import _valid_lack

__all__ = ["UkeireTile", "ukeire", "ukeire_codes"]


@dataclass(frozen=True)
class UkeireTile:
    """一张有效牌。"""

    tile_index: int
    code: str
    new_shanten: int  # 摸入后的向听(下叫输入下为 -1 表示即胡)


def ukeire(hand: Hand, lack_suit: int | None = None, melds: int = 0) -> list[UkeireTile]:
    """返回降低向听的有效牌列表(按索引升序)。

    hand 必须为待摸态(13-3*melds 张)。下叫输入返回待ち(胡牌牌);差 1 张输入返回进张(改善牌)。
    """
    if not isinstance(melds, int) or isinstance(melds, bool) or melds < 0:
        raise ValueError(f"melds must be a non-negative int, got {melds!r}")
    expected_wait = 13 - 3 * melds  # 待摸态
    if hand.total != expected_wait:
        raise ValueError(
            f"ukeire 需 {expected_wait} 张手牌(melds={melds}),当前 {hand.total} 张"
        )
    lack = _valid_lack(lack_suit)

    base = shanten(hand, lack, melds)
    results: list[UkeireTile] = []
    counts = hand.counts
    for idx in range(27):
        if counts[idx] >= 4:
            continue  # 牌池上限:手中已有 4 张,不可再摸第 5 张
        new_shanten = shanten(hand.add(idx), lack, melds)
        if new_shanten < base:
            results.append(UkeireTile(idx, index_to_code(idx), new_shanten))
    results.sort(key=lambda u: u.tile_index)
    return results


def ukeire_codes(hand: Hand, lack_suit: int | None = None, melds: int = 0) -> list[str]:
    """便捷:返回有效牌的字符串码列表(按索引升序)。"""
    return [u.code for u in ukeire(hand, lack_suit, melds)]
