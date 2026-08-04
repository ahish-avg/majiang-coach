"""CLI demo(Phase 4):给手牌 + 局面 + hints_on -> 输出 advise JSON/摘要。

advise(view, hints_on, llm_config, weights) -> AdviseResult:
硬算 analysis(始终有)+ 可选 LLM Advice(防幻觉、不替打)。

用法:
    # 14 张(刚摸态)+ 默认开提示(.env 配 LLM 即调 LLM,否则兜底硬算)
    python -m majiang_coach.demo_advise 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p

    # 关提示:仅硬算 analysis,advice=null(无需 LLM 配置即可演示)
    python -m majiang_coach.demo_advise 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p --no-hints

    # 13 张(待摸态)+ claim
    python -m majiang_coach.demo_advise 1m2m3m 4m5m6m 7m8m9m 5s5s 3m4m --lack p --last-discard 5m

    # 每请求覆盖 LLM(优先级 > .env)
    python -m majiang_coach.demo_advise 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p \
        --base-url https://api.deepseek.com --api-key sk-xxx --model deepseek-chat

牌码可单张(1m)或同门拼接(1m2m3m);空格分隔。--lack 指定缺门(m/s/p)。
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine.melds import Meld
from .engine.view import PlayerView
from .hand import Hand
from .llm import advise, resolve_llm_config
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
        code, _, src_s = spec.partition(":")
        tile = code_to_index(code)
        src = int(src_s) if src_s else 1
        melds.append(Meld(kind="pon", tile=tile, src_seat=src))

    public_melds: tuple = (tuple(melds), (), (), ())
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


def _summary(res) -> str:
    a = res.analysis
    lines: list[str] = []
    lines.append(f"座 {a['seat']} | 暗手 {a['hand_total']} 张 | 缺门 {_SUIT_NAME.get(a['lack_suit'], '?')} | 副露 {len(a['melds'])} 副")
    lines.append(f"当前: {_shanten_cn(a['hand']['shanten'])} | 进攻分 {a['hand']['score']} | 提示开关: {'开' if res.hints_on else '关'}")

    rec = a.get("recommend")
    if rec:
        lines.append(
            f"硬算推荐弃牌: {rec['code']}{index_to_emoji(_code_idx(rec['code']))}"
            f"(综合 {rec['composite_score']}) | 进攻 {rec['offense_score']} 防守 {rec['defense_score']} 危险 {rec['danger']}"
        )
    elif a.get("claim"):
        c = a["claim"]
        parts = [f"申索 {c['code']}:"]
        parts.append("可胡(ron)" if c["can_ron"] else "不可胡")
        parts.append("可碰(pon)" if c["can_pon"] else "不可碰")
        if c.get("pon_shanten_after") is not None:
            parts.append(f"碰后{_shanten_cn(c['pon_shanten_after'])}")
        lines.append(" ".join(parts))

    lines.append("")
    if res.advice is not None:
        adv = res.advice
        lines.append(f"LLM 建议(model={res.model_used}):")
        rt = adv.recommended_tile
        lines.append(f"  推荐弃牌: {rt if rt else '(待摸态,无推荐)'}")
        lines.append(f"  进攻理由: {adv.offense_reason}")
        lines.append(f"  防守理由: {adv.defense_reason}")
        lines.append(f"  教学点: {adv.teaching_point}")
        lines.append(f"  对手读牌: {adv.opponent_read}")
    elif res.error:
        lines.append(f"LLM 未出建议: {res.error}(已降级为硬算 analysis)")
    else:
        lines.append("LLM 未启用(hints_on=false),仅硬算 analysis。")

    return "\n".join(lines)


def _code_idx(code: str) -> int:
    return code_to_index(code)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="majiang-advise",
        description="川麻血战 Phase 4 LLM 助手(硬算 + 可插拔 LLM 解释,防幻觉)",
    )
    p.add_argument("codes", nargs="+", help="牌码,空格分隔(单张或同门拼接)")
    p.add_argument("--lack", choices=["m", "s", "p"], default=None, help="指定缺门")
    p.add_argument("--pon", action="append", help="已碰副露,形如 5m 或 5m:1(牌码:来源座),可多次")
    p.add_argument("--last-discard", default=None, help="最近弃牌(牌码,如 5m),用于 13 张 claim")
    p.add_argument("--wall", type=int, default=30, help="牌墙剩余(默认 30)")
    p.add_argument("--hints", action=argparse.BooleanOptionalAction, default=True,
                   help="开/关 LLM 提示(默认 --hints;--no-hints 仅硬算)")
    p.add_argument("--base-url", default=None, help="LLM base_url 覆盖(优先级 > .env)")
    p.add_argument("--api-key", default=None, help="LLM api_key 覆盖(优先级 > .env)")
    p.add_argument("--model", default=None, help="LLM model 覆盖(优先级 > .env)")
    p.add_argument("--weights", default=None, help='权重 JSON,如 \'{"offense":0.6,"defense":0.4}\'')
    p.add_argument("--json", action="store_true", help="输出完整 AdviseResult JSON(而非摘要)")
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

    override: dict = {}
    if args.base_url:
        override["base_url"] = args.base_url
    if args.api_key:
        override["api_key"] = args.api_key
    if args.model:
        override["model"] = args.model
    llm_config = resolve_llm_config(override or None)

    weights = None
    if args.weights:
        try:
            weights = json.loads(args.weights)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"错误:--weights 非合法 JSON:{e}", file=sys.stderr)
            return 2

    try:
        res = advise(view, hints_on=args.hints, llm_config=llm_config, weights=weights)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_summary(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
