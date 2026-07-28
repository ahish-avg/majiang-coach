"""TileWall:带种子洗牌 / 发牌 / 摸牌 / 杠尾摸牌 / 流局判定。

血战到底牌墙:27 种牌 × 4 张 = 108 张。发牌 4×13=52,余 56 为活牌墙。
首摸从牌墙前端;杠尾(岭上)摸从牌墙尾端。两指针相遇 = 流局(摸完)。

零第三方依赖,纯 Python。
"""

from __future__ import annotations

import random

from .. import tiles

__all__ = ["TileWall", "WallExhausted"]


class WallExhausted(Exception):
    """牌墙已摸完,无法再摸。"""


class TileWall:
    """108 张带种子洗牌牌墙。

    内部用一维列表 + 前后双指针:
        - ``_front``:下次首摸位置(向右推进)。
        - ``_back``:下次杠尾摸位置(向左推进,指向待取牌的下一格)。
    剩余 = ``_back - _front``;两指针相遇即流局。
    """

    __slots__ = ("_wall", "_front", "_back", "_seed")

    def __init__(self, seed: int, preset: list[int] | None = None) -> None:
        self._seed = seed
        if preset is not None:
            self._wall = list(preset)
        else:
            rng = random.Random(seed)
            wall: list[int] = []
            for idx in range(tiles.NUM_TILES):
                wall.extend([idx, idx, idx, idx])
            rng.shuffle(wall)
            self._wall = wall
        self._front = 0
        self._back = len(self._wall)  # 108

    @property
    def seed(self) -> int:
        return self._seed

    def deal(self) -> list[list[int]]:
        """发牌:4 座各 13 张(共 52),返回各座索引列表。余 56 为活牌墙。"""
        if self._front != 0:
            raise RuntimeError("deal() 只能在摸牌前调用一次")
        hands: list[list[int]] = []
        for _ in range(4):
            hand = self._wall[self._front : self._front + 13]
            self._front += 13
            hands.append(list(hand))
        return hands

    def draw(self) -> int:
        """从牌墙首端摸一张。牌墙空则 raise WallExhausted。"""
        if self._front >= self._back:
            raise WallExhausted()
        tile = self._wall[self._front]
        self._front += 1
        return tile

    def draw_rinshan(self) -> int:
        """从牌墙尾端(杠尾/岭上)摸一张。牌墙空则 raise WallExhausted。"""
        if self._front >= self._back:
            raise WallExhausted()
        self._back -= 1
        return self._wall[self._back]

    def remaining(self) -> int:
        """首/尾指针间剩余张数。"""
        return self._back - self._front

    def exhausted(self) -> bool:
        """牌墙是否已摸完(流局)。"""
        return self._front >= self._back
