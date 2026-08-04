"""demo_practice:CLI 模拟人类(自动)跑一局练习,打印提示流/牌谱摘要。

用人类座0 + 3 启发式 AI(座1-3),完整血战到底。人类决策由 HeuristicActor 自动
代填(模拟),打印每个决策点的 phase / 合法动作数 / 推荐提示,终局打印牌谱摘要。

用法:
    python -m majiang_coach.demo_practice [seed]
    python -m majiang_coach.demo_practice 42 --strengths weak mid strong
    python -m majiang_coach.demo_practice 42 --no-hints --full   # 打印完整 JSON 牌谱

核心引擎零依赖;本 CLI 仅用标准库。
"""

from __future__ import annotations

import argparse
import json
import sys

from .ai import HeuristicActor
from .engine.action import Action, lack_action
from .practice import PracticeSession

_SUIT_NAME = {0: "万", 1: "条", 2: "筒"}
_PHASE_CN = {
    "swap": "换三张", "lack": "定缺", "turn_action": "自家摸牌后",
    "claim": "申索", "robbery": "抢杠", "game_over": "终局",
}


def _auto_action(pending, strength="mid"):
    actor = HeuristicActor(strength, 0)
    k = pending.kind
    if k == "swap":
        return Action("swap", tiles=actor.choose_swap(pending.view))
    if k == "lack":
        return lack_action(actor.choose_lack(pending.view))
    if k == "turn_action":
        return actor.choose_turn_action(pending.view, pending.drawn)
    if k in ("claim", "robbery"):
        return actor.choose_claim(pending.view, pending.legal_actions)
    raise ValueError(k)


def _print_prompt(p, step):
    phase = p["phase"]
    print(f"[{step}] {_PHASE_CN.get(phase, phase)}", end="")
    if p.get("drawn"):
        print(f" | 摸 {p['drawn']}", end="")
    if p["legal_actions"]:
        kinds = {}
        for a in p["legal_actions"]:
            kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
        print(f" | 合法动作: {kinds}", end="")
    if p.get("hint") and isinstance(p["hint"], dict) and p["hint"].get("recommend"):
        rec = p["hint"]["recommend"]
        print(f" | 硬算推荐弃 {rec['code']}(综合 {rec['composite_score']})", end="")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="练习模式 demo(人类自动 + 3 启发式 AI)")
    parser.add_argument("seed", type=int, nargs="?", default=42, help="随机种子")
    parser.add_argument("--strengths", nargs=3, default=["mid", "mid", "mid"],
                        choices=["weak", "mid", "strong"], help="座1-3 AI 强度")
    parser.add_argument("--hints", action=argparse.BooleanOptionalAction, default=False,
                        help="开/关 LLM 提示(默认 --no-hints)")
    parser.add_argument("--full", action="store_true", help="打印完整 JSON 牌谱")
    parser.add_argument("--json", action="store_true", help="打印摘要 JSON")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    s = PracticeSession(
        ai_strengths=args.strengths, hints_on=args.hints, seed=args.seed,
    )

    step = 0
    while not s.is_over():
        p = s.current_prompt()
        if s.is_over():
            break
        if not args.json:
            _print_prompt(p, step)
        act = _auto_action(s.pending)
        s.submit(act)
        step += 1
        if step > 5000:
            print("步数过多,中止", file=sys.stderr)
            return 1

    s._finalize()
    rec = s._record
    result = rec.result or {}

    if args.full:
        print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
        return 0

    summary = {
        "seed": args.seed,
        "strengths": args.strengths,
        "hints_on": args.hints,
        "steps": step,
        "num_events": len(rec.events),
        "winners": [{"seat": w["seat"], "by": w["by"], "tile": w["tile"],
                     "from": w.get("from"), "robbery": w.get("robbery", False)}
                    for w in result.get("winners", [])],
        "drawn": result.get("drawn", False),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== 终局 === 种子 {args.seed} | 强度 {args.strengths} | 步数 {step}")
        if summary["winners"]:
            for w in summary["winners"]:
                by = "自摸" if w["by"] == "tsumo" else f"点炮(座{w['from']})"
                extra = " 抢杠" if w["robbery"] else ""
                print(f"  胡家 座{w['seat']}:{by} {w['tile']}{extra}")
        else:
            print("  无胡家")
        print(f"  流局: {'是' if summary['drawn'] else '否'} | 事件数 {summary['num_events']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
