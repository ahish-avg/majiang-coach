"""CLI demo(Phase 3):给手牌 + 局面 -> 输出分析 JSON 与川麻口语摘要。

analyze(view) 纯函数:逐候选弃牌的进攻期望 + 安全度 + 综合排序推荐。

用法:
    # 14 张(刚摸态、待弃):输出弃牌候选与推荐
    python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p

    # 13 张(待摸态、轮别人):输出 hand + 可选 claim(需 --last-discard)
    python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 5s5s 3m4m --lack p --last-discard 5m

    # 副露(碰):--pon 5m 表示已碰 5m(来源座1)
    python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 5s5s --lack p --pon 5m

牌码可单张(1m)或同门拼接(1m2m3m);空格分隔。--lack 指定缺门(m/s/p)。
"""

from __future__ import annotations

import argparse
import json
import sys

from .analysis import analyze, analysis_result_to_dict
from .engine.melds import Meld
from .engine.view import PlayerView
from .hand import Hand
from .tiles import code_to_index, index_to_code, index_to_emoji

_SUIT_LETTER = {"m": 0, "s": 1, "p": 2}
_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}


def _build_view(args) -> PlayerView:
    lack = _SUIT_LETTER[args.lack] if args.lack else None
    tokens: list[str] = []
    for c in args.codes:
        tokens.extend(c.split())
    hand = Hand.from_codes(tokens)

    melds: list[Meld] = []
    for spec in args.pon or []:
        # spec 形如 "5m" 或 "5m:1"(牌码:来源座)
        code, _, src_s = spec.partition(":")
        tile = code_to_index(code)
        src = int(src_s) if src_s else 1
        melds.append(Meld(kind="pon", tile=tile, src_seat=src))

    public_melds: tuple = (tuple(melds), (), (), ())
    # 公开缺门:自家缺门公开,他座缺门未知(默认与自家同或缺省)
    lack_suits = (lack, lack, lack, lack) if lack is not None else ()

    last_discard = None
    if args.last_discard:
        lt = code_to_index(args.last_discard)
        last_discard = (1, lt)

    return PlayerView(
        seat=0,
        hand=hand,
        melds=tuple(melds),
        lack_suit=lack,
        lack_suits=lack_suits,
        public_melds=public_melds,
        discards=((), (), (), ()),
        wall_remaining=args.wall,
        active_seats=(0, 1, 2, 3),
        last_discard=last_discard,
    )


def _shanten_cn(s: int) -> str:
    if s == -1:
        return "已胡牌"
    if s == 0:
        return "下叫(听牌)"
    return f"差 {s} 张下叫"


def _summary(result) -> str:
    lines: list[str] = []
    lack = result.lack_suit
    lack_label = _SUIT_NAME[lack] if lack is not None else "(自动)"
    lines.append(f"座 {result.seat} | 暗手 {result.hand_total} 张 | 缺门 {lack_label} | 副露 {len(result.melds)} 副")
    lines.append(f"当前: {_shanten_cn(result.hand.shanten)} | 进攻分 {result.hand.score}")
    if result.hand.ukeire:
        waits = " ".join(f"{index_to_code(u.tile_index)}{index_to_emoji(u.tile_index)}" for u in result.hand.ukeire)
        lines.append(f"进张/叫牌({result.hand.ukeire_count}种,未见{result.hand.ukeire_remaining_total}): {waits}")

    if result.candidates:
        lines.append("")
        lines.append(f"弃牌候选({len(result.candidates)}张,按综合降序):")
        lines.append(f"  {'牌':<6}{'差张':<6}{'进攻':<6}{'防守':<6}{'综合':<6}理由")
        for c in result.candidates:
            mark = " <== 推荐" if (result.recommend and c.tile == result.recommend.tile) else ""
            emoji = index_to_emoji(c.tile)
            lines.append(
                f"  {index_to_code(c.tile)}{emoji:<4}"
                f"{_shanten_cn(c.shanten_after):<7}"
                f"{c.offense_score:<6}{c.defense_score:<6}{c.composite_score:<6}"
                f"{c.safety_reasons[0] if c.safety_reasons else ''}{mark}"
            )
        if result.recommend:
            lines.append("")
            bo = result.best_offense
            bd = result.best_defense
            lines.append(
                f"推荐弃牌: {index_to_code(result.recommend.tile)}{index_to_emoji(result.recommend.tile)}"
                f"(综合 {result.recommend.composite_score}) | "
                f"最佳进攻: {index_to_code(bo.tile)}({bo.offense_score}) | "
                f"最安全: {index_to_code(bd.tile)}({bd.defense_score})"
            )

    if result.claim:
        c = result.claim
        lines.append("")
        parts = [f"申索 {c['code']}:"]
        parts.append("可胡(ron)" if c["can_ron"] else "不可胡")
        parts.append("可碰(pon)" if c["can_pon"] else "不可碰")
        if c["pon_shanten_after"] is not None:
            parts.append(f"碰后{_shanten_cn(c['pon_shanten_after'])}")
        lines.append(" ".join(parts))

    lines.append("")
    lines.append(f"权重: 进攻 {result.weights_used['offense']} / 防守 {result.weights_used['defense']}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="majiang-analyze",
        description="川麻血战 Phase 3 分析引擎(进攻期望 + 安全度 + 综合推荐)",
    )
    p.add_argument("codes", nargs="+", help="牌码,空格分隔(单张或同门拼接)")
    p.add_argument("--lack", choices=["m", "s", "p"], default=None, help="指定缺门")
    p.add_argument("--pon", action="append", help="已碰副露,形如 5m 或 5m:1(牌码:来源座),可多次")
    p.add_argument("--last-discard", default=None, help="最近弃牌(牌码,如 5m),用于 13 张 claim")
    p.add_argument("--wall", type=int, default=30, help="牌墙剩余(默认 30)")
    p.add_argument("--json", action="store_true", help="输出完整 JSON(而非摘要)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    try:
        view = _build_view(args)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    try:
        result = analyze(view)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(analysis_result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(_summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
