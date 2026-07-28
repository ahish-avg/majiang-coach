"""CLI demo:读入手牌 -> 输出 是否胡牌/听牌/向听/有效牌。

用法:
    python -m majiang_coach.demo 1m 2m 3m 4m5m6m 7m8m9m 1s2s3s 5s5s
    python -m majiang_coach.demo 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s --lack p

牌码可单张(1m)或同门拼接(1m2m3m);空格分隔。--lack 指定缺门(m/s/p)。
"""

from __future__ import annotations

import argparse
import sys

from .hand import Hand
from .shanten import shanten
from .tiles import index_to_code, index_to_emoji
from .ukeire import ukeire
from .win import win

_SUIT_LETTER = {"m": 0, "s": 1, "p": 2}
_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}


def _fmt(idx: int, emoji: bool = True) -> str:
    if emoji:
        return f"{index_to_code(idx)}{index_to_emoji(idx)}"
    return index_to_code(idx)


def analyze(hand: Hand, lack_suit: int | None = None, emoji: bool = True) -> str:
    total = hand.total
    lack_label = _SUIT_NAME[lack_suit] if lack_suit is not None else "(自动枚举最优缺门)"
    lines: list[str] = []
    lines.append(f"手牌({total}张): {' '.join(_fmt(i, emoji) for i in hand.to_indices())}")
    lines.append(f"缺门: {lack_label}  出现门: {sorted(_SUIT_NAME[s] for s in hand.suits_present())}")

    if total == 14:
        is_win = win(hand, lack_suit)
        lines.append(f"是否胡牌: {'是' if is_win else '否'}")

    s = shanten(hand, lack_suit)
    # 川麻口语:向听数 -> 差几张下叫(听牌=下叫)
    if s == -1:
        lines.append("下叫状态: 已胡牌")
    elif s == 0:
        lines.append("下叫状态: 下叫(听牌) - 差 0 张")
    else:
        lines.append(f"下叫状态: 差 {s} 张下叫")

    if total == 13:
        u = ukeire(hand, lack_suit)
        if s == 0:
            machi = " ".join(_fmt(t.tile_index, emoji) for t in u)
            lines.append(f"叫牌({len(u)}种,摸到即胡): {machi or '(无 - 可能死叫)'}")
        else:
            imps = "  ".join(
                f"{_fmt(t.tile_index, emoji)}->差{t.new_shanten}张" for t in u
            )
            lines.append(f"进张({len(u)}种,摸入后差几张下叫): {imps or '(无)'}")
    elif total == 14 and s != -1:
        lines.append("(14 张非胡:差几张下叫 = 弃一张后最优;进张请用 13 张输入)")

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="majiang-demo",
        description="川麻血战 Phase 1 手牌分析(胡牌/听牌/向听/有效牌)",
    )
    p.add_argument("codes", nargs="+", help="牌码,空格分隔(单张或同门拼接,如 1m 2m3m 5p5p)")
    p.add_argument("--lack", choices=["m", "s", "p"], default=None, help="指定缺门")
    p.add_argument("--no-emoji", dest="emoji", action="store_false", help="不显示 emoji(兼容不支持 unicode 的终端)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    lack = _SUIT_LETTER[args.lack] if args.lack else None

    # Windows 控制台默认 GBK,emoji 会触发 UnicodeEncodeError;尝试切到 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    tokens: list[str] = []
    for c in args.codes:
        tokens.extend(c.split())
    if not tokens:
        print("错误:未输入牌码", file=sys.stderr)
        return 2

    try:
        hand = Hand.from_codes(tokens)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    try:
        out = analyze(hand, lack, emoji=args.emoji)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
