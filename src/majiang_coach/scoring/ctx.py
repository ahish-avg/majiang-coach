"""ctx.py:胡牌事件上下文扫描(Phase 7,轻量、不 import review/)。

逐事件扫描 GameRecord 事件流,为每个 tsumo/ron 事件判定事件番所需事实:
  - kan_win(杠上开花):tsumo 前邻同座 kan_draw(岭上摸牌后胡)。
  - kan_dama(杠上炮):ron 点炮者的上一摸为 kan_draw(杠后打牌点炮);
    抢杠(robbery)互斥(抢杠胡另计)。
  - sea_bottom(海底捞月/海底炮):胡牌时牌墙已空(该次摸牌为墙末张)。
    墙计数仿 ReviewCursor:108 - 发牌张数 - 累计 draw/kan_draw 数;摸至 0 即墙空。
  - heaven(天胡):庄家(座 0)首次摸牌即自摸,之前无任何 draw/discard。
  - earth(地胡):非庄家在全场首张弃牌(庄家首打)上 ron,之前无任何弃牌。
  - robbery(抢杠胡):ron 事件自带 robbery=True。

确定性纯函数:同 record -> 同上下文列表。
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import tiles

__all__ = ["WinCtx", "scan_win_contexts"]

_TOTAL_TILES = 108


@dataclass(frozen=True)
class WinCtx:
    """一次胡牌(tsumo/ron 事件)的事件番上下文。"""

    event_index: int
    seat: int
    by: str                    # "tsumo" | "ron"
    tile: int
    from_seat: int | None
    robbery: bool
    kan_win: bool              # 杠上开花
    kan_dama: bool             # 杠上炮
    sea_bottom: bool           # 海底捞月 / 海底炮
    heaven: bool               # 天胡
    earth: bool                # 地胡


def scan_win_contexts(events: list[dict]) -> list[WinCtx]:
    """扫描事件流,按胡牌事件顺序返回 WinCtx 列表。"""
    wall = _TOTAL_TILES
    last_draw: dict[int, tuple[str, bool]] = {}  # seat -> (src, is_kan) 最近一次摸牌
    win_at_sea_bottom = False  # 墙摸空当巡:该摸之后、下一 draw 之前的胡牌
    ctxs: list[WinCtx] = []

    for i, ev in enumerate(events):
        t = ev["t"]

        if t == "deal":
            wall -= len(ev["tiles"])
            continue

        if t in ("draw", "kan_draw"):
            s = ev["seat"]
            is_kan = t == "kan_draw"
            wall -= 1
            last_draw[s] = (ev.get("src", "wall"), is_kan)
            # 墙摸空:这张就是海底牌,本巡胡牌算海底捞月/炮
            win_at_sea_bottom = wall == 0
            continue

        if t == "discard":
            continue

        if t == "tsumo":
            s = ev["seat"]
            _, is_kan = last_draw.get(s, ("wall", False))
            heaven = s == 0 and _is_dealer_first_trip(events, i)
            ctxs.append(WinCtx(
                event_index=i, seat=s, by="tsumo",
                tile=tiles.code_to_index(ev["tile"]), from_seat=None,
                robbery=False,
                kan_win=bool(is_kan),
                kan_dama=False,
                sea_bottom=win_at_sea_bottom,
                heaven=heaven,
                earth=False,
            ))
            win_at_sea_bottom = False
            continue

        if t == "ron":
            s = ev["seat"]
            frm = ev["from"]
            robbery = bool(ev.get("robbery"))
            earth = _is_earth_win(events, i)
            _, disc_was_kan = last_draw.get(frm, ("wall", False))
            ctxs.append(WinCtx(
                event_index=i, seat=s, by="ron",
                tile=tiles.code_to_index(ev["tile"]), from_seat=frm,
                robbery=robbery,
                kan_win=False,
                kan_dama=disc_was_kan and not robbery,
                sea_bottom=win_at_sea_bottom,
                heaven=False,
                earth=earth,
            ))
            win_at_sea_bottom = False
            continue

    return ctxs


def _is_dealer_first_trip(events: list[dict], i: int) -> bool:
    """tsumo 事件 i 是否为天胡:庄家首摸(全场第一张 draw)即自摸。

    它之前恰有一次 draw(庄家首摸,发牌后),无 discard/pon/kan/ron。
    """
    draws = 0
    for ev in events[:i]:
        tt = ev["t"]
        if tt in ("draw", "kan_draw"):
            draws += 1
        elif tt in ("discard", "pon", "kan", "ron"):
            return False
    return draws == 1


def _is_earth_win(events: list[dict], i: int) -> bool:
    """ron 事件 i 是否为地胡:非庄家胡在庄家首打(全场第一张弃牌)上。

    它之前恰有一次 discard(全场首张),且无任何副露/杠/胡牌事件。
    """
    discards = 0
    for ev in events[:i]:
        tt = ev["t"]
        if tt == "discard":
            discards += 1
        elif tt in ("pon", "kan", "ron"):
            return False
    return discards == 1
