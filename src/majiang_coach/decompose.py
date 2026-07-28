"""单门面子/搭子分解(内部模块,供 win 与 shanten 复用)。

输入:长度 9 的单门计数序列(某门 1-9 各自张数,每项 0-4)。
输出:
  - suit_decompositions(): 该门所有 Pareto 前沿分解 (sets, taatsu, pairs)。
      sets   = 完成面子数(刻子/顺子)
      taatsu = 搭子数(两面/嵌张/边张,2 张未完成)
      pairs  = 对子数
  - suit_can_full_melds(): 该门是否可全部拆为面子(无对子/搭子/浮牌)——win 复用。

Pareto 前沿:在 (sets, taatsu, pairs) 三维上"越多越好"(向听公式中三者系数
均为非正:sets=-2, taatsu/pairs=-1,且 pairs 可免除缺头罚),故被支配
(三维均 <= 且至少一维 <)的分解可安全剪枝。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

__all__ = ["suit_decompositions", "suit_can_full_melds"]


@lru_cache(maxsize=None)
def _decompose(c: tuple[int, ...]) -> frozenset[tuple[int, int, int]]:
    """递归枚举剩余计数 c 的所有分解 (sets, taatsu, pairs)。

    始终处理最低位非零牌:它必须被某种结构消耗(刻子/顺子/对子/搭子/孤立)。
    """
    n = len(c)
    i = 0
    while i < n and c[i] == 0:
        i += 1
    if i == n:
        return frozenset({(0, 0, 0)})

    results: set[tuple[int, int, int]] = set()

    # 刻子 i,i,i
    if c[i] >= 3:
        nxt = list(c)
        nxt[i] -= 3
        for s, t, p in _decompose(tuple(nxt)):
            results.add((s + 1, t, p))

    # 顺子 i,i+1,i+2
    if i + 2 < n and c[i] >= 1 and c[i + 1] >= 1 and c[i + 2] >= 1:
        nxt = list(c)
        nxt[i] -= 1
        nxt[i + 1] -= 1
        nxt[i + 2] -= 1
        for s, t, p in _decompose(tuple(nxt)):
            results.add((s + 1, t, p))

    # 对子 i,i
    if c[i] >= 2:
        nxt = list(c)
        nxt[i] -= 2
        for s, t, p in _decompose(tuple(nxt)):
            results.add((s, t, p + 1))

    # 搭子(两面/边张) i,i+1
    if i + 1 < n and c[i] >= 1 and c[i + 1] >= 1:
        nxt = list(c)
        nxt[i] -= 1
        nxt[i + 1] -= 1
        for s, t, p in _decompose(tuple(nxt)):
            results.add((s, t + 1, p))

    # 搭子(嵌张) i,i+2
    if i + 2 < n and c[i] >= 1 and c[i + 2] >= 1:
        nxt = list(c)
        nxt[i] -= 1
        nxt[i + 2] -= 1
        for s, t, p in _decompose(tuple(nxt)):
            results.add((s, t + 1, p))

    # 孤立牌(浮牌):仅消耗一张,不形成任何搭子
    nxt = list(c)
    nxt[i] -= 1
    for s, t, p in _decompose(tuple(nxt)):
        results.add((s, t, p))

    return frozenset(results)


def _pareto(
    decomps: frozenset[tuple[int, int, int]],
) -> tuple[tuple[int, int, int], ...]:
    """保留 (sets, taatsu, pairs) 三维非支配分解。"""
    pts = list(decomps)
    keep: list[tuple[int, int, int]] = []
    for d in pts:
        dominated = False
        for other in pts:
            if other is d or other == d:
                continue
            if other[0] >= d[0] and other[1] >= d[1] and other[2] >= d[2]:
                dominated = True
                break
        if not dominated:
            keep.append(d)
    return tuple(keep)


def suit_decompositions(
    counts_9: Sequence[int],
) -> tuple[tuple[int, int, int], ...]:
    """单门 Pareto 前沿分解集合。"""
    return _pareto(_decompose(tuple(counts_9)))


def suit_can_full_melds(counts_9: Sequence[int]) -> bool:
    """该门是否可全部拆为面子(刻子/顺子),无对子/搭子/浮牌残留。

    win 标准形:取出雀头后,剩余 12 张需三门各自全部成面子。
    最低位非零牌必须作为某面子的起点(刻子或顺子),否则不可能全成面子。
    """
    c = list(counts_9)

    def rec() -> bool:
        i = 0
        while i < 9 and c[i] == 0:
            i += 1
        if i == 9:
            return True
        # 刻子
        if c[i] >= 3:
            c[i] -= 3
            if rec():
                c[i] += 3
                return True
            c[i] += 3
        # 顺子
        if i + 2 < 9 and c[i] >= 1 and c[i + 1] >= 1 and c[i + 2] >= 1:
            c[i] -= 1
            c[i + 1] -= 1
            c[i + 2] -= 1
            if rec():
                c[i] += 1
                c[i + 1] += 1
                c[i + 2] += 1
                return True
            c[i] += 1
            c[i + 1] += 1
            c[i + 2] += 1
        return False

    return rec()
