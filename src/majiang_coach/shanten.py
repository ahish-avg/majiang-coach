"""向听数 shanten(hand, lack_suit=None, melds=0) -> int。

13/14 张语义(务必与 ukeire 配合一致,见模块末尾约定):

  - 待弃态(13-3*melds 张):标准向听。听牌 = 0,1 向听 = 1,……(3n+1 约定)。
  - 刚摸态(14-3*melds 张):若 win() -> -1(已胡);否则 = min(各可弃牌后待弃态的向听)。
        即"弃一张后最优向听"。刚摸态听牌(弃一张即听)记 0;胡牌记 -1。
  - lack_suit 指定某门为缺门:该门牌**禁止参与任何搭子/对子/面子**(视为必须打出的
        废牌),但**仍占张数**(不从 counts 删除)。这使标准公式自然体现"每张缺门牌≈+1 向听",
        并通过缺头罚处理"缺门孤立牌无法当雀头"的情形。
  - lack_suit=None:枚举三门作缺门取最小向听(自动选最优缺门)。

副露(melds>0,Phase 3 扩展,镜像 win 的 melds 参数):
  - melds = 已固定副露数(碰/杠各计 1 副露;杠虽 4 张但计 1,杠后岭上补摸抵消,故
    暗手张数恒为 14-3*melds,与碰一致)。
  - melds>0:标准形目标 = (4-melds) 面子 + 1 将对;差张下叫基线 2*(4-melds)(替代
        硬编码 8),搭子/面子候补上限 (4-melds);**七对路径禁用**(副露不能七对)。
  - 张数校验:合法暗手 = {13-3*melds(待弃态), 14-3*melds(刚摸态)};melds=0 时即
        {13,14},原 12/16 张报错用例继续生效。
  - lru_cache key 含 melds(基线随 melds 变)。
  - 向后兼容:melds=0 与 Phase 1 完全一致。

返回:-1=已胡,0=听牌,>=1=向听数。

=== 与 ukeire 的约定(避免打架)===
  ukeire(hand待弃态):对每个可能摸到的牌 idx,构成刚摸态后调用本函数 shanten(刚摸态);
                  若该刚摸态向听 < 输入待弃态向听,则为有效牌。
  - 听牌输入(待弃态向听 0):有效牌 = 使刚摸态向听 = -1 的牌(即待ち/胡牌牌)。
  - 1 向听输入:有效牌 = 使刚摸态向听 = 0(弃一张即听)或 -1 的牌。
  故 ukeire 始终用"刚摸态 shanten"评估摸入,用"待弃态 shanten"作基线,二者语义在此锁定。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from .decompose import suit_decompositions
from .hand import Hand
from .win import _valid_lack, win

__all__ = ["shanten"]


def shanten(hand: Hand, lack_suit: int | None = None, melds: int = 0) -> int:
    """计算向听数。详见模块文档串。

    melds>0 时禁七对、目标面子数为 (4-melds)、暗手张数为 14-3*melds(刚摸)/13-3*melds(待弃)。
    """
    if not isinstance(melds, int) or isinstance(melds, bool) or melds < 0:
        raise ValueError(f"melds must be a non-negative int, got {melds!r}")
    lack = _valid_lack(lack_suit)
    total = hand.total

    expected_draw = 14 - 3 * melds   # 刚摸态(待弃:刚摸,有弃牌选择)
    expected_wait = 13 - 3 * melds   # 待摸态(轮别人:已弃,等摸;= ukeire 输入)
    if total != expected_draw and total != expected_wait:
        raise ValueError(
            f"shanten 需 {expected_wait} 或 {expected_draw} 张手牌(melds={melds}),当前 {total} 张"
        )

    if total == expected_draw:
        if win(hand, lack, melds):
            return -1
        best = 8 - 2 * melds
        counts = hand.counts
        for idx in range(27):
            if counts[idx] > 0:
                removed = list(counts)
                removed[idx] -= 1
                s = _shanten_13(tuple(removed), lack, melds)
                if s < best:
                    best = s
                    if best == -1:
                        break
        return best

    return _shanten_13(hand.counts, lack, melds)


@lru_cache(maxsize=None)
def _shanten_13(counts: tuple[int, ...], lack, melds: int) -> int:
    """待弃态(3n+1)向听。lack 为 None 时枚举三门取最小。melds>0 时禁七对。"""
    if lack is None:
        return min(_shanten_13(counts, L, melds) for L in (0, 1, 2))
    if melds > 0:
        return _standard_13(counts, lack, melds)
    return min(_standard_13(counts, lack, 0), _chiitoitsu_13(counts, lack))


def _standard_13(counts: Sequence[int], dead_suit: int | None, melds: int = 0) -> int:
    """标准形向听((4-melds) 面子 + 1 雀头)。melds 默认 0(向后兼容旧调用/oracle)。

    dead_suit 为某门(0/1/2):该门禁搭但仍占张数(缺一门模型)。
    dead_suit 为 None:三门皆可用(无缺门)--仅用于与开源参考实现对齐校验,
        公开 shanten() 路径不会传入 None(血战必缺一门,由 _shanten_13 枚举)。

    公式(移植自已验证实现,与 MahjongRepository regular shanten 对齐,副露泛化):
        need_sets = 4 - melds                      # 仍需完成的面子数
        kouho = M + T + (Pa-1 if Pa>=1 else 0)     # 雀头单独预留时的面子候补数
        excess = max(0, kouho - need_sets)         # 超出 need_sets 的搭子要拆,每多 1 个 +1
        ret = (8 - 2*melds) - 2*M - T - Pa + excess
    缺头罚:Pa==0 且 excess==0(未靠拆搭补雀头)且无可用(非缺门)浮牌当雀头时 +1。
    """
    total = sum(counts)
    need_sets = 4 - melds
    baseline = 8 - 2 * melds
    if dead_suit is None:
        dead_tiles = 0
    else:
        dead_tiles = sum(counts[dead_suit * 9:dead_suit * 9 + 9])

    decomps: list[tuple[tuple[int, int, int], ...]] = []
    for s in range(3):
        if dead_suit is not None and s == dead_suit:
            decomps.append(((0, 0, 0),))  # 缺门:禁搭,贡献 0,但牌仍占 total
        else:
            decomps.append(suit_decompositions(counts[s * 9:s * 9 + 9]))

    best = baseline
    for a in decomps[0]:
        for b in decomps[1]:
            for c in decomps[2]:
                M = a[0] + b[0] + c[0]
                T = a[1] + b[1] + c[1]
                Pa = a[2] + b[2] + c[2]
                kouho = M + T + (Pa - 1 if Pa >= 1 else 0)
                excess = kouho - need_sets
                if excess < 0:
                    excess = 0
                ret = baseline - 2 * M - T - Pa + excess
                if Pa == 0 and excess == 0:
                    # 无对子、未拆搭:需要一张可用浮牌当雀头(单骑/边张等)。
                    # 缺门浮牌不可用,故 usable = 浮牌 - 缺门张数;若无可用 -> +1。
                    floaters = total - 3 * M - 2 * T
                    if floaters < 0:
                        floaters = 0
                    if floaters - dead_tiles <= 0:
                        ret += 1
                if ret < best:
                    best = ret
    return best


def _chiitoitsu_13(counts: Sequence[int], dead_suit: int) -> int:
    """七对(含龙七对结构)向听。count//2 计对(count==4 视为两对),无"七种互异"约束。

    缺门牌不能成对(禁搭),仅当废牌占张。设:
        p = 非缺门对子数(sum c//2), s = 非缺门单张数(sum c%2),
        U = 非缺门总张数, L = 缺门张数(= total - U)。
    听牌目标 = 6 对 + 1 非缺门单张(待ち)。
        若 s >= 7 - p(单张足够凑齐剩余对子并留 1 张待ち):向听 = 6 - p。
        否则缺单张,每缺 1 需多 1 巡(先摸新种成单再成对),合计 = L。
    无缺门(L=0)时退化为 6 - p(标准七对向听)。

    仅 melds==0 调用(副露不能七对)。
    """
    p = 0
    s = 0
    U = 0
    for suit in range(3):
        if suit == dead_suit:
            continue
        base = suit * 9
        for c in counts[base:base + 9]:
            if c:
                p += c // 2
                s += c % 2
                U += c
    if p >= 7:
        return -1
    L = sum(counts) - U
    if s >= 7 - p:
        return 6 - p
    return L
