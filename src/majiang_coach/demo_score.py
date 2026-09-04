"""demo_score:CLI 算分——番种 + 完整结算(Phase 7,成都血战标准)。

用法:
    python -m majiang_coach.demo_score [seed]
    python -m majiang_coach.demo_score 42 --full       # 输出完整 SettleResult JSON
    python -m majiang_coach.demo_score --file x.json   # 直接结算牌谱 JSON

默认内跑一局 Game(...).run() 拿 record;打印各胡番种、杠钱、查叫/花猪与四座输赢。
核心引擎零依赖;本 CLI 仅用标准库。
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine.game import Game, RandomActor
from .engine.record import GameRecord
from .scoring import FanRules, settle_record

_KAN_CN = {"ankan": "暗杠", "daiminkan": "直杠", "shouminkan": "补杠"}


def _load_record(args) -> GameRecord:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return GameRecord.from_dict(json.load(f))
    actors = [RandomActor(args.seed * 4 + i) for i in range(4)]
    return Game(actors, args.seed).run()


def _print_settle(res, args) -> None:
    d = res.to_dict()
    seed_txt = args.seed if not args.file else f"文件 {args.file}"
    print(f"=== 结算 === {seed_txt} | {'流局' if d['drawn'] else '终局'} | 底分 {d['base_score']}")

    for w in d["wins"]:
        fan = w["fan"]
        names = "、".join(i["name"] for i in fan["items"])
        cap = "(封顶)" if fan["cap_applied"] else ""
        who = "自摸" if w["by"] == "tsumo" else f"点炮(座{w['from']})"
        payers = "、".join(f"座{p}" for p in w["payer_seats"])
        print(f"  胡 座{w['seat']} {who} {w['tile']}:{names},"
              f"{fan['total_fan']} 番 {fan['multiplier']} 倍{cap} | {payers} 各付 {w['amount_each']}")

    for k in d["kans"]:
        payers = "、".join(f"座{p}" for p in k["payer_seats"])
        print(f"  杠 座{k['seat']} {_KAN_CN.get(k['kind'], k['kind'])} {k['tile']}:"
              f"{payers} 各付 {k['amount_each']}(杠钱)")

    for t in d["tenpais"]:
        print(f"  查叫 座{t['payer']} 赔 座{t['wait_seat']} "
              f"(叫 {'、'.join(t['wait_tiles']) or '死叫'},理论 {t['max_fan']} 番 "
              f"{t['multiplier']} 倍):{t['amount']}")

    for h in d["huazhus"]:
        print(f"  查花猪 座{h['huazhu_seat']} 赔 座{h['payee']} 顶格:{h['amount']}")

    print("--- 四座输赢(底分单位)---")
    for seat in range(4):
        v = d["per_seat"][str(seat)]
        sign = "+" if v > 0 else ""
        print(f"  座{seat}: {sign}{v}")
    print(f"  合计: {sum(d['per_seat'].values())}(恒为 0)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="番种算分 + 完整结算(Phase 7)")
    parser.add_argument("seed", type=int, nargs="?", default=42, help="随机种子(--file 时忽略)")
    parser.add_argument("--file", default=None, help="直接读牌谱 JSON 文件(替代内跑一局)")
    parser.add_argument("--base", type=int, default=None, help="底分(默认 1)")
    parser.add_argument("--json", action="store_true", help="输出完整 SettleResult JSON")
    parser.add_argument("--full", action="store_true", help="同 --json(输出完整 SettleResult JSON)")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    record = _load_record(args)
    rules = FanRules.from_dict({"base_score": args.base} if args.base is not None else None)
    try:
        res = settle_record(record, rules)
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    if args.json or args.full:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_settle(res, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
