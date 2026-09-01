"""demo_review:CLI 复盘——牌谱逐步回放 + AI 点评(Phase 6)。

用法:
    python -m majiang_coach.demo_review [seed]
    python -m majiang_coach.demo_review 42 --full          # 输出完整 ReviewResult JSON
    python -m majiang_coach.demo_review 42 --seat 0        # 只点评座 0
    python -m majiang_coach.demo_review 42 --hints         # 开 LLM 提示(需 .env 配置,否则兜底)
    python -m majiang_coach.demo_review 42 --hints --no-llm
    python -m majiang_coach.demo_review --file x.json      # 直接读牌谱 JSON

默认内跑一局 Game(...).run() 拿 record;--file 直接读牌谱 JSON。
核心引擎零依赖;本 CLI 仅用标准库。
"""

from __future__ import annotations

import argparse
import json
import sys

from .engine.game import Game, RandomActor
from .engine.record import GameRecord
from .llm import resolve_llm_config
from .review import review_record

_PHASE_CN = {
    "turn_action": "摸牌决策",
    "claim": "申索",
    "win": "胡牌",
    "over": "终局",
}
_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}


def _load_record(args) -> GameRecord:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return GameRecord.from_dict(json.load(f))
    actors = [RandomActor(args.seed * 4 + i) for i in range(4)]
    return Game(actors, args.seed).run()


def _print_review(res, args) -> None:
    d = res.to_dict()
    print(f"=== 复盘 === 种子 {d['meta'].get('seed')} | 步骤 {d['summary']['num_steps']}")
    for s in d["steps"]:
        seat = f"座{s['seat']}" if s["seat"] >= 0 else "全场"
        print(f"[{s['step']:>3}] {_PHASE_CN.get(s['phase'], s['phase'])} | {seat} | {s['comment']}")
    print("\n=== 按座汇总 ===")
    for seat, stats in d["summary"]["per_seat"].items():
        win = {"tsumo": "自摸", "ron": "点炮"}.get(stats["win_by"], "未胡")
        print(f"座{seat}: 决策 {stats['turn_steps']} 次 | 与硬算一致 {stats['matched_actual']} | "
              f"申索 {stats['claims']} | {win}")
    ev = d["summary"].get("events", {})
    print(f"事件计数: {ev}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="复盘系统:牌谱逐步回放 + AI 点评(Phase 6)")
    parser.add_argument("seed", type=int, nargs="?", default=42, help="随机种子(--file 时忽略)")
    parser.add_argument("--file", default=None, help="直接读牌谱 JSON 文件(替代内跑一局)")
    parser.add_argument("--hints", action=argparse.BooleanOptionalAction, default=False,
                        help="开/关 LLM 提示(默认 --no-hints;仅硬算 analysis)")
    parser.add_argument("--seat", type=int, default=None, help="只点评该座(默认全部 4 座)")
    parser.add_argument("--json", action="store_true", help="输出完整 ReviewResult JSON")
    parser.add_argument("--full", action="store_true", help="同 --json(输出完整 ReviewResult JSON)")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    record = _load_record(args)
    llm_config = resolve_llm_config() if args.hints else None
    try:
        res = review_record(
            record, hints_on=args.hints, llm_config=llm_config,
            seat_focus=args.seat,
        )
    except ValueError as e:
        print(f"错误:{e}", file=sys.stderr)
        return 2

    if args.json or args.full:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_review(res, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
