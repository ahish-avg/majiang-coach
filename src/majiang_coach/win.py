"""胡牌判定 win(hand, lack_suit=None, melds=0) -> bool。

hand 为暗手(concealed)。胡牌 = 标准形(4 面子 + 1 雀头) ‖ 七对(含龙七对结构),
且满足缺一门。

副露(melds>0,Phase 2 扩展):
  - melds = 已固定副露数(碰/杠各计 1 副露;杠虽 4 张但计 1 副露)。
  - 杠后从杠尾补摸,故暗手张数恒为 14 - 3*melds(与碰一致:碰-3,杠-4+1岭上=净-3)。
  - melds>0:暗手须成 (4-melds) 面子 + 1 雀头;**七对路径禁用**(副露不能七对)。
  - 缺一门:暗手中缺门牌须为 0;副露按构造不含缺门牌(由动作层保证)。
  - 向后兼容:melds=0 行为与 Phase 1 完全一致。

缺一门(血战到底核心规则):
  - 胡牌时手中必须不含所缺的那一门(已全部打出)。
  - lack_suit=None:自动枚举三门作缺门,等价于"手牌至多两门"(非三门齐)且结构成立。
  - lack_suit=L:要求 L 门在手中张数为 0,且其余两门结构成立。

注意:七对中的 count==4 视为两对(龙七对结构),Phase 1 仅做结构判定,不识别番名。
"""

from __future__ import annotations

from .decompose import suit_can_full_melds
from .hand import Hand

__all__ = ["win"]


def _valid_lack(lack_suit) -> int | None:
    if lack_suit is None:
        return None
    if not isinstance(lack_suit, int) or isinstance(lack_suit, bool) or lack_suit not in (0, 1, 2):
        raise ValueError(f"lack_suit must be None or 0/1/2, got {lack_suit!r}")
    return lack_suit


def _win_standard(counts: tuple[int, ...]) -> bool:
    """标准形:4 面子 + 1 雀头。尝试每个对子作雀头,剩余 12 张三门全成面子。"""
    for head in range(27):
        if counts[head] < 2:
            continue
        rem = list(counts)
        rem[head] -= 2
        ok = True
        for s in range(3):
            if not suit_can_full_melds(rem[s * 9:s * 9 + 9]):
                ok = False
                break
        if ok:
            return True
    return False


def _win_seven_pairs(counts: tuple[int, ...]) -> bool:
    """七对(含龙七对结构):count//2 之和 == 7(14 张全部成对,count==4 视为两对)。"""
    return sum(c // 2 for c in counts) == 7


def _win_structure(counts: tuple[int, ...]) -> bool:
    return _win_standard(counts) or _win_seven_pairs(counts)


def win(hand: Hand, lack_suit: int | None = None, melds: int = 0) -> bool:
    """暗手是否胡牌(标准形 ‖ 七对),内置缺一门。

    返回 True 当且仅当:暗手张数 == 14 - 3*melds,且满足缺一门,且结构成立。
    melds>0 时七对路径禁用(副露不能七对)。

    注意:melds>0 且 lack_suit=None 时,缺门仅检查暗手门数(副露门不可见);
    引擎调用时必传显式 lack_suit,故该限制不影响实际使用。
    """
    if not isinstance(melds, int) or isinstance(melds, bool) or melds < 0:
        raise ValueError(f"melds must be a non-negative int, got {melds!r}")
    expected = 14 - 3 * melds
    if hand.total != expected:
        return False
    lack = _valid_lack(lack_suit)
    present = hand.suits_present()

    if lack is None:
        # 三门齐(三门都有牌)不能胡
        if len(present) >= 3:
            return False
    else:
        # 所缺那门必须已全部打出(手中 0 张)
        if lack in present:
            return False

    # melds>0:七对禁用,仅标准形
    if melds > 0:
        return _win_standard(hand.counts)
    return _win_structure(hand.counts)
