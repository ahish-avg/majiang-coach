"""fan.py:番种识别纯函数(Phase 7,成都血战标准)。

fan_of(hand14, melds, lack, by, ctx, rules) -> FanResult:
  - hand14:胡牌暗手(索引列表,含胡牌张;张数 = 14 - 3*副露数)。
  - melds: 副露 Meld 列表(pon/ankan/daiminkan/shouminkan)。
  - lack:   缺门(0/1/2);防呆:胡牌张不得含缺门牌。
  - by:    "tsumo" | "ron"。
  - ctx:   scoring.ctx.WinCtx(事件番上下文;None 则只算牌型番)。
  - rules: FanRules(默认 DEFAULT_RULES)。

番种(默认表,全部进 FanRules):
  牌型番(互斥/叠加按川麻口径):七对 4、龙七对 8(互斥;龙对那 4 张不另计根)、
    对对胡 2、清一色 4、金勾钓 4(4 副露且暗手仅剩将)、幺九 4(全 1/9,含将)、
    天胡/地胡 16(值即顶格);都不沾 = 平胡 1 番。
  事件番(累加):自摸 +1、杠上开花 +2、杠上炮 +2、抢杠胡 +2、
    海底捞月/海底炮 +2、每根 +1(暗手 4 同张或杠各 1 根)。
  倍数 = 2^(总番-1);总番封顶 cap_fan(默认 5 番 = 16 倍),cap_applied 标注。
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import tiles
from ..engine.melds import Meld
from .ctx import WinCtx
from .rules import DEFAULT_RULES, FanRules

__all__ = ["FanItem", "FanResult", "fan_of"]


@dataclass(frozen=True)
class FanItem:
    """一个番种条目。"""

    name: str        # 川麻口语名
    fan: int         # 番数
    basis: str = ""  # 依据(牌码/事件说明)

    def to_dict(self) -> dict:
        return {"name": self.name, "fan": self.fan, "basis": self.basis}

    @classmethod
    def from_dict(cls, d: dict) -> "FanItem":
        return cls(name=d["name"], fan=d["fan"], basis=d.get("basis", ""))


@dataclass(frozen=True)
class FanResult:
    """一次胡牌的番种识别结果。"""

    items: list[FanItem]
    total_fan: int
    cap_applied: bool
    multiplier: int
    by: str

    def names(self) -> list[str]:
        return [it.name for it in self.items]

    def has(self, name: str) -> bool:
        return any(it.name == name for it in self.items)

    def to_dict(self) -> dict:
        return {
            "items": [it.to_dict() for it in self.items],
            "total_fan": self.total_fan,
            "cap_applied": self.cap_applied,
            "multiplier": self.multiplier,
            "by": self.by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FanResult":
        return cls(
            items=[FanItem.from_dict(it) for it in d.get("items", [])],
            total_fan=d["total_fan"],
            cap_applied=d.get("cap_applied", False),
            multiplier=d["multiplier"],
            by=d.get("by", ""),
        )


def _counts_of(hand14) -> list[int]:
    counts = [0] * tiles.NUM_TILES
    for idx in hand14:
        counts[idx] += 1
    return counts


def _all_triplets_concealed(counts: list[int]) -> bool:
    """暗手是否可全拆为刻子(用于对对胡判定)。

    暗手张数 = 2 + 3*k(k = 暗手面子数):一对将 + k 个暗刻。枚举每个对子作将,
    其余每种牌张数须恰为 0 或 3(暗刻;count==4 表示含 1 张顺子,必不在此路径)。
    """
    for head in range(tiles.NUM_TILES):
        if counts[head] < 2:
            continue
        ok = True
        for i in range(tiles.NUM_TILES):
            c = counts[i] - (2 if i == head else 0)
            if c not in (0, 3):
                ok = False
                break
        if ok:
            return True
    return False


def fan_of(
    hand14,
    melds: list[Meld] | None = None,
    lack: int | None = None,
    by: str = "tsumo",
    ctx: WinCtx | None = None,
    rules: FanRules | None = None,
) -> FanResult:
    """胡牌番种识别(纯函数)。详见模块文档串。"""
    rules = rules or DEFAULT_RULES
    melds = list(melds or [])
    counts = _counts_of(hand14)
    n_melds = len(melds)

    expected = 14 - 3 * n_melds
    if sum(counts) != expected:
        raise ValueError(
            f"fan_of 需暗手 {expected} 张(副露 {n_melds}),实际 {sum(counts)} 张"
        )
    if lack is not None:
        if sum(counts[lack * 9:lack * 9 + 9]) > 0:
            raise ValueError(f"防呆:胡牌暗手含缺门牌({tiles.SUIT_NAMES[lack]})")
        for m in melds:
            if tiles.suit_of(m.tile) == lack:
                raise ValueError(f"防呆:副露含缺门牌({tiles.SUIT_NAMES[lack]})")

    items: list[FanItem] = []

    all_tiles = list(hand14)
    for m in melds:
        all_tiles.extend([m.tile] * (4 if m.is_kan else 3))
    all_counts = _counts_of(all_tiles)

    suits = {tiles.suit_of(t) for t in all_tiles}
    qingyise = len(suits) == 1
    seven_pairs = n_melds == 0 and sum(c // 2 for c in counts) == 7
    long_qidui = seven_pairs and any(c == 4 for c in counts)
    qidui = seven_pairs and not long_qidui
    jingoudiao = n_melds == 4 and sum(counts) == 2 and len([c for c in counts if c == 2]) == 1
    # 对对胡:暗手全拆刻子+将(副露本就只有碰/杠两种,无吃);
    # 金勾钓手把将(暗手仅 2 张将)由金勾钓名目覆盖,不重复计对对胡。
    all_triplets = (not jingoudiao) and _all_triplets_concealed(counts)
    # 幺九:全 1/9(含将);七对路径另有名目,幺九仅在标准形叠加
    yaojiu = (not seven_pairs) and all(tiles.number_of(t) in (1, 9) for t in all_tiles)

    # ---- 牌型番(七对/龙七对互斥)----
    if long_qidui:
        items.append(FanItem("龙七对", rules.fan_long_qidui, "4 同张作两对"))
    elif qidui:
        items.append(FanItem("七对", rules.fan_qidui, "七个对子"))

    if all_triplets:
        items.append(FanItem("对对胡", rules.fan_duidui, "全刻子+将"))
    if qingyise:
        items.append(FanItem("清一色", rules.fan_qingyise,
                             f"全{tiles.SUIT_NAMES[next(iter(suits))]}"))
    if jingoudiao:
        items.append(FanItem("金勾钓", rules.fan_jingoudiao, "4 副露,手把将"))
    if yaojiu:
        items.append(FanItem("幺九", rules.fan_yaojiu, "全 1/9 牌"))

    # 七对本身是牌型番;标准形无任何大牌型 = 平胡 1 番
    standard_big = all_triplets or qingyise or jingoudiao or yaojiu
    if not seven_pairs and not standard_big:
        items.append(FanItem("平胡", 1, "基本牌型"))

    # ---- 天胡 / 地胡(值即顶格:番数记 cap_fan,倍数由封顶给出)----
    if ctx is not None:
        if ctx.heaven:
            items.append(FanItem("天胡", rules.cap_fan, "庄家首摸自摸,顶格"))
        if ctx.earth:
            items.append(FanItem("地胡", rules.cap_fan, "非庄胡庄家首打,顶格"))

    # ---- 事件番 ----
    if by == "tsumo":
        items.append(FanItem("自摸", rules.fan_zimo, "自摸胡"))
    if ctx is not None:
        if ctx.kan_win:
            items.append(FanItem("杠上开花", rules.fan_kan_kaihua, "岭上摸牌胡"))
        if ctx.kan_dama and not ctx.robbery:
            items.append(FanItem("杠上炮", rules.fan_kan_dama, "杠后打牌点炮"))
        if ctx.robbery:
            items.append(FanItem("抢杠胡", rules.fan_qianggang, "抢补杠胡"))
        if ctx.sea_bottom:
            name = "海底捞月" if by == "tsumo" else "海底炮"
            items.append(FanItem(name, rules.fan_haidi, "墙末张"))

    # ---- 根:暗手 4 同张 / 杠 各 1 根;龙七对的龙对 4 张不计根 ----
    gen_tiles = [
        tiles.index_to_code(i)
        for i, c in enumerate(all_counts)
        if c == 4 and not (long_qidui and counts[i] == 4)
    ]
    if gen_tiles:
        items.append(FanItem(
            "根", rules.fan_gen * len(gen_tiles),
            f"{'、'.join(gen_tiles)}" + (f" ×{len(gen_tiles)}" if len(gen_tiles) > 1 else ""),
        ))

    total = sum(it.fan for it in items)
    capped = min(total, rules.cap_fan)
    cap_applied = total > rules.cap_fan
    return FanResult(
        items=items,
        total_fan=capped,
        cap_applied=cap_applied,
        multiplier=rules.multiplier(total),
        by=by,
    )
