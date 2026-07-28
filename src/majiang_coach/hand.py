"""Hand:不可变手牌计数结构。

内部用长度 27 的 `counts` 元组(每项 0-4)。frozen=True 使其可哈希、可比较、
被多模块安全复用。所有变更操作(add/remove)返回新实例,符合血战算法层
"纯函数 + 不可变数据"的约定。

缺一门判定由 `suits_present()` 提供原语;具体"是否构成胡牌所需缺一门"由 win 模块判定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from . import tiles

__all__ = ["Hand"]


@dataclass(frozen=True)
class Hand:
    """不可变手牌:counts 为长度 27 的元组,每项 0-4。"""

    counts: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.counts, tuple):
            # 允许传入 list/Sequence,自动转 tuple
            object.__setattr__(self, "counts", tuple(self.counts))
        c = self.counts
        if len(c) != tiles.NUM_TILES:
            raise ValueError(
                f"counts length must be {tiles.NUM_TILES}, got {len(c)}"
            )
        for i, v in enumerate(c):
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError(f"counts[{i}] must be int, got {v!r}")
            if not (0 <= v <= 4):
                raise ValueError(
                    f"counts[{i}] must be in 0..4 (牌池每牌最多 4 张), got {v}"
                )

    # ---- 基本属性 ----
    @property
    def total(self) -> int:
        """手牌总张数。"""
        return sum(self.counts)

    def count(self, idx: int) -> int:
        """某索引牌的当前张数。"""
        return self.counts[idx]

    def suits_present(self) -> set[int]:
        """当前手牌出现的门集合 (0=万 1=条 2=筒)。

        缺一门原语:血战胡牌要求 len(suits_present()) <= 2(恰缺一门或更少)。
        """
        return {i // 9 for i, c in enumerate(self.counts) if c > 0}

    # ---- 变更(返回新实例) ----
    def add(self, idx: int) -> "Hand":
        """摸入一张 idx,返回新 Hand。超过 4 张抛 ValueError。"""
        if not isinstance(idx, int) or not (0 <= idx < tiles.NUM_TILES):
            raise ValueError(f"Invalid tile index: {idx!r}")
        if self.counts[idx] >= 4:
            raise ValueError(
                f"Cannot add {tiles.index_to_code(idx)}: already 4 copies"
            )
        lst = list(self.counts)
        lst[idx] += 1
        return Hand(tuple(lst))

    def remove(self, idx: int) -> "Hand":
        """打出一张 idx,返回新 Hand。该牌为 0 张抛 ValueError。"""
        if not isinstance(idx, int) or not (0 <= idx < tiles.NUM_TILES):
            raise ValueError(f"Invalid tile index: {idx!r}")
        if self.counts[idx] <= 0:
            raise ValueError(
                f"Cannot remove {tiles.index_to_code(idx)}: count is 0"
            )
        lst = list(self.counts)
        lst[idx] -= 1
        return Hand(tuple(lst))

    def clone(self) -> "Hand":
        """返回等价副本(frozen,与 self 相等)。"""
        return Hand(self.counts)

    # ---- 构造 ----
    @classmethod
    def from_counts(cls, counts: Sequence[int]) -> "Hand":
        return cls(tuple(counts))

    @classmethod
    def from_indices(cls, indices: Iterable[int]) -> "Hand":
        counts = [0] * tiles.NUM_TILES
        for i in indices:
            if not (0 <= i < tiles.NUM_TILES):
                raise ValueError(f"Invalid tile index: {i!r}")
            counts[i] += 1
            if counts[i] > 4:
                raise ValueError(f"Too many copies of {tiles.index_to_code(i)}")
        return cls(tuple(counts))

    @classmethod
    def from_codes(cls, codes) -> "Hand":
        """从牌码列表(元素可为单码或拼接码)构造。"""
        return cls.from_indices(tiles.codes_to_indices(codes))

    @classmethod
    def empty(cls) -> "Hand":
        return cls(tuple([0] * tiles.NUM_TILES))

    # ---- 序列化 ----
    def to_indices(self) -> list[int]:
        """展开为索引列表(按索引升序,按张数重复)。"""
        out: list[int] = []
        for i, c in enumerate(self.counts):
            if c:
                out.extend([i] * c)
        return out

    def to_codes(self) -> list[str]:
        """展开为牌码列表(每张一个码)。"""
        return [tiles.index_to_code(i) for i in self.to_indices()]

    def __repr__(self) -> str:  # noqa: D401
        codes = " ".join(self.to_codes())
        return f"Hand({'empty' if not codes else codes})"
